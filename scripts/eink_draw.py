#!/usr/bin/env python3
"""Show an image (or a built-in demo) on the SES-imagotag HRD3-0210-A's 250x128 black/white/red e-paper panel.

usage: eink_draw.py [IMAGE | --demo] [--crop x0,y0,x1,y1] [--dither] [--led] [--no-refresh] [--preview out.png]

The image is resized/cropped to 250x128 (landscape, connector on the right) and quantised: red where it is clearly red, black where it is dark,
white otherwise. Transport: the MCU's GPIOs are bit-banged from the host through SWD (scripts/swdburst.py), so the tag does not need firmware.
Panel facts found by experiment (docs/research-log.md): RES = PC04, BUSY = PA08 (active low), SCK = PC01, SDA = PC00, CS/DC = PC02/PC03 (order unresolved),
display power path PC06 (drive LOW), controller UC81xx-like: PSR 0xCF, 0x61 resolution 128 x 250, planes 0x10 (black/white, 0 = black) and
0x13 (red, 0 = red), refresh 0x12 takes ~18 s. Panel coordinates: x = line 0..249 left to right, y = 0..127 bottom to top (connector at the right).
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pyocd.core.helpers import ConnectHelper
from swdburst import burst

W, H = 250, 128          # lines driven / panel rows
VIS_W = 248              # columns actually visible: the last two lines (x = 248, 249, right side) are not displayed
G = 0x4003C000
DO_C, DIN_A = G + 0x30 * 2 + 0x10, G + 0x14
SDA, SCK, RES = 1 << 0, 1 << 1, 1 << 4
CS, DC = 1 << 2, 1 << 3


def classify(px):
    r, g, b = px[:3]
    if r > 150 and g < 110 and b < 110: return "red"
    if (r * 299 + g * 587 + b * 114) / 1000 < 110: return "black"
    return "white"


def planes_from_image(img):
    """img: PIL RGB 250x128, upright landscape. Returns (bw_plane, red_plane) as bytes, 16 bytes per line, 250 lines."""
    px = img.load(); bw = bytearray(); red = bytearray()
    for x in range(W):
        for yb in range(H // 8):
            vb, vr = 0xFF, 0xFF
            for bit in range(8):
                y = yb * 8 + bit                          # panel y, 0 = bottom
                c = classify(px[x, H - 1 - y])            # image row 0 is the top
                if c == "black": vb &= ~(0x80 >> bit)
                elif c == "red": vr &= ~(0x80 >> bit)
            bw.append(vb); red.append(vr)
    return bytes(bw), bytes(red)


def demo_image():
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    d.fontmode = "1"          # no antialiasing: strokes stay whole pixels instead of being rounded away by the 3-colour quantiser
    try:
        big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38, index=1)
        mid = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except Exception:
        big = mid = small = ImageFont.load_default()
    d.rectangle([0, 0, VIS_W - 1, 33], fill=(255, 0, 0))
    d.text((8, 5), "SES-imagotag", font=mid, fill="white")
    d.text((8, 40), "HRD3-0210-A", font=big, fill="black")
    d.text((8, 88), "unlocked, reflashed,", font=small, fill="black")
    d.text((8, 104), "and drawing on its own.", font=small, fill="black")
    d.rectangle([0, 0, VIS_W - 1, H - 1], outline="black")
    d.ellipse([205, 80, 240, 115], fill=(255, 0, 0))
    return img


def dither3(img):
    """Floyd-Steinberg dither an RGB image to the panel's three inks (black, white, red)."""
    pal = Image.new("P", (1, 1)); pal.putpalette([0, 0, 0, 255, 255, 255, 220, 0, 0] + [0, 0, 0] * 253)
    return img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")


def fit(img, crop=None):
    img = img.convert("RGB")
    if crop: img = img.crop(crop)
    r = max(VIS_W / img.width, H / img.height)
    img = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    l, t = (img.width - VIS_W) // 2, (img.height - H) // 2
    out = Image.new("RGB", (W, H), "white")          # the two hidden lines stay white
    out.paste(img.crop((l, t, l + VIS_W, t + H)), (0, 0))
    return out


class Panel:
    def __init__(self, led=False):
        self.led_on = led
        for i in range(20):
            try:
                self.s = ConnectHelper.session_with_chosen_probe(blocking=False, options={
                    "target_override": "cortex_m", "connect_mode": "attach", "frequency": 1000000, "resume_on_disconnect": False})
                self.s.open(); break
            except Exception: time.sleep(0.2)
        else: sys.exit("could not connect to the target")
        self.T = self.s.target
        self.T.write32(0xE000EDF0, 0xA05F0003)                                     # halt: do not fight the running demo firmware
        self.T.write32(0x40008064, self.T.read32(0x40008064) | (1 << 26))        # GPIO clock
        for p in range(5): self.mode(2, p, 4)
        self.T.write32(DO_C, RES | CS | DC)
        self.mode(2, 6, 4); self.T.write32(DO_C, (self.T.read32(DO_C) & ~(1 << 6)))   # PC06 low = display power path on
        self.mode(0, 8, 2); self.T.write32(G + 0x10, self.T.read32(G + 0x10) & ~(1 << 8))
        time.sleep(0.1)

    def mode(self, port, pin, m):
        a = G + 0x30 * port + (0x04 if pin < 8 else 0x0C); sh = 4 * (pin % 8)
        self.T.write32(a, (self.T.read32(a) & ~(0xF << sh)) | (m << sh))

    def led(self, *cols):
        if not self.led_on: return
        T = self.T; GB, GD = G + 0x30, G + 0x90
        T.write32(GD + 0x10, T.read32(GD + 0x10) | 1); T.write32(GD + 4, (T.read32(GD + 4) & ~0xF) | 4)
        m = T.read32(GB + 4)
        for pin in (0, 2, 4): m = (m & ~(0xF << (4 * pin))) | (4 << (4 * pin))
        T.write32(GB + 4, m); v = T.read32(GB + 0x10) & ~0x15
        for c in cols: v |= {"red": 4, "green": 1, "blue": 16}[c]
        T.write32(GB + 0x10, v)

    def busy_high(self): return (self.T.read32(DIN_A) >> 8) & 1

    def wait(self, what, timeout=90):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.busy_high(): return time.time() - t0
            time.sleep(0.02)
        raise RuntimeError(f"panel stayed busy: {what}")

    @staticmethod
    def xfer(data, is_cmd):
        base = RES | (0 if is_cmd else DC); vals = [RES | CS | DC, base]
        for byte in data:
            for i in range(8):
                b = SDA if (byte >> (7 - i)) & 1 else 0; vals += [base | b, base | b | SCK]
        return vals + [base, RES | CS | DC]

    def cmd(self, c, data=()):
        burst(self.T, DO_C, self.xfer([c], True) + (self.xfer(list(data), False) if data else []))

    def show(self, bw, red, refresh=True):
        self.led("red")
        self.T.write32(DO_C, CS | DC); time.sleep(0.02); self.T.write32(DO_C, RES | CS | DC); time.sleep(0.1)
        self.cmd(0x01, [0x03, 0x00, 0x2B, 0x2B, 0x03]); self.cmd(0x06, [0x17, 0x17, 0x17])
        self.cmd(0x04); self.wait("power on")
        self.cmd(0x00, [0xCF]); self.cmd(0x61, [H, 0, W]); self.cmd(0x50, [0x77])
        self.led("red", "green")
        self.led("green"); self.cmd(0x10); burst(self.T, DO_C, self.xfer(bw, False))
        self.cmd(0x13); burst(self.T, DO_C, self.xfer(red, False))
        if refresh:
            self.led("blue"); self.cmd(0x12); time.sleep(0.2); dt = self.wait("refresh"); print(f"refresh took {dt:.1f} s")
        self.led("red", "green", "blue"); self.cmd(0x02); self.wait("power off"); time.sleep(1.0); self.led()

    def close(self): self.s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?"); ap.add_argument("--demo", action="store_true"); ap.add_argument("--led", action="store_true")
    ap.add_argument("--no-refresh", action="store_true"); ap.add_argument("--preview")
    ap.add_argument("--crop", help="x0,y0,x1,y1 in source-image pixels, applied before fitting"); ap.add_argument("--dither", action="store_true"); ap.add_argument("--preview-only", action="store_true", help="write the --preview image and exit without touching the tag")
    a = ap.parse_args()
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    img = demo_image() if (a.demo or not a.image) else fit(Image.open(a.image), crop)
    if a.dither and not (a.demo or not a.image): img = dither3(img)
    bw, red = planes_from_image(img)
    if a.preview:
        pv = Image.new("RGB", (W, H), "white"); pp = pv.load(); px = img.load()
        for x in range(W):
            for y in range(H): pp[x, y] = {"red": (220, 0, 0), "black": (0, 0, 0), "white": (255, 255, 255)}[classify(px[x, y])]
        pv.resize((W * 3, H * 3), Image.NEAREST).save(a.preview); print("preview saved to", a.preview)
    if a.preview_only: return
    p = Panel(led=a.led)
    try: p.show(bw, red, refresh=not a.no_refresh)
    finally: p.close()
    print("done")



if __name__ == "__main__":
    main()
