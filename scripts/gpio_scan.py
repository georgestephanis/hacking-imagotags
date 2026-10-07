# SPDX-License-Identifier: GPL-2.0-or-later
"""Scan GPIOs one at a time (high 3 s, low/off 1 s) to find what lights the RGB LED.

usage: gpio_scan.py high|low
  high: drive each pin high (others disabled)
  low : drive each pin low while all scanned pins are driven high
Skips PA01/PA02 (SWD). Register map: see gpio_poke.py. Port stride 0x30; MODEL pins 0-7, MODEH pins 8-15.
"""
import sys, time
from pyocd.core.helpers import ConnectHelper

CMU_CLKEN0 = 0x40008000 + 0x64
GPIO = 0x4003C000
PINS = [("PA", 0, 0), ("PA", 0, 3), ("PA", 0, 4), ("PA", 0, 5), ("PA", 0, 6), ("PA", 0, 7), ("PA", 0, 8),
        ("PB", 1, 0), ("PB", 1, 1), ("PB", 1, 2), ("PB", 1, 3), ("PB", 1, 4)] + \
       [("PC", 2, n) for n in range(8)] + [("PD", 3, n) for n in range(4)]

def reg(port, off): return GPIO + 0x30 * port + off

class Tgt:
    """pyOCD target wrapper that reconnects and retries when the flaky SWD link drops."""
    def __init__(self): self.s = None; self.open()
    def open(self):
        if self.s is not None:
            try: self.s.close()
            except Exception: pass
            self.s = None
        for i in range(20):
            try:
                self.s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
                    "target_override": "cortex_m", "connect_mode": "attach", "frequency": 20000,
                    "resume_on_disconnect": False}); self.s.open()
                self.s.target.write32(0xE000EDF0, 0xA05F0003)   # DHCSR: DBGKEY | C_HALT | C_DEBUGEN; a halted core cannot lock up/reset
                return
            except Exception: self.s = None; time.sleep(0.3)
        sys.exit("no connect")
    def _do(self, fn, *a):
        for i in range(8):
            try: return fn(self.s.target, *a)
            except Exception: self.open()
        sys.exit("link lost")
    def read32(self, a): return self._do(lambda t, a: t.read32(a), a)
    def write32(self, a, v): return self._do(lambda t, a, v: t.write32(a, v), a, v)

def set_mode(t, port, pin, mode):
    a = reg(port, 0x04 if pin < 8 else 0x0C); sh = 4 * (pin % 8)
    t.write32(a, (t.read32(a) & ~(0xF << sh)) | (mode << sh))

def main():
    pol = sys.argv[1]
    t = Tgt()
    t.write32(CMU_CLKEN0, t.read32(CMU_CLKEN0) | (1 << 26))
    if pol == "low":
        for name, port, pin in PINS:
            set_mode(t, port, pin, 4); a = reg(port, 0x10); t.write32(a, t.read32(a) | (1 << pin))
    for n, (name, port, pin) in enumerate(PINS, 1):
        label = f"{name}{pin:02d}"; a = reg(port, 0x10)
        set_mode(t, port, pin, 4)
        if pol == "high": t.write32(a, t.read32(a) | (1 << pin))
        else: t.write32(a, t.read32(a) & ~(1 << pin))
        print(f"#{n:2d} {label} {pol.upper()} {time.strftime('%T')}", flush=True); time.sleep(3)
        if pol == "high": t.write32(a, t.read32(a) & ~(1 << pin)); set_mode(t, port, pin, 0)
        else: t.write32(a, t.read32(a) | (1 << pin))
        time.sleep(1)
    for name, port, pin in PINS: set_mode(t, port, pin, 0)
    t.s.close(); print("scan done")

main()
