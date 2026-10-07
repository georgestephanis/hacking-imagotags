# SPDX-License-Identifier: GPL-2.0-or-later
"""Drive PB00/PB02/PB04 (MCU pins 20/18/16) from the debugger to find the RGB LED channels.

usage: gpio_poke.py init            enable GPIO clock, set PB0/PB2/PB4 push-pull, all driven LOW
       gpio_poke.py high 0|2|4      drive only that pin HIGH (others low)
       gpio_poke.py low  0|2|4      drive only that pin LOW (others high)  [for an active-low / common-anode LED]
       gpio_poke.py off             all pins low
       gpio_poke.py led r|g|b|off   RGB LED (common anode, active-low): r=PB02, g=PB00, b=PB04. Mapping from the netlist + user tracing,
                                    NOT yet verified on the chip.
Addresses from Silicon Labs simplicity_sdk: efr32fg22c121f512gm40.h (CMU_S 0x40008000, GPIO_S 0x4003C000)
and efr32fg22_gpio_port.h (port stride 0x30; CTRL,MODEL,-,MODEH,DOUT,DIN).
Port B = index 1. GPIO outputs persist after the debug session ends (until reset/power-cycle).
"""
import sys, time
from pyocd.core.helpers import ConnectHelper

CMU_CLKEN0 = 0x40008000 + 0x64
GPIO_PB    = 0x4003C000 + 0x30
PB_MODEL, PB_DOUT = GPIO_PB + 0x04, GPIO_PB + 0x10
PINS = (0, 2, 4)
GPIO_CLK = 1 << 26

def connect():
    for i in range(10):
        try:
            s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
                "target_override": "cortex_m", "connect_mode": "attach", "frequency": 20000})
            s.open(); return s
        except Exception as e:
            print("connect retry", i, str(e)[:60]); time.sleep(0.3)
    sys.exit("could not connect")

def main():
    cmd = sys.argv[1]
    s = connect(); t = s.target
    try:
        t.write32(CMU_CLKEN0, t.read32(CMU_CLKEN0) | GPIO_CLK)
        model = t.read32(PB_MODEL)
        for p in PINS:
            model = (model & ~(0xF << (4 * p))) | (0x4 << (4 * p))   # MODEn = PUSHPULL
        t.write32(PB_MODEL, model)
        mask = sum(1 << p for p in PINS)
        if cmd in ("init", "off"): dout = 0
        elif cmd == "high": dout = 1 << int(sys.argv[2])
        elif cmd == "low":  dout = mask & ~(1 << int(sys.argv[2]))
        elif cmd == "led":
            pin = {"r": 2, "g": 0, "b": 4}.get(sys.argv[2])
            dout = mask if pin is None else mask & ~(1 << pin)   # all high = LED off; selected pin low = colour on
        else: sys.exit("bad command")
        cur = t.read32(PB_DOUT)
        t.write32(PB_DOUT, (cur & ~mask) | dout)
        print("CMU_CLKEN0 =", hex(t.read32(CMU_CLKEN0)), " PB_MODEL =", hex(t.read32(PB_MODEL)),
              " PB_DOUT =", hex(t.read32(PB_DOUT)), " PB_DIN =", hex(t.read32(GPIO_PB + 0x14)))
    finally:
        s.close()

main()
