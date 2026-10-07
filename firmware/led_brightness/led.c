/* LED brightness test for the SES-imagotag HRD3-0210-A (ContRD010A, EFR32FG22).
 *
 * The RGB LED is common-anode behind a supply switch: PD00 high = LED supply on, PB02/PB00/PB04 = R/G/B (active high).
 * Dimming = software PWM on PD00 (all three colours together), ~1.16 kHz (period 2^14 cycles at ~19 MHz).
 *
 * Shows GREEN at 100 %, 60 %, 40 %, 25 %, 10 % duty, 3 s each, with 0.5 s dark between levels and 1.5 s dark before the sequence repeats.
 *
 * Built by scripts/build_fw.py (no linker): position independent, no global data, no const arrays.
 */
#include <stdint.h>

#define REG(a)  (*(volatile uint32_t *)(a))
#define CPU_HZ  19000000u
#define MS(n)   ((n) * (CPU_HZ / 1000u))

#define CMU_CLKEN0  0x40008064u
#define GPIO        0x4003C000u
#define PORT(p)     (GPIO + 0x30u * (p))
#define MODEL(p)    REG(PORT(p) + 0x04u)
#define DOUT(p)     REG(PORT(p) + 0x10u)
#define PB 1u
#define PD 3u
#define DEMCR       REG(0xE000EDFCu)
#define DWT_CTRL    REG(0xE0001000u)
#define CYCCNT      REG(0xE0001004u)

#define PERIOD  16384u            /* PWM period in cycles; the phase is CYCCNT & (PERIOD - 1) */

static void gpio_out(uint32_t port, uint32_t pin)
{
    uint32_t sh = 4u * pin;
    MODEL(port) = (MODEL(port) & ~(0xFu << sh)) | (4u << sh);
}

static void wait_until(uint32_t t) { while ((int32_t)(CYCCNT - t) < 0) { } }

/* Hold the LED for `cycles`, on for `duty` of every PERIOD cycles (duty >= PERIOD = fully on, 0 = off). */
static void pwm_hold(uint32_t duty, uint32_t cycles)
{
    uint32_t end = CYCCNT + cycles;
    while ((int32_t)(CYCCNT - end) < 0) {
        if ((CYCCNT & (PERIOD - 1u)) < duty) DOUT(PD) |= 1u; else DOUT(PD) &= ~1u;
    }
    DOUT(PD) &= ~1u;
}

#define PCT(n)  ((PERIOD * (n)) / 100u)

static void level(uint32_t duty)
{
    pwm_hold(duty, MS(3000));
    wait_until(CYCCNT + MS(500));
}

void reset(void)
{
    REG(CMU_CLKEN0) |= 1u << 26;                 /* GPIO clock */
    DEMCR |= 1u << 24;                           /* DWT cycle counter */
    DWT_CTRL |= 1u;

    gpio_out(PD, 0);
    DOUT(PD) &= ~1u;
    DOUT(PB) &= ~0x15u;
    gpio_out(PB, 0); gpio_out(PB, 2); gpio_out(PB, 4);
    DOUT(PB) |= 1u << 0;                         /* PB00 = green, held on; PD00 gates it */

    for (;;) {
        level(PERIOD);          /* 100 % */
        level(PCT(60));
        level(PCT(40));
        level(PCT(25));
        level(PCT(10));
        wait_until(CYCCNT + MS(1000));
    }
}
