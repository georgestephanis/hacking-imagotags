# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate the tone / half-tone test frames used in docs/display.md (8000-byte frames: 4000 black/white plane + 4000 red plane).

usage: make_tone_tests.py [OUT_DIR]        (default: ./tone-tests)   Needs Pillow; reuses the plane conversion from eink_draw.py.

Writes (each with a 4x preview PNG where it makes sense):
  t1_fs.bin        Floyd-Steinberg gradients: black->white, red->white, red->black
  t2_swatch.bin    the same three ink pairs as 9 flat steps (0/8..8/8 coverage) of an 8x8 Bayer pattern
  s1.bin           three solid bands (red | black | white): the known start state for the black/white-mode test
  kw_old_bw.bin    the black/white plane of s1, sent as the "old" plane (0x10) in black/white mode
  kw_new.bin       the "new" plane (0x13) for that test: 1 in the top half of the panel, 0 in the bottom half
  h2.bin           four bands testing the (bw, red) bit pairs: (1,1) white | (0,1) black | (1,0) red | (0,0) both bits set
Run them on the Pico with scripts/pico_uc81_probe.py.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import eink_draw as E

W, H, VIS = E.W, E.H, E.VIS_W
RED, BLK, WHT = (220, 0, 0), (0, 0, 0), (255, 255, 255)
PAIRS = [("black -> white", BLK, WHT), ("red -> white", RED, WHT), ("red -> black", RED, BLK)]   # (label, colour at t=0, colour at t=1)
BAYER = [[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26], [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
         [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25], [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]]
OUT = sys.argv[1] if len(sys.argv) > 1 else "tone-tests"


def font(n):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p): return ImageFont.truetype(p, n)
    return ImageFont.load_default()


def blocks(fn, kind):
    img = Image.new("RGB", (W, H), WHT); d = ImageDraw.Draw(img); d.fontmode = "1"
    d.rectangle([0, 0, VIS - 1, H - 1], outline=BLK)
    px = img.load(); y0, bh, x0, x1 = 3, 28, 4, VIS - 4
    for label, ca, cb in PAIRS:
        d.text((x0, y0), label + "  (" + kind + ")", font=font(9), fill=BLK)
        top = y0 + 11
        vals = fn(x1 - x0, bh)                   # rows of 0/1: 1 = colour cb
        for yy in range(bh):
            for xx in range(x1 - x0): px[x0 + xx, top + yy] = cb if vals[yy][xx] else ca
        y0 += 11 + bh + 2
    return img


def fs_gradient(w, h):                           # Floyd-Steinberg on a left->right ramp
    err = [[0.0] * (w + 2) for _ in range(h + 1)]; out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            v = x / (w - 1) + err[y][x + 1]; q = 1 if v >= 0.5 else 0; out[y][x] = q; e = v - q
            err[y][x + 2] += e * 7 / 16; err[y + 1][x] += e * 3 / 16; err[y + 1][x + 1] += e * 5 / 16; err[y + 1][x + 2] += e * 1 / 16
    return out


def swatches(w, h):                              # 9 flat levels, k/8 coverage of the second ink, 8x8 Bayer
    n = 9; sw = w // n
    return [[1 if BAYER[y % 8][x % 8] < min(x // sw, n - 1) * 8 else 0 for x in range(w)] for y in range(h)]


def save(img, name):
    bw, red = E.planes_from_image(img); open(f"{OUT}/{name}.bin", "wb").write(bw + red)
    pv = Image.new("RGB", (W, H), WHT); pp = pv.load(); px = img.load()
    for x in range(W):
        for y in range(H): pp[x, y] = {"red": RED, "black": BLK, "white": WHT}[E.classify(px[x, y])]
    pv.resize((W * 4, H * 4), Image.NEAREST).save(f"{OUT}/{name}_preview.png"); print("wrote", name)
    return bw


os.makedirs(OUT, exist_ok=True)
save(blocks(fs_gradient, "Floyd-Steinberg"), "t1_fs")
save(blocks(swatches, "Bayer 8x8, 9 levels"), "t2_swatch")

bands = Image.new("RGB", (W, H), WHT); d = ImageDraw.Draw(bands); t = VIS // 3
d.rectangle([0, 0, t - 1, H - 1], fill=RED); d.rectangle([t, 0, 2 * t - 1, H - 1], fill=BLK)
bw = save(bands, "s1")
open(f"{OUT}/kw_old_bw.bin", "wb").write(bw)
# per line: 16 bytes = 128 rows; bytes 0..7 = panel y 0..63 (bottom half, new data 0), bytes 8..15 = y 64..127 (top half, new data 1)
open(f"{OUT}/kw_new.bin", "wb").write(bytes(([0x00] * 8 + [0xFF] * 8) * 250))
print("wrote kw_old_bw, kw_new")

combo = [(1, 1), (0, 1), (1, 0), (0, 0)]         # (bw bit, red bit) per band of 62 lines; the two hidden lines stay white
bw = bytearray(); rd = bytearray()
for line in range(250):
    a, b = combo[min(line // 62, 3)] if line < 248 else (1, 1)
    bw += bytes([0xFF if a else 0x00] * 16); rd += bytes([0xFF if b else 0x00] * 16)
open(f"{OUT}/h2.bin", "wb").write(bytes(bw) + bytes(rd)); print("wrote h2")
