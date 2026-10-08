# nametag: a standalone name badge on the ContRD010A tag

Turns a tag into a wearable name badge that runs from a 3.3 V supply with no host: **page 1** shows a name, email and phone number; **a short press of the button** (the one on the back, PB03) moves to the next page,
and the last wraps round to the first, while a **long press** (hold for about a second) jumps straight back to page 1. The other pages are **QR-code pages**: a smaller name, a red arrow pointing at the code, and a caption under the arrow (a website's domain, or "Venmo" / "Cash App" with the handle).
Pages are defined in a config file, so adding one is a line of JSON.

> Status: the page generator, layouts and **firmware** are written (`nametag.c`, `nametag.bin`, 1.9 KB). Your details live in a local config that is kept out of git (see below).

## Make the pages

```bash
cp nametag/nametag.example.json nametag/mine.local.json      # *.local.json is gitignored; edit it
python3 nametag/make_pages.py nametag/mine.local.json        # needs: pip install pillow segno
```

Output (in `./nametag-out/`): `page1.png`, `page2.png` (4x previews of exactly what the panel will draw, red header and rule = red ink) and `pages.bin` (the flash image).

- Config keys: `name`, `email`, `phone`, and `pages`, a list of `{"type": "contact"}` or `{"type": "qr", "url": ..., "caption": [...]}` (see `nametag.example.json`). Without `pages` you get a contact page and one QR page for a `url`.
- For each URL the generator tries error-correction levels Q, M and L and keeps the combination with the **largest whole-pixel module size** (ties go to the stronger level), because a bigger module scans more reliably than extra error correction on a clean e-paper.
  For example a 20-character URL is version 2 at level Q (25 × 25 modules, 100 px); a 44-character Venmo URL is version 3 at level L (29 × 29 modules, 116 px); a Cash App URL is version 3 at level M. At 4 px per module a code is about 19-22 mm wide on the panel.
  Keep URLs short: each extra step in size shrinks the module or the code. The generator checks nothing about scanning, so test each code with a phone (we also decoded every page with OpenCV).
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

## Firmware behaviour (`nametag.c`)

- Boot: draw page 1 (about 22 s); the dimmed status LED (10 %) shows work in progress.
- Button (PB03, active-low, internal pull-up, debounced about 30 ms):
  - **short press** (released in under 1 s): next page, wrapping from the last to the first;
  - **long press** (held for 1 s, recognised while still held, with a brief dim LED flash as acknowledgement): back to page 1 (nothing happens if page 1 is already showing);
  - the hold time is one constant in the firmware (`LONG_PRESS_MS`, default 1000);
  - presses **during a refresh are ignored** (a refresh takes about 22 s and the MCU is busy), and a button still held when the refresh ends is not counted; release it and press again.
- Between presses the MCU idles; the display needs no power to hold the image. Current draw of the idle loop is not measured, and a deep-sleep (EM2/EM4) button wake is a possible follow-up.
- Flash: `nametag/flash.sh PATH/TO/DFP.pack` puts the firmware at `0x0` and `nametag-out/pages.bin` at `0x2000` with pyOCD (wiring and unlocking: [../docs/flashing.md](../docs/flashing.md)); the tag must already be unlocked.
- Build the firmware with `python3 scripts/build_fw.py nametag/nametag.c nametag/nametag.bin` (needs Homebrew LLVM). Without `pages.bin` flashed, the LED blinks red.
- Powering the finished badge: 3.3 V on the centre spring (`spring-vin-3v3`) and ground on `spring-gnd`, no probe attached.

## Privacy

Your name, email and phone number are only in your local config and in the flash image on your tag. Do not commit `*.local.json` or `pages.bin` (gitignored). The example config uses placeholders.
