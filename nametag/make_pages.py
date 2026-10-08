#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the page images for firmware/nametag: a contact page and a "small name + QR code" page, packed for the tag's flash.

usage: make_pages.py CONFIG.json [OUT_DIR]       (default OUT_DIR: ./nametag-out)
CONFIG.json (keep your own copy OUT OF git, it has personal details; see nametag.example.json):
    {"name": "Ada Lovelace", "email": "ada@example.org", "phone": "555-0100", "url": "https://example.org"}
Writes pages.bin (flash it at 0x2000, see README.md) and page1.png / page2.png (4x previews).
Needs Pillow and segno (pip install pillow segno).

pages.bin layout: 16-byte header (b"PGS1", uint32 little-endian page count, 8 zero bytes) then page after page, 8000 bytes each
(4000-byte black/white plane then 4000-byte red plane, the same layout as scripts/make_frame.py).
"""
import json, os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from PIL import Image, ImageDraw, ImageFont
import segno
import eink_draw as E

W, H, VIS = E.W, E.H, E.VIS_W
RED, BLK, WHT = (220, 0, 0), (0, 0, 0), (255, 255, 255)
FONTS = ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def font(size, bold=True):
    for p in FONTS:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size, index=1 if (bold and p.endswith(".ttc")) else 0)
            except Exception: return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit(d, text, maxw, start=60, bold=True):
    for s in range(start, 6, -1):
        f = font(s, bold)
        if d.textlength(text, font=f) <= maxw: return f
    return font(7, bold)


def text(d, xy, t, f, fill=BLK, anchor="la"):
    d.text(xy, t, font=f, fill=fill, anchor=anchor)


def page_contact(c):
    img = Image.new("RGB", (W, H), WHT); d = ImageDraw.Draw(img); d.fontmode = "1"
    d.rectangle([0, 0, VIS - 1, 47], fill=RED)
    f = fit(d, c["name"], VIS - 20, 34); text(d, (VIS // 2, 24), c["name"], f, WHT, "mm")
    fe = fit(d, c["email"], VIS - 24, 26, False); text(d, (VIS // 2, 72), c["email"], fe, BLK, "mm")
    fp = fit(d, c["phone"], VIS - 24, 30, True); text(d, (VIS // 2, 106), c["phone"], fp, BLK, "mm")
    d.rectangle([0, 0, VIS - 1, H - 1], outline=BLK)
    return img


def page_qr(c):
    img = Image.new("RGB", (W, H), WHT); d = ImageDraw.Draw(img); d.fontmode = "1"
    q = segno.make(c["url"], error="q", micro=False)
    n = q.symbol_size(border=0)[0]; m = max(1, (H - 8) // n)            # largest whole-pixel module size that fits with a margin
    side = n * m; x0, y0 = VIS - side - 8, (H - side) // 2
    for r, row in enumerate(q.matrix):
        for k, v in enumerate(row):
            if v: d.rectangle([x0 + k * m, y0 + r * m, x0 + k * m + m - 1, y0 + r * m + m - 1], fill=BLK)
    left = x0 - 14
    parts = c["name"].split(" ", 1) if " " in c["name"] else [c["name"]]
    fs = min((fit(d, p, left, 30) for p in parts), key=lambda f: f.size)                         # smaller of the fitted fonts so the lines match
    ys = [(H // 2) - 20 + i * 30 for i in range(len(parts))] if len(parts) > 1 else [H // 2 - 6]
    for p, y in zip(parts, ys): text(d, (8, y), p, fs, BLK, "lm")
    d.rectangle([8, ys[-1] + 20, left - 8, ys[-1] + 22], fill=RED)
    text(d, (8, H - 14), "scan me", font(12, False), BLK, "lm")
    d.rectangle([0, 0, VIS - 1, H - 1], outline=BLK)
    print(f"QR: version {q.version}, {n}x{n} modules at {m}px = {side}px")
    return img


def main():
    c = json.load(open(sys.argv[1])); out = sys.argv[2] if len(sys.argv) > 2 else "nametag-out"
    os.makedirs(out, exist_ok=True)
    pages = [page_contact(c), page_qr(c)]
    blob = struct.pack("<4sI8x", b"PGS1", len(pages))
    for i, img in enumerate(pages, 1):
        bw, red = E.planes_from_image(img); blob += bw + red
        pv = Image.new("RGB", (W, H), WHT); pp = pv.load(); px = img.load()
        for x in range(W):
            for y in range(H): pp[x, y] = {"red": RED, "black": BLK, "white": WHT}[E.classify(px[x, y])]
        pv.resize((W * 4, H * 4), Image.NEAREST).save(f"{out}/page{i}.png")
    open(f"{out}/pages.bin", "wb").write(blob)
    cap = (0x80000 - 0x2000 - 16) // 8000              # flash 512 KiB, firmware in the first 8 KiB page, 16-byte header, 8000 bytes per page
    print(f"wrote {out}/pages.bin: {len(blob)} bytes, {len(pages)} pages (the flash holds up to {cap} full-colour pages, {cap * 2 + 1} black/white-only)")


main()
