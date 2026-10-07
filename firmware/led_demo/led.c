/* Minimal bare-metal demo for the SES-imagotag HRD3-0210-A (EFR32FG22C121F512GM40).
 *
 * Cycles the RGB LED through red -> green -> blue -> off each time the push button (PB03, active-low) is pressed.
 * Pin map (confirmed on hardware, docs/log.md):
 *   PD00 high = LED supply enable; PB02 = red, PB00 = green, PB04 = blue (all active-high); PB03 = button to ground.
 * No libraries, no startup file, no calls, no globals: the build (scripts/build_fw.py) places a vector table in front of this code,
 * so everything must stay position independent. Register addresses are from Silicon Labs simplicity_sdk headers.
 */
#include <stdint.h>

#define REG(a)  (*(volatile uint32_t *)(a))

#define CMU_CLKEN0   0x40008064u
#define GPIO         0x4003C000u
#define PORT(p)      (GPIO + 0x30u * (p))
#define MODEL(p)     REG(PORT(p) + 0x04u)
#define DOUT(p)      REG(PORT(p) + 0x10u)
#define DIN(p)       REG(PORT(p) + 0x14u)
#define PORT_B 1u
#define PORT_D 3u

static inline void delay(volatile uint32_t n) { while (n--) { __asm__ volatile(""); } }

void __attribute__((noreturn)) reset(void)
{
    REG(CMU_CLKEN0) |= 1u << 26;                                   /* GPIO clock */

    /* PD00 push-pull (mode 4), driven high: LED supply on */
    MODEL(PORT_D) = (MODEL(PORT_D) & ~0xFu) | 0x4u;
    DOUT(PORT_D) |= 1u;

    /* PB00/PB02/PB04 push-pull outputs (mode 4), initially low; PB03 input with pull-up (mode 2, DOUT=1) */
    uint32_t m = MODEL(PORT_B);
    m &= ~((0xFu << 0) | (0xFu << 8) | (0xFu << 16) | (0xFu << 12));
    m |= (0x4u << 0) | (0x4u << 8) | (0x4u << 16) | (0x2u << 12);
    MODEL(PORT_B) = m;
    DOUT(PORT_B) = (DOUT(PORT_B) & ~0x15u) | (1u << 3);

    delay(500000);               /* let the pull-up settle: without this the pin reads low at startup and counts as a press */

    uint32_t state = 0;          /* 0 red (PB02), 1 green (PB00), 2 blue (PB04), 3 off */

    for (;;) {
        /* show the current colour: drive only its pin high, others low (low also discharges the transistor gate) */
        uint32_t out = DOUT(PORT_B) & ~0x15u;
        if      (state == 0) out |= 1u << 2;   /* red   */
        else if (state == 1) out |= 1u << 0;   /* green */
        else if (state == 2) out |= 1u << 4;   /* blue  */
        DOUT(PORT_B) = out;

        while (DIN(PORT_B) & (1u << 3)) { }      /* wait for press (low) */
        delay(200000);                           /* debounce */
        while (!(DIN(PORT_B) & (1u << 3))) { }   /* wait for release */
        delay(200000);
        state = (state + 1u) & 3u;
    }
}
