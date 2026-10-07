#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-driven (bit-banged over SWD) UC8151/UC8159-style e-paper test: init, draw a stripe pattern, refresh.

usage: eink_uc81.py [--cs 2] [--dc 3] [--power 6|none] [--power-level 0|1] [--stripe PX] [--w 212] [--h 104] [--pattern frame|stripes|white|black] [--id N] [--red]
Pins (found by experiment, see docs/research-log.md): RES = PC04, BUSY = PA08 (active low: low = busy), SCK = PC01, SDA = PC00,
CS/DC = PC02/PC03 (order not yet known), PC06 = candidate display power enable (user: power comes in via tp-back-40 = MCU pin 7).
The init sequence is the Good Display GDEW0213Z16 (UC8151) one, as a first guess: PWR 0x01, booster 0x06, PON 0x04, panel 0x00, resolution 0x61, 0x50.
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyocd.core.helpers import ConnectHelper
from swdburst import burst

G = 0x4003C000
DO_C, DIN_A = G + 0x30 * 2 + 0x10, G + 0x14

ap = argparse.ArgumentParser()
ap.add_argument("--cs", type=int, default=2); ap.add_argument("--dc", type=int, default=3)
ap.add_argument("--power", default="6"); ap.add_argument("--power-level", type=int, default=1); ap.add_argument("--stripe", type=int, default=8); ap.add_argument("--id", type=int, default=1); ap.add_argument("--w", type=int, default=212); ap.add_argument("--h", type=int, default=104)
ap.add_argument("--pattern", default="stripes"); ap.add_argument("--red", action="store_true")
ap.add_argument("--init", default="z16"); ap.add_argument("--psr", type=lambda v: int(v, 0), default=None, help="panel setting byte for command 0x00 (default 0x0F; Good Display 2.13in BWR uses 0xCF)")
ap.add_argument("--led", action="store_true", help="show progress on the RGB LED: red=reset, yellow=init sent, green=sending data, blue=refreshing, white=done")
a = ap.parse_args()

for i in range(20):
    try:
        s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
            "target_override": "cortex_m", "connect_mode": "attach", "frequency": 1000000, "resume_on_disconnect": False}); s.open(); break
    except Exception: time.sleep(0.2)
else: sys.exit("no connect")
T = s.target
T.write32(0xE000EDF0, 0xA05F0003)      # halt the core so the demo firmware does not fight us
T.write32(0x40008064, T.read32(0x40008064) | (1 << 26))

def setmode(port, pin, m):
    ad = G + 0x30 * port + (0x04 if pin < 8 else 0x0C); sh = 4 * (pin % 8)
    T.write32(ad, (T.read32(ad) & ~(0xF << sh)) | (m << sh))

LED = {"red": 1 << 2, "green": 1 << 0, "blue": 1 << 4}      # PB02 / PB00 / PB04, active high; PD00 = LED supply enable
def led(*colours):
    if not a.led: return
    G_B, G_D = G + 0x30 * 1, G + 0x30 * 3
    T.write32(G_D + 0x10, T.read32(G_D + 0x10) | 1)
    ad = G_D + 0x04; T.write32(ad, (T.read32(ad) & ~0xF) | 4)
    m = T.read32(G_B + 0x04)
    for pin in (0, 2, 4): m = (m & ~(0xF << (4 * pin))) | (4 << (4 * pin))
    T.write32(G_B + 0x04, m)
    v = T.read32(G_B + 0x10) & ~0x15
    for c in colours: v |= LED[c]
    T.write32(G_B + 0x10, v)

SDA, SCK, RES = 1 << 0, 1 << 1, 1 << 4
CS, DC = 1 << a.cs, 1 << a.dc
state = RES | CS | DC          # idle: RES high, CS high, DC high, SCK low, SDA low
T.write32(DO_C, state)
for p in range(5): setmode(2, p, 4)
if a.power != "none":
    pw = int(a.power); T.write32(DO_C, (T.read32(DO_C) | (1 << pw)) if a.power_level else (T.read32(DO_C) & ~(1 << pw))); setmode(2, pw, 4)
    if a.power_level: state |= (1 << pw)
setmode(0, 8, 2); T.write32(G + 0x10, T.read32(G + 0x10) & ~(1 << 8))     # PA08 input pull-down
time.sleep(0.1)
busy_high = lambda: (T.read32(DIN_A) >> 8) & 1       # 1 = idle/ready

PW = state & ~(SDA | SCK | RES | CS | DC)        # extra output bits to keep driven (display power enable)

def xfer(data, is_cmd):
    """Build the DOUT values for one chip-select-low transfer of the given bytes (SPI mode 0, MSB first)."""
    base = RES | (0 if is_cmd else DC)               # CS low; DC low = command
    vals = [PW | RES | CS | DC, PW | base]
    for byte in data:
        for i in range(8):
            b = SDA if (byte >> (7 - i)) & 1 else 0
            vals += [PW | base | b, PW | base | b | SCK]
    vals += [PW | base, PW | RES | CS | DC]
    return vals

def send_all(vals): burst(T, DO_C, vals)

def cmd(c, *data):
    send_all(xfer([c], True) + (xfer(list(data), False) if data else []))

def wait_busy(what, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if busy_high(): return round(time.time() - t0, 2)
        time.sleep(0.02)
    print(f"  !! BUSY still low after {timeout}s ({what})"); return None

led("red"); print("reset", flush=True); T.write32(DO_C, PW | CS | DC); time.sleep(0.02); T.write32(DO_C, PW | RES | CS | DC); time.sleep(0.1)
print("BUSY after reset:", busy_high(), flush=True)
cmd(0x01, 0x03, 0x00, 0x2B, 0x2B, 0x03)
cmd(0x06, 0x17, 0x17, 0x17)
cmd(0x04); print("power on, busy cleared after", wait_busy("PON"), "s")
cmd(0x00, a.psr if a.psr is not None else (0x0F if a.init == "z16" else 0x1F))
cmd(0x61, a.h & 0xFF, (a.w >> 8) & 0xFF, a.w & 0xFF)
cmd(0x50, 0x77)
led("red", "green"); print("init sent (LED yellow)", flush=True)

rowbytes = (a.h + 7) // 8
total = rowbytes * a.w
def black_px(x, y):
    """x = gate line index (0..w-1, the long side), y = source index (0..h-1). Pattern 'frame': border, ticks every 32 px, origin/opposite-corner squares, --id dots."""
    if a.pattern == "frame":
        if x < 3 or x >= a.w - 3 or y < 3 or y >= a.h - 3: return True
        if (y < 12 and x % 32 == 0) or (x < 12 and y % 32 == 0): return True
        if x < 20 and y < 20: return True                              # big square marks the origin
        if x >= a.w - 8 and y >= a.h - 8: return True                  # small square marks the far corner
        cx, cy = a.w // 2, a.h // 2
        for k in range(a.id):                                          # --id dots (4x4 px, 8 px apart): attempt number
            if cx + 8 * k <= x < cx + 8 * k + 4 and cy <= y < cy + 4: return True
        return False
    if a.pattern == "calib":
        # edge calibration: vertical lines near the far end of x with lengths that grow, horizontal lines near the far end of y likewise
        for k, xx in enumerate((236, 240, 242, 244, 245, 246, 247, 248, 249)):
            if x == xx and 8 <= y < 8 + 12 * (k + 1): return True
        for k, yy in enumerate((116, 120, 122, 123, 124, 125, 126, 127)):
            if y == yy and 8 <= x < 8 + 24 * (k + 1): return True
        if x < 3 or y < 3: return True                                  # near edges: origin sides
        cx, cy = a.w // 2, a.h // 2
        for k in range(a.id):
            if cx + 8 * k <= x < cx + 8 * k + 4 and cy <= y < cy + 4: return True
        return False
    if a.pattern == "white": return False
    if a.pattern == "black": return True
    return (x // a.stripe) % 2 == 0

def plane(red):
    out = []
    for x in range(a.w):
        for yb in range(rowbytes):
            if red:
                v = 0xFF
                if a.pattern == "calib":
                    for bit in range(8):
                        y = yb * 8 + bit
                        if 60 <= x < 120 and 40 <= y < 90: v &= ~(0x80 >> bit)          # solid red rectangle (red-plane bit = 0)
                out.append(v); continue
            v = 0
            for bit in range(8):
                y = yb * 8 + bit
                white = not (y < a.h and black_px(x, y))
                if white: v |= 0x80 >> bit
            out.append(v)
    return out
t0 = time.time(); led("green")
cmd(0x10); send_all(xfer(plane(False), False))
cmd(0x13); send_all(xfer(plane(True), False))
print(f"sent {2 * total} bytes in {time.time() - t0:.1f} s; refreshing (watch the panel)", flush=True)
led("blue"); cmd(0x12); time.sleep(0.2)
print("refresh busy cleared after", wait_busy("refresh", 90), "s")
led("red", "green", "blue"); cmd(0x02); print("power off; busy cleared after", wait_busy("POF"), "s")
time.sleep(2); led()
s.close()
