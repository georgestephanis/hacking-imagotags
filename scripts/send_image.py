#!/usr/bin/env python3
"""Send an image to a tag running firmware/eink_receiver over its signal contact (PB01), from any 3.3 V serial TX.

usage: send_image.py PORT [IMAGE | --demo] [--baud 38400] [--crop x0,y0,x1,y1] [--dither] [--preview out.png]
       send_image.py PORT --raw frame.bin ...        (send an already-built frame)

Wiring: serial adapter / Pico UART TX -> the tag's signal spring contact (pad-front-123); GND -> ground contact; the tag also needs
+3.3 V on its supply contact (pad-front-122). With the Pico debug probe (debugprobe firmware): TX = GP4 (pin 6), port /dev/cu.usbmodemXXXX.

Frame (see firmware/eink_receiver/receiver.c): 0x55, 0xA5 0x5A, 8000 payload bytes (black/white plane then red plane, as built by
eink_draw.planes_from_image), CRC-16/CCITT-FALSE of the payload (big-endian). 8005 bytes: ~2 s at 38400 baud. The tag then refreshes (~18 s).
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
from PIL import Image
from eink_draw import W, H, classify, planes_from_image, fit, dither3, demo_image


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def build_frame(bw: bytes, red: bytes) -> bytes:
    payload = bw + red
    assert len(payload) == 8000, len(payload)
    return b"\x55\xA5\x5A" + payload + crc16_ccitt_false(payload).to_bytes(2, "big")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port"); ap.add_argument("image", nargs="?"); ap.add_argument("--demo", action="store_true")
    ap.add_argument("--baud", type=int, default=38400); ap.add_argument("--crop"); ap.add_argument("--dither", action="store_true")
    ap.add_argument("--preview"); ap.add_argument("--raw", help="send this prebuilt frame file instead of an image")
    a = ap.parse_args()
    if a.raw:
        frame = open(a.raw, "rb").read()
    else:
        crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
        img = demo_image() if (a.demo or not a.image) else fit(Image.open(a.image), crop)
        if a.dither and not (a.demo or not a.image): img = dither3(img)
        if a.preview:
            pv = Image.new("RGB", (W, H)); pp = pv.load(); px = img.load()
            for x in range(W):
                for y in range(H): pp[x, y] = {"red": (220, 0, 0), "black": (0, 0, 0), "white": (255, 255, 255)}[classify(px[x, y])]
            pv.resize((W * 3, H * 3), Image.NEAREST).save(a.preview); print("preview saved to", a.preview)
        frame = build_frame(*planes_from_image(img))
    print(f"sending {len(frame)} bytes at {a.baud} baud on {a.port} (~{len(frame) * 10 / a.baud:.1f} s)")
    with serial.Serial(a.port, a.baud, bytesize=8, parity="N", stopbits=1, timeout=1, write_timeout=30) as ser:
        time.sleep(0.2)                       # let the line idle high
        ser.write(frame); ser.flush()
        time.sleep(len(frame) * 10 / a.baud + 0.3)
    print("sent. The tag's LED: blue while receiving, then white (refreshing, ~18 s) and green when done; red = bad frame.")


if __name__ == "__main__":
    main()
