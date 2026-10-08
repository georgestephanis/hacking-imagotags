#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the page images for firmware/nametag: a contact page and a "small name + QR code" page, packed for the tag's flash.

usage: make_pages.py CONFIG.json [OUT_DIR]       (default OUT_DIR: ./nametag-out)
CONFIG.json (keep your own copy OUT OF git, it has personal details; see nametag.example.json):
    {"name": "Ada Lovelace", "email": "ada@example.org", "phone": "555-0100",
     "pages": [{"type": "contact"},
               {"type": "qr", "url": "https://example.org", "caption": ["example.org"]},
               {"type": "qr", "url": "https://account.venmo.com/u/ada", "caption": ["Venmo", "@ada"]}]}
A "qr" page shows the name, a red arrow pointing at the QR code, and the caption lines under the arrow (default: the URL's domain).
Without "pages" you get a contact page and one QR page for "url".
Writes pages.bin (flash it at 0x2000, see README.md) and pageN.png (4x previews).
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


def best_qr(url, avail):
    """Pick (error level, symbol) giving the largest whole-pixel module size that fits `avail` pixels; ties go to the stronger error correction."""
    best = None
    for lvl in ("q", "m", "l"):
        q = segno.make(url, error=lvl, micro=False); n = q.symbol_size(border=0)[0]; m = avail // n
        if m >= 1 and (best is None or m > best[0]): best = (m, lvl, q, n)
    return best


def arrow(d, x0, x1, y, h=22):
    """A right-pointing red arrow from x0 to x1 centred on y."""
    head = int(h * 0.9); mid = h // 2
    d.rectangle([x0, y - 4, x1 - head, y + 4], fill=RED)
    d.polygon([(x1 - head, y - mid), (x1, y), (x1 - head, y + mid)], fill=RED)


def page_qr(c, spec):
    img = Image.new("RGB", (W, H), WHT); d = ImageDraw.Draw(img); d.fontmode = "1"
    m, lvl, q, n = best_qr(spec["url"], H - 8); side = n * m; x0, y0 = VIS - side - 8, (H - side) // 2
    for r, row in enumerate(q.matrix):
        for k, v in enumerate(row):
            if v: d.rectangle([x0 + k * m, y0 + r * m, x0 + k * m + m - 1, y0 + r * m + m - 1], fill=BLK)
    left = x0 - 12                                                       # right edge of the left-hand column
    parts = c["name"].split(" ", 1) if " " in c["name"] else [c["name"]]
    fs = min((fit(d, p, left - 8, 30) for p in parts), key=lambda f: f.size)
    for p, y in zip(parts, ([18, 46] if len(parts) > 1 else [30])): text(d, (8, y), p, fs, BLK, "lm")
    arrow(d, 8, left, 74)
    cap = spec.get("caption") or [spec["url"].split("//")[-1].split("/")[0]]
    ys = [100] if len(cap) == 1 else [96, 114]
    for i, (line, y) in enumerate(zip(cap, ys)):
        text(d, (8, y), line, fit(d, line, left - 8, 17 if len(cap) == 1 else (16 if i == 0 else 13), i == 0), BLK, "lm")
    d.rectangle([0, 0, VIS - 1, H - 1], outline=BLK)
    print(f"QR {spec['url']}: version {q.version}, error {lvl.upper()}, {n}x{n} modules at {m}px = {side}px")
    return img


def main():
    c = json.load(open(sys.argv[1])); out = sys.argv[2] if len(sys.argv) > 2 else "nametag-out"
    os.makedirs(out, exist_ok=True)
    specs = c.get("pages") or [{"type": "contact"}, {"type": "qr", "url": c["url"]}]
    pages = [page_contact(c) if sp["type"] == "contact" else page_qr(c, sp) for sp in specs]
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
