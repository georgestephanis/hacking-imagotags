#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the 8000-byte frame (4000 black/white plane + 4000 red plane) that scripts/pico_eink.py draws.

usage: make_frame.py [IMAGE | --demo-pico] OUT.bin [--crop x0,y0,x1,y1] [--dither] [--preview out.png]
Reuses the image helpers from eink_draw.py (same quantisation and plane layout as the SWD route).
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import eink_draw as E


def demo_pico():
    img = Image.new("RGB", (E.W, E.H), "white"); d = ImageDraw.Draw(img); d.fontmode = "1"
    try:
        big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 34, index=1)
        mid = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except Exception:
        big = mid = small = ImageFont.load_default()
    d.rectangle([0, 0, E.VIS_W - 1, 33], fill=(255, 0, 0))
    d.text((8, 5), "Driven by a Pico", font=mid, fill="white")
    d.text((8, 40), "direct SPI", font=big, fill="black")
    d.text((8, 88), "no help from the tag's MCU:", font=small, fill="black")
    d.text((8, 104), "GP17-GP22 -> test points.", font=small, fill="black")
    d.rectangle([0, 0, E.VIS_W - 1, E.H - 1], outline="black")
    d.polygon([(210, 112), (225, 82), (240, 112)], fill=(255, 0, 0))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?"); ap.add_argument("out"); ap.add_argument("--demo-pico", action="store_true")
    ap.add_argument("--crop"); ap.add_argument("--dither", action="store_true"); ap.add_argument("--preview")
    a = ap.parse_args()
    # `image` and `out` are positional; with --demo-pico the single positional is the output
    if a.demo_pico and a.out is None: a.out, a.image = a.image, None
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    img = demo_pico() if a.demo_pico else E.fit(Image.open(a.image), crop)
    if a.dither and not a.demo_pico: img = E.dither3(img)
    bw, red = E.planes_from_image(img)
    open(a.out, "wb").write(bw + red)
    print(f"wrote {a.out}: {len(bw) + len(red)} bytes")
    if a.preview:
        pv = Image.new("RGB", (E.W, E.H), "white"); pp = pv.load(); px = img.load()
        for x in range(E.W):
            for y in range(E.H): pp[x, y] = {"red": (220, 0, 0), "black": (0, 0, 0), "white": (255, 255, 255)}[E.classify(px[x, y])]
        pv.resize((E.W * 3, E.H * 3), Image.NEAREST).save(a.preview); print("preview:", a.preview)


if __name__ == "__main__":
    main()
