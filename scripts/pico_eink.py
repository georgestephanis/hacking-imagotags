# SPDX-License-Identifier: GPL-2.0-or-later
# MicroPython for the Pico: draw a frame on the tag's e-paper by driving the panel's SPI lines directly
# through the display test points (bypassing the tag's MCU). Same init/refresh sequence as scripts/eink_draw.py.
#
# Wiring (see docs): tp43 SDA -> GP19, tp48 SCK -> GP18, tp42 CS -> GP17, tp47 D/C -> GP20, tp44 RES -> GP21,
# tp41 BUSY -> GP22, tp40 PC06 power -> GP16 (optional), tag nRESET (tp23) -> GP1, tag GND/3V3 as before.
# ~330 ohm in series with each Pico-driven line is recommended (tag rail ~2.9 V, Pico drives 3.3 V).
#
# Usage on the Pico:  copy this file as main.py (or run with mpremote) and copy frame.bin (from scripts/make_frame.py) next to it.
import time
from machine import Pin, SPI

W, H = 250, 128
NRESET = Pin(1, Pin.OUT, value=0)        # hold the tag's MCU in reset so it does not fight us on the display lines
PWR = Pin(16, Pin.OUT, value=0)          # PC06 low = panel power path on (the tag floats it low in reset anyway)
CS = Pin(17, Pin.OUT, value=1)
DC = Pin(20, Pin.OUT, value=1)
RES = Pin(21, Pin.OUT, value=1)
BUSY = Pin(22, Pin.IN)                   # low = busy
spi = SPI(0, baudrate=500_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19), miso=None)


def wait(what, timeout_ms=90_000):
    t0 = time.ticks_ms()
    while not BUSY.value():
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
            raise RuntimeError("panel stayed busy: " + what)
        time.sleep_ms(20)
    return time.ticks_diff(time.ticks_ms(), t0)


def cmd(c, data=b""):
    DC.value(0); CS.value(0); spi.write(bytes([c])); CS.value(1)
    if data:
        DC.value(1); CS.value(0); spi.write(data); CS.value(1)
    DC.value(1)


def data_block(c, block):
    DC.value(0); CS.value(0); spi.write(bytes([c])); CS.value(1)
    DC.value(1); CS.value(0)
    for i in range(0, len(block), 256):
        spi.write(block[i:i + 256])
    CS.value(1)


def show(bw, red):
    RES.value(0); time.sleep_ms(20); RES.value(1); time.sleep_ms(100)
    cmd(0x01, bytes([0x03, 0x00, 0x2B, 0x2B, 0x03])); cmd(0x06, bytes([0x17, 0x17, 0x17]))
    cmd(0x04); wait("power on")
    cmd(0x00, bytes([0xCF])); cmd(0x61, bytes([H, 0, W])); cmd(0x50, bytes([0x77]))
    data_block(0x10, bw); data_block(0x13, red)
    cmd(0x12); time.sleep_ms(200)
    print("refresh took", wait("refresh"), "ms")
    cmd(0x02); wait("power off")


def main(path="frame.bin"):
    with open(path, "rb") as f:
        frame = f.read()
    assert len(frame) == 8000, "frame.bin must be 8000 bytes (4000 black/white + 4000 red)"
    show(frame[:4000], frame[4000:])
    print("done")


main()
