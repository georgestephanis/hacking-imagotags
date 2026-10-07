"""Watch PB03 (MCU pin 17) as an input with pull-up and log transitions, to test the 'button to ground' hypothesis.
usage: button_watch.py [SECONDS]   (default 40)
Registers: PB MODEL +0x34 (MODE3 = bits 15:12, INPUTPULL = 2), DOUT bit 3 = 1 selects pull-up, DIN +0x44."""
import sys, time
from pyocd.core.helpers import ConnectHelper

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 40
for i in range(20):
    try:
        s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
            "target_override": "cortex_m", "connect_mode": "attach", "frequency": 20000, "resume_on_disconnect": False})
        s.open(); break
    except Exception: time.sleep(0.2)
else: sys.exit("no connect")
t = s.target
t.write32(0x40008064, t.read32(0x40008064) | (1 << 26))           # GPIO clock
m = t.read32(0x4003C034); t.write32(0x4003C034, (m & ~(0xF << 12)) | (0x2 << 12))   # PB03 input + pull
t.write32(0x4003C040, t.read32(0x4003C040) | (1 << 3))            # pull-up
t0 = time.time(); last = None; n = 0
while time.time() - t0 < secs:
    try: v = (t.read32(0x4003C044) >> 3) & 1
    except Exception: print(f"{time.time()-t0:6.2f}s link error"); time.sleep(0.1); continue
    if v != last:
        print(f"{time.time()-t0:6.2f}s PB03 = {v} ({'released/high' if v else 'PRESSED/low'})", flush=True); last = v; n += 1
    time.sleep(0.01)
print(f"{n} state readings")
