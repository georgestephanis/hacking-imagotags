/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Standalone name badge for the SES-imagotag HRD3-0210-A (ContRD010A: EFR32FG22C121F512GM40, 250x128 black/white/red e-paper).
 *
 * Shows page 0 at power-up. Button (PB03, active-low):
 *   short press (released in under LONG_PRESS_MS): next page, wrapping from the last to the first;
 *   long press  (held for LONG_PRESS_MS, recognised while still held, dim blue flash): back to page 0 (nothing if already there).
 * Presses during a refresh (~22 s) are ignored; a button still held when the refresh ends is not counted.
 *
 * The pages live in flash, built by nametag/make_pages.py and flashed at 0x2000, so no host is needed; they are streamed straight
 * from flash to the panel (no RAM buffer):
 *     0x2000   "PGS1" (0x31534750 as a little-endian word), uint32 page count (1..64), 8 bytes padding
 *     0x2010   page 0: 4000-byte black/white plane then 4000-byte red plane, 250 lines of 16 bytes (see scripts/eink_draw.py)
 *     0x2010 + 8000 * n   page n
 * If the header is missing the LED blinks red (dimmed) forever.
 *
 * LED (common-anode RGB behind PD00 enable) is dimmed to 10 % by software PWM on PD00: dim white while a page is drawing,
 * dim green at boot, dim blue as the long-press acknowledgement. Set LED_ACTIVITY to 0 for a completely dark badge.
 *
 * Hardware facts (docs/hardware.md): PD00 = LED enable, PB02/PB00/PB04 = R/G/B (active high), PB03 = button (internal pull-up),
 * e-paper: PC00 = SDA, PC01 = SCK, PC02 = CS, PC03 = D/C, PC04 = RES, PA08 = BUSY (low = busy), PC06 = power path (LOW).
 * Core clock after reset: ~19 MHz HFRCO. Idle current of the polling loop is not measured; a deep-sleep wake is future work.
 *
 * Built by scripts/build_fw.py (no linker): position independent, no global data, no const arrays.
 */
#include <stdint.h>

#define REG(a)  (*(volatile uint32_t *)(a))

#define CPU_HZ          19000000u
#define US(n)           ((n) * (CPU_HZ / 1000000u))
#define MS(n)           (US(n) * 1000u)

#define LONG_PRESS_MS   1000u
#define DEBOUNCE_MS     30u
#define LED_ACTIVITY    1

#define PAGES_BASE      0x00002000u
#define PAGES_MAGIC     0x31534750u        /* "PGS1" */
#define PAGES_MAX       64u
#define PAGE_BYTES      8000u
#define PLANE_BYTES     4000u

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

#define P_SDA   (1u << 0)
#define P_SCK   (1u << 1)
#define P_CS    (1u << 2)
#define P_DC    (1u << 3)
#define P_RES   (1u << 4)

#define BTN()           (!((DIN(PB) >> 3) & 1u))             /* PB03: low = pressed */
#define EPD_BUSY_HIGH() ((DIN(PA) >> 8) & 1u)               /* PA08: high = idle */

enum { LED_RED = 1, LED_GREEN = 2, LED_BLUE = 4, LED_WHITE = 7 };

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
#if LED_ACTIVITY
    uint32_t out = DOUT(PB) & ~0x15u;
    if (colour & LED_RED)   out |= 1u << 2;
    if (colour & LED_GREEN) out |= 1u << 0;
    if (colour & LED_BLUE)  out |= 1u << 4;
    DOUT(PB) = out;                          /* bit 3 (the button's pull-up) is left alone */
    if (!colour) DOUT(PD) &= ~1u;            /* PD00 = LED supply enable */
#else
    (void)colour;
#endif
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

static void epd_plane(uint32_t cmd, const volatile uint8_t *p)
{
    epd_cmd(cmd);
    epd_begin(P_DC);
    for (uint32_t i = 0; i < PLANE_BYTES; i++) { epd_byte(p[i], P_DC); led_tick(); }
    epd_end();
}

static void epd_show(const volatile uint8_t *page)     /* page: 4000-byte black/white plane then 4000-byte red plane */
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
    epd_plane(0x10, page);                                                                            /* black/white plane */
    epd_plane(0x13, page + PLANE_BYTES);                                                              /* red plane */
    epd_cmd(0x12);                                                                                    /* refresh (~22 s, BUSY low) */
    delay_cycles(MS(200));
    epd_wait_idle(60000);
    epd_cmd(0x02);                                                                                    /* power off */
    epd_wait_idle(2000);
}

/* ------------------------------------------------------------------ pages */

static uint32_t page_count(void)
{
    if (REG(PAGES_BASE) != PAGES_MAGIC) return 0;
    uint32_t n = REG(PAGES_BASE + 4u);
    return (n >= 1u && n <= PAGES_MAX) ? n : 0;
}

static void draw_page(uint32_t n)
{
    led(LED_WHITE);
    epd_show((const volatile uint8_t *)(PAGES_BASE + 16u + n * PAGE_BYTES));
    led(0);
}

static void wait_release(void)                      /* wait for the button to be released, then let the contacts settle */
{
    while (BTN()) { }
    delay_cycles(MS(50));
}

/* ------------------------------------------------------------------- main */

void reset(void)
{
    REG(CMU_CLKEN0) |= 1u << 26;                                    /* GPIO clock */
    DEMCR |= 1u << 24;                                              /* enable the DWT cycle counter */
    DWT_CTRL |= 1u;

    /* LED: PD00 enable + PB00/PB02/PB04 outputs (low); button PB03 input with pull-up (DOUT bit 3 = 1) */
    gpio_mode(PD, 0, 4);
    DOUT(PD) &= ~1u;
    DOUT(PB) = (DOUT(PB) & ~0x1Fu) | (1u << 3);
    gpio_mode(PB, 0, 4); gpio_mode(PB, 2, 4); gpio_mode(PB, 4, 4);
    gpio_mode(PB, 3, 2);

    /* e-paper: PC00-PC04 outputs idle (RES, CS, DC high), PC06 low = display power path on, PA08 busy input with pull-down */
    DOUT(PC) = P_RES | P_CS | P_DC;
    for (uint32_t p = 0; p < 5; p++) gpio_mode(PC, p, 4);
    gpio_mode(PC, 6, 4);
    DOUT(PA) &= ~(1u << 8);
    gpio_mode(PA, 8, 2);

    uint32_t n = page_count();
    if (n == 0) {                                                   /* no pages flashed: blink red forever */
        for (;;) { led(LED_RED); delay_cycles(MS(300)); led(0); delay_cycles(MS(700)); }
    }

    led(LED_GREEN);
    delay_cycles(MS(300));
    led(0);

    uint32_t page = 0;
    draw_page(page);
    wait_release();

    for (;;) {
        if (!BTN()) continue;
        delay_cycles(MS(DEBOUNCE_MS));
        if (!BTN()) continue;                                       /* a bounce, not a press */

        uint32_t t0 = CYCCNT, long_press = 0;
        while (BTN()) {
            if ((int32_t)(CYCCNT - t0 - MS(LONG_PRESS_MS)) >= 0) { long_press = 1; break; }
        }

        if (long_press) {
            led(LED_BLUE); delay_cycles(MS(150)); led(0);           /* acknowledge, then rewind */
            if (page != 0) { page = 0; draw_page(page); }
        } else if (n > 1) {
            page = (page + 1u >= n) ? 0u : page + 1u;
            draw_page(page);
        }
        wait_release();
    }
}
