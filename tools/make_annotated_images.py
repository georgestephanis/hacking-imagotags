#!/usr/bin/env python3
"""Draw the named pads / pins onto the board photos embedded in the traced SVG (hardware/netlist/contrd010a.svg).

usage: make_annotated_images.py [SVG] [OUT_DIR]      -> test-pad-side.png, mcu-side.png, mcu-pinout.png
Needs Pillow. Pad positions come from the SVG (in photo pixels); the names come from tools/rename_netlist.py.
"""
import base64, io, os, re, sys
from PIL import Image, ImageDraw, ImageFont

SVG = sys.argv[1] if len(sys.argv) > 1 else "hardware/netlist/contrd010a.svg"
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/images"
FONT = next((p for p in ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if os.path.exists(p)), None)
F = lambda n: ImageFont.truetype(FONT, n) if FONT else ImageFont.load_default()
s = open(SVG).read()


def side_image(side):
    i = s.index(f'<g data-side="{side}"'); j = s.index("<image", i)
    return Image.open(io.BytesIO(base64.b64decode(re.search(r'base64,([^"]*)"', s[j:]).group(1)))).convert("RGB")


def attrs(t): return dict(re.findall(r"([\w-]+)=\"([^\"]*)\"", t))


def pads(prefix):
    out = {}
    for t in re.findall(r"<(?:rect|circle)\b[^>]*\bid=\"%s[^\"]*\"[^>]*/?>" % prefix, s):
        a = attrs(t)
        if "cx" in a: out[a["id"]] = (float(a["cx"]), float(a["cy"]), 2 * float(a["r"]), 2 * float(a["r"]))
        else:
            w, h = float(a["width"]), float(a["height"]); out[a["id"]] = (float(a["x"]) + w / 2, float(a["y"]) + h / 2, w, h)
    return out


GROUPS = [("tp-swclk", "#000000"), ("tp-swdio", "#000000"), ("tp-swo", "#000000"), ("tp-nreset", "#000000"), ("tp-vdd", "#d62728"),
          ("tp-gnd", "#555555"), ("tp-vin", "#d62728"), ("tp-sig", "#ff7f0e"), ("tp-btn", "#ff7f0e"), ("tp-led", "#e377c2"),
          ("tp-disp", "#1f77b4"), ("tp-boost", "#8c564b"), ("tp-p", "#2ca02c")]


def colour(name):
    return next((c for p, c in GROUPS if name.startswith(p)), "#9a9a9a")


def tag(d, xy, text, c, size=34):
    f = F(size); tb = d.textbbox(xy, text, font=f)
    d.rectangle([tb[0] - 6, tb[1] - 4, tb[2] + 6, tb[3] + 6], fill=(255, 255, 255, 230), outline=c, width=2); d.text(xy, text, fill=c, font=f)


def place(boxes, x, y, w, h, avoid):
    for r in (46, 80, 120, 170):
        for dx, dy in ((1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 1), (-1, -1), (-1, 1)):
            cx, cy = x + dx * (r + (w / 2 if dx else 0)), y + dy * (r + (h / 2 if dy else 0))
            b = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            if b[0] < 0 or b[1] < 0 or b[2] > avoid[0] or b[3] > avoid[1]: continue
            if all(b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3] for o in boxes): return b
    return None


def test_pad_side():
    im = side_image("back"); d = ImageDraw.Draw(im, "RGBA"); f = F(30); boxes = []
    tps = pads("tp-")
    for k, (x, y, w, h) in tps.items(): boxes.append((x - 30, y - 30, x + 30, y + 30))
    d.rectangle([874, 100, 2724, 600], outline="#2ca02c", width=6); tag(d, (890, 110), "NFC coil (no NFC chip fitted)", "#2ca02c")
    d.rectangle([40, 40, 220, 250], outline="#e377c2", width=6); tag(d, (235, 60), "RGB LED (common anode, gated by PD00)", "#e377c2")
    boxes += [(40, 40, 900, 250)]
    for k, (x, y, w, h) in sorted(tps.items()):
        name = k[3:] if not k.startswith("tp-back-") else None
        c = colour(k); d.ellipse([x - 28, y - 28, x + 28, y + 28], outline=c, width=5)
        text = name or "?" + k.split("-")[-1]
        f2 = f if name else F(24)
        tb = d.textbbox((0, 0), text, font=f2); tw, th = tb[2] - tb[0] + 14, tb[3] - tb[1] + 12
        b = place(boxes, x, y, tw, th, im.size)
        if not b: continue
        boxes.append(b)
        d.line([(x, y), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)], fill=c, width=3)
        d.rectangle(b, fill=(255, 255, 255, 225), outline=c, width=3); d.text((b[0] + 7, b[1] + 3), text, fill=c, font=f2)
    ly = 90
    for lab, c in (("debug / reset", "#000000"), ("power", "#d62728"), ("GND", "#555555"), ("signal spring / button", "#ff7f0e"), ("LED", "#e377c2"),
                   ("display (direct SPI)", "#1f77b4"), ("booster", "#8c564b"), ("spare GPIO", "#2ca02c"), ("untraced / unknown", "#9a9a9a")):
        d.rectangle([2900, ly, 2936, ly + 26], fill=c); tag(d, (2950, ly - 4), lab, "#333333", 28); ly += 46
    im.thumbnail((2600, 2600)); im.save(f"{OUT}/test-pad-side.png", optimize=True)


def mcu_side():
    im = side_image("front"); d = ImageDraw.Draw(im, "RGBA")
    p = pads("pad-front-"); p.update(pads("spring-")); p.update(pads("mcu-"))
    for n, lab in (("spring-gnd", "spring-gnd"), ("spring-vin-3v3", "spring-vin-3v3 (power in)"), ("spring-sig", "spring-sig (-> PB01)")):
        x, y, w, h = p[n]; d.rectangle([x - w / 2 - 10, y - h / 2 - 10, x + w / 2 + 10, y + h / 2 + 10], outline="#d62728", width=6)
        tag(d, (x - 90, y - h / 2 - 66), lab, "#d62728")
    xs = [p[k] for k in p if k.startswith("mcu-")]
    x0, x1 = min(v[0] for v in xs) - 40, max(v[0] for v in xs) + 40; y0, y1 = min(v[1] for v in xs) - 40, max(v[1] for v in xs) + 40
    d.rectangle([x0, y0, x1, y1], outline="#1f77b4", width=6); tag(d, (x0 - 20, y1 + 118), "EFR32FG22 QFN40: pin 1 = top of left side", "#1f77b4", 30)
    nfc = [p[f"pad-front-{n}"] for n in range(277, 285) if f"pad-front-{n}" in p]
    if nfc:
        a = (min(v[0] for v in nfc) - 40, min(v[1] for v in nfc) - 40, max(v[0] for v in nfc) + 40, max(v[1] for v in nfc) + 40)
        d.rectangle(a, outline="#2ca02c", width=6); tag(d, (a[0] - 40, a[3] + 14), "NFC IC footprint (empty)", "#2ca02c", 30)
    ind = [p[f"pad-front-{n}"] for n in (315, 316) if f"pad-front-{n}" in p]
    if ind:
        a = (min(v[0] - v[2] / 2 for v in ind) - 20, min(v[1] - v[3] / 2 for v in ind) - 20, max(v[0] + v[2] / 2 for v in ind) + 20, max(v[1] + v[3] / 2 for v in ind) + 20)
        d.rectangle(a, outline="#8c564b", width=6); tag(d, (a[0], a[1] - 54), "boost inductor", "#8c564b", 30)
    d.rectangle([137, 560, 380, 1330], outline="#ff7f0e", width=6); tag(d, (150, 500), "24-pin panel FPC", "#ff7f0e")
    snap = im.copy(); snap.thumbnail((2600, 2600)); snap.save(f"{OUT}/mcu-side.png", optimize=True)
    # zoomed pinout
    z = 3; box = (int(x0 - 330), int(y0 - 170), int(x1 + 330), int(y1 + 190))
    c = im.crop(box).resize(((box[2] - box[0]) * z, (box[3] - box[1]) * z), Image.LANCZOS); d = ImageDraw.Draw(c, "RGBA")
    mp = {k: v for k, v in p.items() if k.startswith("mcu-")}
    for k, (x, y, w, h) in mp.items():
        pin = int(k.split("-")[1]); name = k.split("-", 2)[2].upper()
        X, Y = (x - box[0]) * z, (y - box[1]) * z; t = f"{pin} {name}"; tb = d.textbbox((0, 0), t, font=F(30))
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        side = w > h     # left/right-side pads are wide, top/bottom-row pads are tall
        pad_px = 6
        if side:
            lx = X - 40 - tw if x < (x0 + x1) / 2 else X + 40
            d.rectangle([lx - pad_px, Y - th / 2 - 8, lx + tw + pad_px, Y + th / 2 + 6], fill=(255, 255, 255, 215))
            d.text((lx, Y - th / 2 - 4), t, fill="#b00020", font=F(30))
            d.line([(X - 34, Y), (X - 6, Y)] if x < (x0 + x1) / 2 else [(X + 6, Y), (X + 34, Y)], fill="#b00020", width=2)
        else:
            tmp = Image.new("RGBA", (tw + 16, th + 16), (255, 255, 255, 215)); ImageDraw.Draw(tmp).text((8, 2), t, fill="#b00020", font=F(30)); tmp = tmp.rotate(90, expand=True)
            if y < (y0 + y1) / 2: c.paste(tmp, (int(X - tmp.width / 2), int(Y - 40 - tmp.height)), tmp)
            else: c.paste(tmp, (int(X - tmp.width / 2), int(Y + 40)), tmp)
    c.thumbnail((2400, 2400)); c.save(f"{OUT}/mcu-pinout.png", optimize=True)


os.makedirs(OUT, exist_ok=True)
test_pad_side(); mcu_side(); print("wrote", OUT)
