#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Flash a raw binary into the EFR32FG22's main flash by driving the MSC registers over SWD (no flash algorithm needed).

usage: flash_msc.py IMAGE.bin [--addr 0x0] [--no-reset] [--clock HZ]

This is the host-driven proof of concept; flash/fg22_algo (a real on-target flash algorithm for pyOCD) is the next step.
Sequence (derived from Silicon Labs' em_msc.c, Series 2 'WRITEEND' variant used by the xG22):
  halt the core; CMU_CLKEN1.MSC on; MSC.LOCK = 0x1B71; WRITECTRL.WREN = 1;
  erase each 8 KiB page: ADDRB = page, WRITECMD = ERASEPAGE, wait STATUS.(BUSY|PENDING) == 0 (checked twice);
  program: ADDRB = addr, WDATA = word0, then for each word wait STATUS.WDATAREADY and write WDATA; WRITECMD = WRITEEND; wait idle;
  WREN = 0, LOCK = 0; verify by reading back; optionally SYSRESETREQ so the core boots from flash.
Registers: MSC_S 0x40030000, CMU_S 0x40008000 (CLKEN1 +0x68, MSC = bit 17).
"""
import argparse, struct, sys, time
from pyocd.core.helpers import ConnectHelper

MSC = 0x40030000
WRITECTRL, WRITECMD, ADDRB, WDATA, STATUS, LOCK = (MSC + o for o in (0x0C, 0x10, 0x14, 0x18, 0x1C, 0x3C))
CMU_CLKEN1 = 0x40008068
PAGE = 0x2000
FLASH_SIZE = 0x80000
S_BUSY, S_LOCKED, S_INVADDR, S_WDATAREADY, S_PENDING, S_TIMEOUT, S_REGLOCK = 1, 2, 4, 8, 0x20, 0x40, 0x10000
CMD_ERASEPAGE, CMD_WRITEEND = 2, 4


class MscError(Exception):
    pass


class Flasher:
    def __init__(self, target):
        self.t = target

    def wait(self, mask, value, what, timeout=2.0):
        end = time.time() + timeout
        while True:
            st = self.t.read32(STATUS)
            if st & S_INVADDR:
                raise MscError(f"{what}: invalid address (STATUS={st:#x})")
            if (st & mask) == value:
                if st & (S_LOCKED | S_REGLOCK):
                    raise MscError(f"{what}: MSC or page locked (STATUS={st:#x})")
                return
            if time.time() > end:
                raise MscError(f"{what}: timeout (STATUS={st:#x})")

    def idle(self, what):
        self.wait(S_BUSY | S_PENDING, 0, what)
        self.wait(S_BUSY | S_PENDING, 0, what)      # em_msc.c checks twice

    def begin(self):
        self.t.write32(0xE000EDF0, 0xA05F0003)                          # DHCSR: halt
        self.t.write32(CMU_CLKEN1, self.t.read32(CMU_CLKEN1) | (1 << 17))   # MSC clock
        self.t.write32(LOCK, 0x1B71)
        self.t.write32(WRITECTRL, self.t.read32(WRITECTRL) | 1)             # WREN

    def end(self):
        try:
            self.t.write32(WRITECTRL, self.t.read32(WRITECTRL) & ~1)
            self.t.write32(LOCK, 0)
        except Exception:
            pass

    def erase_page(self, addr):
        self.t.write32(ADDRB, addr)
        self.t.write32(WRITECMD, CMD_ERASEPAGE)
        self.idle(f"erase {addr:#x}")

    def program(self, addr, words):
        """Program words (list of uint32) starting at addr; must not cross a page boundary."""
        assert addr % 4 == 0 and (addr // PAGE) == ((addr + 4 * len(words) - 1) // PAGE)
        self.t.write32(ADDRB, addr)
        if self.t.read32(STATUS) & S_INVADDR:
            raise MscError(f"program {addr:#x}: invalid address")
        self.t.write32(WDATA, words[0])
        for w in words[1:]:
            self.wait(S_WDATAREADY, S_WDATAREADY, f"program {addr:#x}")
            self.t.write32(WDATA, w)
        self.t.write32(WRITECMD, CMD_WRITEEND)
        self.idle(f"program {addr:#x}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--clock", type=int, default=1000000)
    a = ap.parse_args()
    data = open(a.image, "rb").read()
    data += b"\xff" * (-len(data) % 4)
    if a.addr % PAGE and False:
        pass
    if a.addr + len(data) > FLASH_SIZE:
        sys.exit("image does not fit in flash")
    words = list(struct.unpack(f"<{len(data)//4}I", data))

    for i in range(10):
        try:
            s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
                "target_override": "cortex_m", "connect_mode": "attach", "frequency": a.clock, "resume_on_disconnect": False})
            s.open(); break
        except Exception:
            time.sleep(0.3)
    else:
        sys.exit("could not connect to the target")
    t = s.target
    f = Flasher(t)
    try:
        f.begin()
        first, last = a.addr // PAGE, (a.addr + len(data) - 1) // PAGE
        for p in range(first, last + 1):
            f.erase_page(p * PAGE)
        print(f"erased pages {first}..{last} ({(last - first + 1) * PAGE // 1024} KiB)")
        pos = 0
        while pos < len(words):
            addr = a.addr + pos * 4
            n = min(len(words) - pos, (PAGE - addr % PAGE) // 4)
            f.program(addr, words[pos:pos + n])
            pos += n
        print(f"programmed {len(data)} bytes at {a.addr:#x}")
    finally:
        f.end()
    back = t.read_memory_block32(a.addr, len(words))
    bad = [i for i, (x, y) in enumerate(zip(words, back)) if x != y]
    if bad:
        i = bad[0]
        sys.exit(f"VERIFY FAILED at {a.addr + 4*i:#x}: wrote {words[i]:#010x}, read {back[i]:#010x} ({len(bad)} bad words)")
    print("verify OK")
    if not a.no_reset:
        t.write32(0xE000ED0C, 0x05FA0004)       # AIRCR: SYSRESETREQ
        print("reset issued: the core now boots from flash")
    s.close()


main()
