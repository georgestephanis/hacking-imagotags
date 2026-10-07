"""Hold the RGB LED pins in a given state by reconnecting and rewriting continuously.

The chip browns out ~0.1 s after every debugger connection (see docs/research-log.md), so a single write is wiped almost at once.
This loops: connect, then rewrite PB00/PB02/PB04 as fast as the link allows until it drops, then reconnect.
usage: led_burst.py SECONDS STATE        STATE: all (all three low) | r | g | b | off (all high) | hiz (all three disabled / high-impedance)    (LED is common-anode: LOW = lit)
Mapping (unverified on chip): red = PB02, green = PB00, blue = PB04.
"""
import sys, time
from pyocd.core.helpers import ConnectHelper

CMU_CLKEN0 = 0x40008064
GPIO_PB = 0x4003C030
PB_MODEL, PB_DOUT = GPIO_PB + 4, GPIO_PB + 0x10
PIN = {"r": 2, "g": 0, "b": 4}
MASK = (1 << 0) | (1 << 2) | (1 << 4)

def dout_for(state):
    if state in ("all", "hiz"): return 0
    if state == "off": return MASK
    return MASK & ~(1 << PIN[state])

def main():
    secs, state = float(sys.argv[1]), sys.argv[2]
    want = dout_for(state); end = time.time() + secs; writes = connects = 0
    while time.time() < end:
        try:
            s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
                "target_override": "cortex_m", "connect_mode": "attach", "frequency": 20000, "resume_on_disconnect": False})
            s.open(); t = s.target; connects += 1
            t.write32(CMU_CLKEN0, t.read32(CMU_CLKEN0) | (1 << 26))
            model = t.read32(PB_MODEL)
            mode = 0 if state == "hiz" else 4   # 0 = DISABLED (hi-Z), 4 = push-pull
            for p in (0, 2, 4): model = (model & ~(0xF << (4 * p))) | (mode << (4 * p))
            t.write32(PB_MODEL, model)
            while time.time() < end:
                t.write32(PB_DOUT, want); writes += 1
        except Exception:
            pass
        finally:
            try: s.close()
            except Exception: pass
    print(f"{state}: {connects} connects, {writes} writes in {secs:.0f}s")

main()
