# SPDX-License-Identifier: GPL-2.0-or-later
# MicroPython for the Pico: instrumented UC81xx experiments on the tag's e-paper, driven directly through the display test points
# (same wiring as scripts/pico_eink.py; the tag's MCU is held in reset by GP1). Prints the time of every phase of a refresh.
#
# Copy this file to the Pico as probe.py plus the frames from scripts/make_tone_tests.py, then e.g.:
#   mpremote cp scripts/pico_uc81_probe.py :probe.py ; mpremote cp tone-tests/t1_fs.bin :t1_fs.bin
#   mpremote exec "import probe; probe.draw('t1_fs.bin')"                      # normal three-colour update, with timings
#   mpremote exec "import probe; probe.kw('kw_old_bw.bin', 'kw_new.bin')"      # black/white (KW) mode update
#   mpremote exec "import probe; probe.partial_kw('frame.bin', 30, 109)"       # partial-window attempt (KW mode)
# See docs/display.md ("Timing", "Tone and half-tone experiments") for what each of these showed.
import time
from machine import Pin, SPI

W, H = 250, 128
NRESET = Pin(1, Pin.OUT, value=0)           # hold the tag's MCU in reset
PWR = Pin(16, Pin.OUT, value=0)             # PC06 low = panel power on
CS = Pin(17, Pin.OUT, value=1); DC = Pin(20, Pin.OUT, value=1); RES = Pin(21, Pin.OUT, value=1)
BUSY = Pin(22, Pin.IN)                      # low = busy
spi = SPI(0, baudrate=2_000_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19), miso=None)
now = time.ticks_ms


def wait(what, timeout=120000):
    t0 = now()
    while not BUSY.value():
        if time.ticks_diff(now(), t0) > timeout: raise RuntimeError("busy: " + what)
        time.sleep_ms(5)
    return time.ticks_diff(now(), t0)


def cmd(c, data=b""):
    DC.value(0); CS.value(0); spi.write(bytes([c])); CS.value(1)
    if data: DC.value(1); CS.value(0); spi.write(data); CS.value(1)
    DC.value(1)


def block(c, b):
    DC.value(0); CS.value(0); spi.write(bytes([c])); CS.value(1); DC.value(1); CS.value(0)
    for i in range(0, len(b), 256): spi.write(b[i:i + 256])
    CS.value(1)


def run(label, psr, p10, p13):
    """Full-panel update with panel setting byte `psr`: 0xCF = three-colour, 0xDF = black/white (KW) mode. Prints per-phase timings."""
    T = []; t0 = ta = now()
    def lap(n):
        nonlocal ta
        t = now(); T.append((n, time.ticks_diff(t, ta))); ta = t
    RES.value(0); time.sleep_ms(20); RES.value(1); time.sleep_ms(100); lap("reset")
    cmd(0x01, bytes([0x03, 0x00, 0x2B, 0x2B, 0x03])); cmd(0x06, bytes([0x17, 0x17, 0x17])); lap("power + booster commands")
    cmd(0x04); wait("power on"); lap("power on (BUSY)")
    cmd(0x00, bytes([psr])); cmd(0x61, bytes([H, 0, W])); cmd(0x50, bytes([0x77])); lap("panel setting / resolution / vcom")
    block(0x10, p10); lap("upload plane 0x10 (4000 B)")
    block(0x13, p13); lap("upload plane 0x13 (4000 B)")
    cmd(0x12); time.sleep_ms(200); wait("refresh"); lap("refresh (BUSY low)")
    cmd(0x02); wait("power off"); lap("power off (BUSY)")
    print("==", label, "psr=0x%02X" % psr)
    for n, v in T: print("  %-36s %6d ms" % (n, v))
    print("  %-36s %6d ms" % ("TOTAL", time.ticks_diff(now(), t0)))


def draw(path, psr=0xCF):
    f = open(path, "rb").read()
    run(path, psr, f[:4000], f[4000:])


def kw(old_path, new_path):
    run("KW mode " + old_path + " -> " + new_path, 0xDF, open(old_path, "rb").read(), open(new_path, "rb").read())


def partial_kw(path, l0, l1):
    """Partial-window attempt in KW mode: window = lines l0..l1, all 128 rows; new data = the old data inverted. See docs/display.md."""
    f = open(path, "rb").read(); old = f[:4000][l0 * 16:(l1 + 1) * 16]; new = bytes(b ^ 0xFF for b in old)
    t0 = now()
    RES.value(0); time.sleep_ms(20); RES.value(1); time.sleep_ms(100)
    cmd(0x01, bytes([0x03, 0x00, 0x2B, 0x2B, 0x03])); cmd(0x06, bytes([0x17, 0x17, 0x17])); cmd(0x04); wait("power on")
    cmd(0x00, bytes([0xDF])); cmd(0x61, bytes([H, 0, W])); cmd(0x50, bytes([0x77]))
    cmd(0x91); cmd(0x90, bytes([0x00, 0x7F, l0 >> 8, l0 & 255, l1 >> 8, l1 & 255, 0x01]))     # partial in; rows 0..127, lines l0..l1
    block(0x10, old); block(0x13, new)
    cmd(0x12); time.sleep_ms(200); busy = wait("partial refresh") + 200; cmd(0x92); cmd(0x02); wait("power off")
    print("== partial window, KW mode: lines %d..%d" % (l0, l1)); print("  BUSY low after refresh command: %d ms   TOTAL %d ms" % (busy, time.ticks_diff(now(), t0)))
