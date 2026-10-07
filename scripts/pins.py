# SPDX-License-Identifier: GPL-2.0-or-later
"""usage: pins.py SECONDS PB02=1 PD00=1 ...  Drive the listed pins (push-pull) to the given levels, hold, then release them (disabled).

RGB LED (confirmed 2026-10-05): PD00 high = LED anode supply enabled; PB02 high = red, PB00 high = green, PB04 high = blue.
e.g.  pins.py 8 PD00=1 PB02=1        bright red for 8 s
After a colour pin is released its gate stays charged (LED stays dim-on); drive PB00/PB02/PB04/PD00 low for ~2 s to clear:
      pins.py 3 PB00=0 PB02=0 PB04=0 PD00=0
Ports: A B C D; pin number follows (PB02 = port B pin 2). Registers: GPIO_S 0x4003C000, port stride 0x30, MODEL +4, MODEH +0xC, DOUT +0x10.
"""
import sys, time
from pyocd.core.helpers import ConnectHelper
secs = float(sys.argv[1]); spec = []
for a in sys.argv[2:]:
    name, lvl = a.split("="); spec.append(("ABCD".index(name[1]), int(name[2:]), int(lvl), name))
for i in range(20):
    try:
        s = ConnectHelper.session_with_chosen_probe(blocking=False, options={"target_override":"cortex_m","connect_mode":"attach","frequency":200000,"resume_on_disconnect":False}); s.open(); break
    except Exception: time.sleep(.2)
t = s.target
t.write32(0xE000EDF0, 0xA05F0003)   # halt the core so running firmware doesn't fight the test
t.write32(0x40008064, t.read32(0x40008064) | (1 << 26))
G = 0x4003C000
def setmode(port, pin, m):
    a = G + 0x30*port + (0x04 if pin < 8 else 0x0C); sh = 4*(pin % 8)
    t.write32(a, (t.read32(a) & ~(0xF << sh)) | (m << sh))
def dout(port): return G + 0x30*port + 0x10
for port, pin, lvl, name in spec:
    d = t.read32(dout(port)); t.write32(dout(port), (d | (1 << pin)) if lvl else (d & ~(1 << pin))); setmode(port, pin, 4)
print("driving", " ".join(a for a in sys.argv[2:]), time.strftime("%T"), flush=True)
time.sleep(secs)
for port, pin, lvl, name in spec: setmode(port, pin, 0)
chk = [hex(t.read32(G + 0x30*p + 4)) for p in sorted({x[0] for x in spec})]
print("released", time.strftime("%T"), "MODEL regs", chk)
s.close()
