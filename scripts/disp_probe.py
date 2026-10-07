# SPDX-License-Identifier: GPL-2.0-or-later
"""Probe the six MCU pins that reach the e-ink panel: PC00-PC04 (MCU pins 1-5) and PA08 (pin 29).

usage: disp_probe.py spiscan [CMD]  try all 24 CS/DC/SCK/SDA assignments on PC00-PC03 (RES=PC04, BUSY=PA08) and send CMD (default 0x04)
       disp_probe.py busytest       check PA08 (BUSY?) against PC04 (RES?): level, release, pulse, and long watch
       disp_probe.py resetscan      pulse each pin low as a candidate RES and watch the others for BUSY activity
       disp_probe.py powerscan      drive each other GPIO high in turn and see whether any display line starts following its pull (finds a display power gate)
       disp_probe.py drive          drive each pin push-pull high then low and read it back (can the line move?)
       disp_probe.py pulls          read each pin as an input with pull-up and with pull-down; a pin whose value ignores the pull is driven by the panel (BUSY)
Registers: GPIO_S 0x4003C000, port stride 0x30 (A=0, C=2), MODEL +4 (pins 0-7), MODEH +0xC (pins 8-15), DOUT +0x10, DIN +0x14. MODE 2 = input with pull (DOUT bit picks up/down).
Run with the core halted or the demo firmware running; this does not touch PB/PD pins.
"""
import sys, time
from pyocd.core.helpers import ConnectHelper

G = 0x4003C000
PINS = [("PC00", 2, 0, 1), ("PC01", 2, 1, 2), ("PC02", 2, 2, 3), ("PC03", 2, 3, 4), ("PC04", 2, 4, 5), ("PA08", 0, 8, 29)]

def connect():
    for i in range(20):
        try:
            s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
                "target_override": "cortex_m", "connect_mode": "attach", "frequency": 1000000, "resume_on_disconnect": False})
            s.open(); return s
        except Exception: time.sleep(0.2)
    sys.exit("no connect")

class Gpio:
    def __init__(self, t): self.t = t; t.write32(0x40008064, t.read32(0x40008064) | (1 << 26))
    def mode(self, port, pin, m):
        a = G + 0x30 * port + (0x04 if pin < 8 else 0x0C); sh = 4 * (pin % 8)
        self.t.write32(a, (self.t.read32(a) & ~(0xF << sh)) | (m << sh))
    def out(self, port, pin, v):
        a = G + 0x30 * port + 0x10; d = self.t.read32(a)
        self.t.write32(a, (d | (1 << pin)) if v else (d & ~(1 << pin)))
    def inp(self, port, pin): return (self.t.read32(G + 0x30 * port + 0x14) >> pin) & 1

def main():
    s = connect(); g = Gpio(s.target)
    if sys.argv[1] == "pulls":
        print("pin   MCU pin  pull-up  pull-down")
        for name, port, pin, mcu in PINS:
            res = []
            for up in (1, 0):
                g.out(port, pin, up); g.mode(port, pin, 2); time.sleep(0.05)
                res.append(g.inp(port, pin))
            g.mode(port, pin, 0)
            print(f"{name}  {mcu:>6}   {res[0]:>5}    {res[1]:>5}    {'<-- driven by something (BUSY?)' if res[0] == res[1] else ''}")
    elif sys.argv[1] == "resetscan":
        print("pulse each pin LOW (10 ms) as a candidate RES; the other five are watched with pull-downs. 3 repeats each; events = (pin, rise_ms, fall_ms)")
        T = s.target
        for rname, rport, rpin, rmcu in PINS:
            for rep in range(3):
                for name, port, pin, mcu in PINS:
                    if name == rname: g.out(port, pin, 1); g.mode(port, pin, 4)
                    else: g.out(port, pin, 0); g.mode(port, pin, 2)
                time.sleep(0.1)
                g.out(rport, rpin, 0); time.sleep(0.01); g.out(rport, rpin, 1)
                t0 = time.time(); last = {}; ev = {}
                while time.time() - t0 < 0.25:
                    c = T.read32(G + 0x30 * 2 + 0x14); a = T.read32(G + 0x14); now = round((time.time() - t0) * 1000)
                    for name, port, pin, mcu in PINS:
                        if name == rname: continue
                        v = ((c if port == 2 else a) >> pin) & 1
                        if v != last.get(name, 0):
                            ev.setdefault(name, []).append((now, v)); last[name] = v
                for name, port, pin, mcu in PINS: g.mode(port, pin, 0)
                print(f"  RES={rname} #{rep}: {ev if ev else 'no response'}")
    elif sys.argv[1] == "busytest":
        # Is PA08 (pin 29) really BUSY and PC04 (pin 5) RES?  Watch PA08 while PC04 is held low, released, pulsed, and for a long time afterwards.
        T = s.target
        g.out(0, 8, 0); g.mode(0, 8, 2)                      # PA08 input, pull-down
        g.out(2, 4, 1); g.mode(2, 4, 4); time.sleep(0.5)
        def rd(): return (T.read32(G + 0x14) >> 8) & 1
        print("PC04 high (idle):          PA08 =", rd())
        g.out(2, 4, 0); time.sleep(0.2); print("PC04 held LOW 200 ms:      PA08 =", rd())
        g.out(2, 4, 1); t0 = time.time(); ev = []
        while time.time() - t0 < 12:
            v = rd()
            if not ev or v != ev[-1][1]: ev.append((round(time.time() - t0, 3), v))
            time.sleep(0.01)
        print("after releasing RES, PA08 over 12 s (time_s, level):", ev)
        g.out(2, 4, 0); time.sleep(0.01); g.out(2, 4, 1); t0 = time.time(); ev = []
        while time.time() - t0 < 12:
            v = rd()
            if not ev or v != ev[-1][1]: ev.append((round(time.time() - t0, 3), v))
            time.sleep(0.01)
        print("after a 10 ms RES pulse, PA08 over 12 s:", ev)
        g.mode(2, 4, 0); g.mode(0, 8, 0)
    elif sys.argv[1] == "spiscan":
        # PC04 = RES, PA08 = BUSY (active low). Try all 24 assignments of {CS, DC, SCK, SDA} to PC00..PC03 and send 0x04 (UC81xx power on).
        import itertools
        T = s.target; DO = G + 0x30 * 2 + 0x10; DIN_A = G + 0x14
        cmd = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x04
        for pin in range(5): g.out(2, pin, 1 if pin == 4 else 0); g.mode(2, pin, 4)
        g.out(0, 8, 0); g.mode(0, 8, 2)
        busy = lambda: (T.read32(DIN_A) >> 8) & 1
        hits = []
        for perm in itertools.permutations(range(4)):
            cs, dc, sck, sda = (1 << perm[0]), (1 << perm[1]), (1 << perm[2]), (1 << perm[3])
            RES = 1 << 4
            T.write32(DO, RES | cs | dc); time.sleep(0.02)
            T.write32(DO, cs | dc); time.sleep(0.012); T.write32(DO, RES | cs | dc); time.sleep(0.1)
            idle_busy = busy()
            T.write32(DO, RES | dc)                                   # CS low
            T.write32(DO, RES)                                        # DC low = command
            for i in range(8):
                b = sda if (cmd >> (7 - i)) & 1 else 0
                T.write32(DO, RES | b); T.write32(DO, RES | b | sck); T.write32(DO, RES | b)
            T.write32(DO, RES | cs | dc)                              # CS high, DC high
            t0 = time.time(); low_ms = None; first = None
            while time.time() - t0 < 0.4:
                if not busy():
                    if first is None: first = round((time.time() - t0) * 1000)
                    low_ms = round((time.time() - t0) * 1000)
            tag = "  <<<<< BUSY went low" if first is not None else ""
            print(f"  CS=PC0{perm[0]} DC=PC0{perm[1]} SCK=PC0{perm[2]} SDA=PC0{perm[3]}  busy-before={idle_busy} low@{first}..{low_ms} ms{tag}")
            if first is not None: hits.append(perm)
        for pin in range(5): g.mode(2, pin, 0)
        g.mode(0, 8, 0)
        print("hits:", hits)
    elif sys.argv[1] == "powerscan":
        cand = [("PA00", 0, 0), ("PA03", 0, 3), ("PA04", 0, 4), ("PA05", 0, 5), ("PA06", 0, 6), ("PA07", 0, 7),
                ("PB01", 1, 1), ("PC05", 2, 5), ("PC06", 2, 6), ("PC07", 2, 7), ("PD01", 3, 1), ("PD02", 3, 2), ("PD03", 3, 3)]
        print("candidate driven HIGH -> display lines reading 1 with pull-up (expect none while unpowered)")
        for cname, cport, cpin in cand:
            g.out(cport, cpin, 1); g.mode(cport, cpin, 4); time.sleep(0.05)
            ones = []
            for name, port, pin, mcu in PINS:
                g.out(port, pin, 1); g.mode(port, pin, 2); time.sleep(0.02)
                if g.inp(port, pin): ones.append(name)
                g.mode(port, pin, 0)
            g.mode(cport, cpin, 0); g.out(cport, cpin, 0)
            print(f"  {cname}: {ones if ones else '-'}")
    elif sys.argv[1] == "drive":
        print("pin   MCU pin  drive high -> reads   drive low -> reads")
        for name, port, pin, mcu in PINS:
            r = []
            for v in (1, 0):
                g.out(port, pin, v); g.mode(port, pin, 4); time.sleep(0.02); r.append(g.inp(port, pin))
            g.mode(port, pin, 0)
            print(f"{name}  {mcu:>6}         {r[0]}                  {r[1]}")
    s.close()

main()
