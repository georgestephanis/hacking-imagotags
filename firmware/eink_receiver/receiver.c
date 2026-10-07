/* Image receiver for the SES-imagotag HRD3-0210-A (EFR32FG22C121F512GM40, 250x128 black/white/red e-paper).
 *
 * The tag listens on its rail signal contact (PB01) for a serial frame, checks it, and shows it on the e-paper.
 *
 *   Wire: GND, +3.3 V (spring contacts), and the signal contact driven by a 3.3 V serial TX (idle high).
 *   Link: UART, 8N1, any baud from about 2400 to 230400 (tested at 38400). The tag measures the baud rate from the first byte.
 *   Frame, all bytes sent back to back:
 *       0x55                    sync / auto-baud byte
 *       0xA5 0x5A               magic
 *       8000 bytes              payload: black/white plane (4000 bytes) then red plane (4000 bytes), see scripts/eink_draw.py:
 *                               250 lines of 16 bytes, y = 0 at the bottom, bit 7 = lowest y; plane 1: 0 = black, plane 2: 0 = red
 *       CRC16 (hi, lo)          CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over the 8000 payload bytes
 *   Only a frame with a good CRC is drawn (the refresh takes ~18 s; send the next frame after the LED shows green).
 *
 *   LED (common-anode RGB behind PD00 enable), dimmed to 10 % by software PWM on PD00 (LED_DUTY): green = booted, red = bad frame,
 *   white = refreshing, green = done. It is NOT lit while receiving: PWM ticks would disturb the bit sampling, so 'blue = receiving' is gone.
 *
 * Hardware facts (docs/log.md): PB01 = signal contact (one-way, internal pull-down used), PD00 = LED enable, PB02/PB00/PB04 = R/G/B
 * (active high), e-paper: PC00 = SDA, PC01 = SCK, PC02 = CS, PC03 = D/C, PC04 = RES, PA08 = BUSY (low = busy), PC06 = power path (LOW).
 * Controller: UC81xx style. Core clock after reset: ~19 MHz HFRCO (measured 19.1 MHz).
 *
 * Built by scripts/build_fw.py (no linker): everything must be position independent, no global data, no const arrays.
 */
#include <stdint.h>

#define REG(a)  (*(volatile uint32_t *)(a))

#define CPU_HZ          19000000u
#define US(n)           ((n) * (CPU_HZ / 1000000u))
#define MS(n)           (US(n) * 1000u)

#define BUF             ((volatile uint8_t *)0x20000000u)     /* 8000-byte frame buffer; stack is at the top of the 32 KB RAM */
#define PLANE_BYTES     4000u
#define PAYLOAD_BYTES   8000u

#define CMU_CLKEN0      0x40008064u
#define GPIO            0x4003C000u
#define PORT(p)         (GPIO + 0x30u * (p))
#define MODEL(p)        REG(PORT(p) + 0x04u)
#define MODEH(p)        REG(PORT(p) + 0x0Cu)
#define DOUT(p)         REG(PORT(p) + 0x10u)
#define DIN(p)          REG(PORT(p) + 0x14u)
#define PA 0u
#define PB 1u
#define PC 2u
#define PD 3u

#define DEMCR           REG(0xE000EDFCu)
#define DWT_CTRL        REG(0xE0001000u)
#define CYCCNT          REG(0xE0001004u)

/* e-paper pins on port C */
#define P_SDA   (1u << 0)
#define P_SCK   (1u << 1)
#define P_CS    (1u << 2)
#define P_DC    (1u << 3)
#define P_RES   (1u << 4)

#define SIG()           ((DIN(PB) >> 1) & 1u)               /* PB01: rail signal */
#define EPD_BUSY_HIGH() ((DIN(PA) >> 8) & 1u)               /* PA08: high = idle */

enum { LED_RED = 1, LED_GREEN = 2, LED_BLUE = 4, LED_WHITE = 7 };

/* ---------------------------------------------------------------- timing */

static void wait_until(uint32_t t)
{
    while ((int32_t)(CYCCNT - t) < 0) { }
}

/* ------------------------------------------------------------------ GPIO */

static void gpio_mode(uint32_t port, uint32_t pin, uint32_t mode)
{
    if (pin < 8) {
        uint32_t sh = 4u * pin;
        MODEL(port) = (MODEL(port) & ~(0xFu << sh)) | (mode << sh);
    } else {
        uint32_t sh = 4u * (pin - 8u);
        MODEH(port) = (MODEH(port) & ~(0xFu << sh)) | (mode << sh);
    }
}

static void led(uint32_t colour)             /* selects the colour; led_tick() does the dimming */
{
    uint32_t out = DOUT(PB) & ~0x15u;
    if (colour & LED_RED)   out |= 1u << 2;
    if (colour & LED_GREEN) out |= 1u << 0;
    if (colour & LED_BLUE)  out |= 1u << 4;
    DOUT(PB) = out;
    if (!colour) DOUT(PD) &= ~1u;            /* PD00 = LED supply enable */
}

/* Software PWM on the LED supply enable: ~1.16 kHz, LED_DUTY / LED_PERIOD on. Call often wherever timing is not critical. */
#define LED_PERIOD      16384u
#define LED_DUTY        (LED_PERIOD / 10u)          /* 10 % */

static void led_tick(void)
{
    if ((DOUT(PB) & 0x15u) && (CYCCNT & (LED_PERIOD - 1u)) < LED_DUTY) DOUT(PD) |= 1u; else DOUT(PD) &= ~1u;
}

static void delay_cycles(uint32_t n)
{
    uint32_t t = CYCCNT + n;
    while ((int32_t)(CYCCNT - t) < 0) led_tick();
}

/* --------------------------------------------------------------- e-paper */

static void epd_begin(uint32_t dc)          /* chip select low; dc = P_DC for data, 0 for a command */
{
    DOUT(PC) = P_RES | P_CS | P_DC;
    DOUT(PC) = P_RES | dc;
}

static void epd_byte(uint32_t b, uint32_t dc)
{
    for (int i = 7; i >= 0; i--) {
        uint32_t v = P_RES | dc | (((b >> i) & 1u) ? P_SDA : 0u);
        DOUT(PC) = v;
        DOUT(PC) = v | P_SCK;
    }
    DOUT(PC) = P_RES | dc;
}

static void epd_end(void)
{
    DOUT(PC) = P_RES | P_CS | P_DC;
}

static void epd_cmd(uint32_t c)
{
    epd_begin(0);
    epd_byte(c, 0);
    epd_end();
}

static void epd_data(uint32_t d)
{
    epd_begin(P_DC);
    epd_byte(d, P_DC);
    epd_end();
}

static int epd_wait_idle(uint32_t timeout_ms)     /* 1 = idle, 0 = timed out */
{
    uint32_t limit = CYCCNT + MS(timeout_ms);
    while (!EPD_BUSY_HIGH()) {
        if ((int32_t)(CYCCNT - limit) >= 0) return 0;
        led_tick();
    }
    return 1;
}

static void epd_plane(uint32_t cmd, uint32_t offset)
{
    epd_cmd(cmd);
    epd_begin(P_DC);
    for (uint32_t i = 0; i < PLANE_BYTES; i++) { epd_byte(BUF[offset + i], P_DC); led_tick(); }
    epd_end();
}

static void epd_show(void)
{
    DOUT(PC) = P_CS | P_DC;                         /* reset pulse: RES low 20 ms */
    delay_cycles(MS(20));
    DOUT(PC) = P_RES | P_CS | P_DC;
    delay_cycles(MS(100));

    epd_cmd(0x01); epd_data(0x03); epd_data(0x00); epd_data(0x2B); epd_data(0x2B); epd_data(0x03);   /* power settings */
    epd_cmd(0x06); epd_data(0x17); epd_data(0x17); epd_data(0x17);                                    /* booster soft start */
    epd_cmd(0x04); epd_wait_idle(1000);                                                               /* power on */
    epd_cmd(0x00); epd_data(0xCF);                                                                    /* panel setting */
    epd_cmd(0x61); epd_data(128); epd_data(0); epd_data(250);                                         /* 128 px x 250 lines */
    epd_cmd(0x50); epd_data(0x77);                                                                    /* border / data interval */
    epd_plane(0x10, 0);                                                                               /* black/white plane */
    epd_plane(0x13, PLANE_BYTES);                                                                     /* red plane */
    epd_cmd(0x12);                                                                                    /* refresh (~18 s, BUSY low) */
    delay_cycles(MS(200));
    epd_wait_idle(60000);
    epd_cmd(0x02);                                                                                    /* power off */
    epd_wait_idle(2000);
}

/* ---------------------------------------------------------------- receive */

/* Wait for a clean high-to-low edge; returns 1 and the cycle count at the edge, or 0 after timeout_cycles. */
static int next_start(uint32_t timeout_cycles, uint32_t *t)
{
    uint32_t limit = CYCCNT + timeout_cycles;
    while (!SIG()) { if ((int32_t)(CYCCNT - limit) >= 0) return 0; }
    while (SIG())  { if ((int32_t)(CYCCNT - limit) >= 0) return 0; }
    *t = CYCCNT;
    return 1;
}

static uint32_t crc16_step(uint32_t crc, uint32_t b)
{
    crc ^= b << 8;
    for (int i = 0; i < 8; i++) crc = (crc & 0x8000u) ? ((crc << 1) ^ 0x1021u) : (crc << 1);
    return crc & 0xFFFFu;
}

/* Receive one byte after its start edge was seen at time ts; bit time T cycles. */
static uint32_t sample_byte(uint32_t ts, uint32_t T)
{
    uint32_t tt = ts + T + (T >> 1), v = 0;
    for (uint32_t b = 0; b < 8; b++) {
        wait_until(tt);
        v |= SIG() << b;
        tt += T;
    }
    return v;
}

/* 0 = no valid sync (ignore), 1 = good frame in BUF, 2 = frame started but magic/CRC/timing failed */
static int receive_frame(void)
{
    uint32_t t[5], ts;

    /* auto-baud on 0x55: falling edges at 0, 2T, 4T, 6T, 8T */
    if (!next_start(MS(1000), &t[0])) return 0;
    for (int i = 1; i < 5; i++) if (!next_start(MS(10), &t[i])) return 0;
    uint32_t T = (t[4] - t[0]) >> 3;
    if (T < CPU_HZ / 230400u || T > CPU_HZ / 2400u) return 0;
    for (int i = 1; i < 5; i++) {
        uint32_t d = t[i] - t[i - 1];
        if (d < T + (T >> 1) || d > 2u * T + (T >> 1)) return 0;     /* each interval should be about 2T (+-25%) */
    }

    uint32_t crc = 0xFFFFu, byte_timeout = CPU_HZ / 2u;              /* 0.5 s of silence ends the frame */

    if (!next_start(byte_timeout, &ts) || sample_byte(ts, T) != 0xA5u) return 2;
    if (!next_start(byte_timeout, &ts) || sample_byte(ts, T) != 0x5Au) return 2;
    for (uint32_t i = 0; i < PAYLOAD_BYTES; i++) {
        if (!next_start(byte_timeout, &ts)) return 2;
        uint32_t b = sample_byte(ts, T);
        BUF[i] = (uint8_t)b;
        crc = crc16_step(crc, b);
    }
    if (!next_start(byte_timeout, &ts)) return 2;
    uint32_t hi = sample_byte(ts, T);
    if (!next_start(byte_timeout, &ts)) return 2;
    uint32_t lo = sample_byte(ts, T);
    return (((hi << 8) | lo) == crc) ? 1 : 2;
}

/* ------------------------------------------------------------------- main */

void reset(void)
{
    REG(CMU_CLKEN0) |= 1u << 26;                                    /* GPIO clock */
    DEMCR |= 1u << 24;                                              /* enable the DWT cycle counter */
    DWT_CTRL |= 1u;

    /* LED: PD00 enable + PB00/PB02/PB04 outputs (low); signal PB01 input with pull-down (DOUT bit 1 = 0) */
    gpio_mode(PD, 0, 4);
    DOUT(PD) &= ~1u;
    DOUT(PB) &= ~0x1Fu;
    gpio_mode(PB, 0, 4); gpio_mode(PB, 2, 4); gpio_mode(PB, 4, 4);
    gpio_mode(PB, 1, 2);

    /* e-paper: PC00-PC04 outputs idle (RES, CS, DC high), PC06 low = display power path on, PA08 busy input with pull-down */
    DOUT(PC) = P_RES | P_CS | P_DC;
    for (uint32_t p = 0; p < 5; p++) gpio_mode(PC, p, 4);
    gpio_mode(PC, 6, 4);
    DOUT(PA) &= ~(1u << 8);
    gpio_mode(PA, 8, 2);

    led(LED_GREEN);
    delay_cycles(MS(300));
    led(0);

    for (;;) {
        int r = receive_frame();
        if (r == 1) {
            led(LED_WHITE);
            epd_show();
            led(LED_GREEN);
            delay_cycles(MS(1000));
            led(0);
        } else if (r == 2) {
            led(LED_RED);
            delay_cycles(MS(1000));
            led(0);
        }
    }
}
