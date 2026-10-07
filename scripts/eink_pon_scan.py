#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Find what makes the panel's power-on command (UC81xx 0x04) complete: scan candidate power-enable pins/levels and power-register settings.

For every combination: reset the panel, send PWR (0x01) then PON (0x04), wait up to 3 s for BUSY (PA08, active low) to return high.
Roles found earlier: RES = PC04, BUSY = PA08, SCK = PC01, SDA = PC00, CS/DC = PC02/PC03 (--cs/--dc).
usage: eink_pon_scan.py [--cs 2] [--dc 3]
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyocd.core.helpers import ConnectHelper
from swdburst import burst

G = 0x4003C000
DO_C, DIN_A = G + 0x30 * 2 + 0x10, G + 0x14
ap = argparse.ArgumentParser(); ap.add_argument("--cs", type=int, default=2); ap.add_argument("--dc", type=int, default=3); a = ap.parse_args()
for i in range(20):
    try:
        s = ConnectHelper.session_with_chosen_probe(blocking=False, options={"target_override": "cortex_m", "connect_mode": "attach", "frequency": 1000000, "resume_on_disconnect": False}); s.open(); break
    except Exception: time.sleep(0.2)
else: sys.exit("no connect")
T = s.target
T.write32(0xE000EDF0, 0xA05F0003)
T.write32(0x40008064, T.read32(0x40008064) | (1 << 26))

def setmode(port, pin, m):
    ad = G + 0x30 * port + (0x04 if pin < 8 else 0x0C); sh = 4 * (pin % 8)
    T.write32(ad, (T.read32(ad) & ~(0xF << sh)) | (m << sh))

SDA, SCK, RES = 1, 2, 16
CS, DC = 1 << a.cs, 1 << a.dc
busy_high = lambda: (T.read32(DIN_A) >> 8) & 1
setmode(0, 8, 2); T.write32(G + 0x10, T.read32(G + 0x10) & ~(1 << 8))

def xfer(data, is_cmd, pw):
    base = RES | (0 if is_cmd else DC); vals = [pw | RES | CS | DC, pw | base]
    for byte in data:
        for i in range(8):
            b = SDA if (byte >> (7 - i)) & 1 else 0; vals += [pw | base | b, pw | base | b | SCK]
    return vals + [pw | base, pw | RES | CS | DC]

def trial(pin, level, pwr_bytes):
    for p in (5, 6, 7): setmode(2, p, 0)
    for p in range(5): setmode(2, p, 4)
    pw = 0
    if pin is not None:
        pw = (1 << pin) if level else 0
        T.write32(DO_C, pw | RES | CS | DC); setmode(2, pin, 4)
    T.write32(DO_C, pw | CS | DC); time.sleep(0.02); T.write32(DO_C, pw | RES | CS | DC); time.sleep(0.3)
    idle = busy_high()
    burst(T, DO_C, xfer([0x01], True, pw) + xfer(pwr_bytes, False, pw))
    burst(T, DO_C, xfer([0x04], True, pw))
    t0 = time.time(); went_low = False
    while time.time() - t0 < 3:
        if not busy_high(): went_low = True
        elif went_low: return idle, round(time.time() - t0, 2)
        time.sleep(0.005)
    return idle, None

print("power pin/level  PWR bytes                busy-idle  PON finished (s)")
for pin, level in [(None, 0), (6, 1), (6, 0), (5, 1), (5, 0), (7, 1), (7, 0)]:
    for name, pb in [("internal 03 00 2B 2B 03", [0x03, 0x00, 0x2B, 0x2B, 0x03]), ("external 00 00 2B 2B 03", [0x00, 0x00, 0x2B, 0x2B, 0x03])]:
        idle, done = trial(pin, level, pb)
        who = "none" if pin is None else f"PC0{pin}={'high' if level else 'low '}"
        print(f"{who:<16} {name:<24} {idle:^9}  {done if done is not None else 'NEVER (stuck low)'}{'   <<<<<' if done is not None else ''}", flush=True)
for p in range(5, 8): setmode(2, p, 0)
s.close()
