#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the signal path from a serial TX (e.g. the Pico debugprobe's GP4) to the tag's PB01, through the debugger.

usage: signal_test.py PORT [--baud 300] [--bytes 40]
Halts the tag's core, sets PB01 as an input with pull-down, then sends 0x55 bytes at a slow baud rate while polling PB01's input
register over SWD (about 0.3 ms per read, so the baud rate must be slow: 300 baud = 3.3 ms per bit). Reports idle level and the
distribution of high/low durations; at 300 baud a 0x55 stream should show a clean ~3.3 ms alternation.
"""
import argparse, collections, os, sys, threading, time
import serial
from pyocd.core.helpers import ConnectHelper

ap = argparse.ArgumentParser(); ap.add_argument("port"); ap.add_argument("--baud", type=int, default=300); ap.add_argument("--bytes", type=int, default=40)
a = ap.parse_args()
for i in range(20):
    try:
        s = ConnectHelper.session_with_chosen_probe(blocking=False, options={"target_override": "cortex_m", "connect_mode": "attach", "frequency": 1000000, "resume_on_disconnect": False}); s.open(); break
    except Exception: time.sleep(0.2)
else: sys.exit("no connect")
T = s.target
T.write32(0xE000EDF0, 0xA05F0003)                                   # halt so the firmware does not touch anything
T.write32(0x40008064, T.read32(0x40008064) | (1 << 26))
G = 0x4003C000 + 0x30                                               # port B
T.write32(G + 0x10, T.read32(G + 0x10) & ~(1 << 1))                 # DOUT bit 1 = 0 -> pull-down
T.write32(G + 0x04, (T.read32(G + 0x04) & ~(0xF << 4)) | (2 << 4)) # PB01 = input with pull
din = G + 0x14

def read(): return (T.read32(din) >> 1) & 1

ser = serial.Serial(a.port, a.baud, timeout=1, write_timeout=30)    # open first: the bridge may not drive the pin until the port is open
time.sleep(0.5)
print("idle level with the port open, before sending (50 reads):", collections.Counter(read() for _ in range(50)))
stop = threading.Event()
def tx():
    ser.write(b"\x55" * a.bytes); ser.flush(); stop.set()
t0 = time.time(); th = threading.Thread(target=tx); th.start()
samples = []
while not stop.is_set() or time.time() - t0 < 0.3:
    samples.append((time.time() - t0, read()))
    if time.time() - t0 > a.bytes * 10 / a.baud + 1.5: break
th.join(); ser.close()
edges = [(t, v) for (t, v), (_, pv) in zip(samples[1:], samples[:-1]) if v != pv]
print(f"{len(samples)} samples ({len(samples)/(samples[-1][0]):.0f} reads/s), {len(edges)} transitions")
if len(edges) > 2:
    durs = [round((edges[i + 1][0] - edges[i][0]) * 1000) for i in range(len(edges) - 1)]
    print("first transitions (ms, new level):", [(round(t * 1000), v) for t, v in edges[:10]])
    print("duration histogram (ms: count), expect ~%.1f ms at %d baud:" % (1000.0 / a.baud, a.baud), dict(sorted(collections.Counter(durs).items())[:12]))
else:
    print("no activity seen on PB01")
s.close()
