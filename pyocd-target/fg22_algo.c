/* SPDX-License-Identifier: Apache-2.0 */
/* On-target flash algorithm for the Silicon Labs EFR32FG22 (Series 2 'xG22', Cortex-M33), for pyOCD.
 *
 * pyOCD loads this into RAM, sets r0..r3 to the arguments, runs the entry point and checks r0 (0 = success).
 * Entry points (CMSIS-Pack flash-algorithm conventions):
 *   int Init(uint32_t adr, uint32_t clk, uint32_t fnc);   int UnInit(uint32_t fnc);
 *   int EraseSector(uint32_t adr);                        int ProgramPage(uint32_t adr, uint32_t sz, uint32_t *buf);
 * Must stay position independent: no globals, no calls between functions, no libraries. See pyocd-target/build_algo.py.
 *
 * MSC sequence follows Silicon Labs em_msc.c for Series 2 (WRITEEND variant): LOCK key 0x1B71, WRITECTRL.WREN,
 * ADDRB + ERASEPAGE, ADDRB + WDATA... + WRITEEND, wait until STATUS.BUSY|PENDING == 0 (checked twice).
 * Register addresses from simplicity_sdk efr32fg22*.h: MSC_S 0x40030000, CMU_S 0x40008000.
 */
#include <stdint.h>

#define REG(a) (*(volatile uint32_t *)(a))

#define MSC_BASE        0x40030000u
#define MSC_WRITECTRL   REG(MSC_BASE + 0x0Cu)
#define MSC_WRITECMD    REG(MSC_BASE + 0x10u)
#define MSC_ADDRB       REG(MSC_BASE + 0x14u)
#define MSC_WDATA       REG(MSC_BASE + 0x18u)
#define MSC_STATUS      REG(MSC_BASE + 0x1Cu)
#define MSC_LOCK        REG(MSC_BASE + 0x3Cu)
#define CMU_CLKEN1      REG(0x40008068u)

#define ST_BUSY       0x00000001u
#define ST_LOCKED     0x00000002u
#define ST_INVADDR    0x00000004u
#define ST_WDATAREADY 0x00000008u
#define ST_PENDING    0x00000020u
#define ST_REGLOCK    0x00010000u

#define CMD_ERASEPAGE 0x2u
#define CMD_WRITEEND  0x4u
#define TIMEOUT       0x00400000u     /* loop iterations; generous at the default 19 MHz HFRCO */

/* returns 0 when (STATUS & mask) == value and no lock/invalid-address error; 1 otherwise */
static inline __attribute__((always_inline)) int wait_status(uint32_t mask, uint32_t value)
{
    for (uint32_t n = TIMEOUT; n; n--) {
        uint32_t st = MSC_STATUS;
        if (st & ST_INVADDR) return 1;
        if ((st & mask) == value) return (st & (ST_LOCKED | ST_REGLOCK)) ? 1 : 0;
    }
    return 1;
}

static inline __attribute__((always_inline)) int wait_idle(void)
{
    if (wait_status(ST_BUSY | ST_PENDING, 0)) return 1;
    return wait_status(ST_BUSY | ST_PENDING, 0);        /* em_msc.c checks twice */
}

int Init(uint32_t adr, uint32_t clk, uint32_t fnc)
{
    (void)adr; (void)clk; (void)fnc;
    CMU_CLKEN1 |= 1u << 17;                 /* MSC clock */
    MSC_LOCK = 0x1B71u;                     /* unlock */
    MSC_WRITECTRL |= 1u;                    /* WREN */
    return 0;
}

int UnInit(uint32_t fnc)
{
    (void)fnc;
    MSC_WRITECTRL &= ~1u;
    MSC_LOCK = 0;
    return 0;
}

int EraseSector(uint32_t adr)
{
    MSC_ADDRB = adr;
    MSC_WRITECMD = CMD_ERASEPAGE;
    return wait_idle();
}

int ProgramPage(uint32_t adr, uint32_t sz, uint32_t *buf)
{
    MSC_ADDRB = adr;
    if (MSC_STATUS & ST_INVADDR) return 1;
    uint32_t words = sz >> 2;
    if (!words) return 0;
    MSC_WDATA = *buf++;
    for (uint32_t i = 1; i < words; i++) {
        if (wait_status(ST_WDATAREADY, ST_WDATAREADY)) { MSC_WRITECMD = CMD_WRITEEND; return 1; }
        MSC_WDATA = *buf++;
    }
    MSC_WRITECMD = CMD_WRITEEND;
    return wait_idle();
}
