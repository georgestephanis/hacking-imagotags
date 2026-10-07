#!/usr/bin/env python3
"""Watch every free GPIO as an input and report which pins change while you wiggle something (e.g. the signal spring contact pad-front-123).

usage: gpio_watch.py [SECONDS] [--pull up|down|none]
Skips the SWD pins (PA01/PA02) and PB03 (button is fine to include, it will just show your button presses) -- PB03 is included.
Everything else is configured as an input (default: pull-down) and polled; a transition list per pin is printed at the end, most active first.
Run this with the core halted (done automatically) so firmware does not interfere.
"""
import sys, time
from pyocd.core.helpers import ConnectHelper

G = 0x4003C000
PINS = [("PA00", 0, 0)] + [("PA%02d" % n, 0, n) for n in (3, 4, 5, 6, 7, 8)] + [("PB%02d" % n, 1, n) for n in range(5)] + \
       [("PC%02d" % n, 2, n) for n in range(8)] + [("PD%02d" % n, 3, n) for n in range(4)]
secs = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else 40
pull = "down"
if "--pull" in sys.argv: pull = sys.argv[sys.argv.index("--pull") + 1]

for i in range(20):
    try:
        s = ConnectHelper.session_with_chosen_probe(blocking=False, options={"target_override": "cortex_m", "connect_mode": "attach", "frequency": 1000000, "resume_on_disconnect": False}); s.open(); break
    except Exception: time.sleep(0.2)
else: sys.exit("no connect")
T = s.target
T.write32(0xE000EDF0, 0xA05F0003)
T.write32(0x40008064, T.read32(0x40008064) | (1 << 26))
for name, port, pin in PINS:
    a = G + 0x30 * port + (0x04 if pin < 8 else 0x0C); sh = 4 * (pin % 8)
    do = G + 0x30 * port + 0x10; d = T.read32(do)
    if pull == "up": T.write32(do, d | (1 << pin))
    elif pull == "down": T.write32(do, d & ~(1 << pin))
    T.write32(a, (T.read32(a) & ~(0xF << sh)) | ((2 if pull != "none" else 1) << sh))
time.sleep(0.2)
print(f"watching {len(PINS)} pins for {secs:.0f} s (pull-{pull}); wiggle the contact now...", flush=True)
last = {}; changes = {n: [] for n, _, _ in PINS}
t0 = time.time()
while time.time() - t0 < secs:
    regs = {p: T.read32(G + 0x30 * p + 0x14) for p in range(4)}
    now = time.time() - t0
    for name, port, pin in PINS:
        v = (regs[port] >> pin) & 1
        if name in last and v != last[name]: changes[name].append((round(now, 2), v))
        last[name] = v
print("pin   changes  (time_s, new_level) first few")
for name, ch in sorted(changes.items(), key=lambda kv: -len(kv[1])):
    if ch: print(f"{name}   {len(ch):>5}   {ch[:8]}")
print("quiet pins:", [n for n, ch in changes.items() if not ch])
s.close()
