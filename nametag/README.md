# nametag: a standalone name badge on the ContRD010A tag

Turns a tag into a wearable name badge that runs from a 3.3 V supply with no host: **page 1** shows a name, email and phone number; **a press of the button** (the one on the back, PB03) switches to
**page 2**, a smaller name beside a **QR code** for a URL. More pages can be added; each press moves to the next and wraps round.

> Status: the page generator and the layouts are done and checked (the QR decodes). **The firmware is not written yet**; it waits for the layouts to be approved.
> Your details live in a local config that is kept out of git (see below).

## Make the pages

```bash
cp nametag/nametag.example.json nametag/mine.local.json      # *.local.json is gitignored; edit it
python3 nametag/make_pages.py nametag/mine.local.json        # needs: pip install pillow segno
```

Output (in `./nametag-out/`): `page1.png`, `page2.png` (4x previews of exactly what the panel will draw, red header and rule = red ink) and `pages.bin` (the flash image).

- Config keys: `name`, `email`, `phone`, `url`.
- The QR code is version 2 (25 × 25 modules) at **error-correction level Q** (25 % recovery) for a 20-character URL, drawn at 4 px per module = 100 px (about 19 mm at the panel's 0.1875 mm pixels).
  Longer URLs need a bigger version and smaller modules; keep URLs short. The generator picks the largest whole-pixel module size that fits.
- Text is drawn with no anti-aliasing (the panel has no greys); the name is sized to fit.

## Memory: how many screens fit

A full-colour screen is **8000 bytes** (a 4000-byte black/white plane and a 4000-byte red plane). The firmware streams a page straight from flash to the panel, so RAM does not limit the count.

| Item | Size |
|---|---|
| Flash | 512 KiB (`0x00000000`-`0x0007FFFF`), erased in 8 KiB pages |
| Firmware (first flash page) | well under 8 KiB, reserved `0x0000`-`0x1FFF` |
| Page store | `0x2000` upward: 16-byte header, then 8000 bytes per page |
| **Full-colour pages that fit** | **64** (516 080 bytes available) |
| Black/white-only pages (4000 B each) | 129 |
| With simple run-length compression (not implemented) | several hundred for text and QR pages |
| RAM | 32 KiB, so up to 4 pages could be held in RAM, but streaming from flash needs none |

Comfortably, **a few dozen pages** is plenty: every page change is a full ~22 s refresh and a button press moves one page at a time, so cycling through more than about 8-10 is tedious. (Compression and a long-press to jump
sections would be the way to go beyond that.) The e-paper keeps its image with no power at all.

`pages.bin` layout: `b"PGS1"`, a little-endian `uint32` page count, 8 zero bytes, then the pages in order.

## Planned firmware behaviour

- Boot: draw page 1 (about 22 s); the dimmed status LED (10 %) shows work in progress.
- Button (PB03, active-low, internal pull-up, debounced): next page, wrap at the end; presses during a refresh are ignored.
- Between presses the MCU idles; the display needs no power to hold the image. Current draw of the idle loop is not measured, and a deep-sleep (EM2/EM4) button wake is a possible follow-up.
- Flash: firmware at `0x0` and `pages.bin` at `0x2000` with pyOCD (see [../docs/flashing.md](../docs/flashing.md)); the tag must already be unlocked.

## Privacy

Your name, email and phone number are only in your local config and in the flash image on your tag. Do not commit `*.local.json` or `pages.bin` (gitignored). The example config uses placeholders.
