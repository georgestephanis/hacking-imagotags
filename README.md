# hacking-imagotags

Reverse engineering and re-flashing **SES-imagotag / VusionGroup "HRD3-0210-A" electronic shelf labels** (PCB `ContRD010A`, EFR32FG22 MCU, 2.06" three-colour e-paper), the kind that turn up in
20-packs on eBay still showing their factory barcode. This repo documents the board, how to unlock and flash it, every pin we have mapped, and several ways to draw on the display.

> Status: **working**. Unlock, flash, draw images three different ways, run the LED (dimmed) and read the button. Not working yet: receiving images over the rail's signal contact.
> Work done on tags I own. Retail shelf labels in stores belong to the retailer; do not touch those. Tags from eBay may differ internally, see [Revisions](docs/revisions.md).

![coil / test-pad side, with named test points](docs/images/test-pad-side.png)

![MCU side](docs/images/mcu-side.png)

## What the tag is

| | |
|---|---|
| MCU | Silicon Labs **EFR32FG22C121F512GM40** (Cortex-M33, 512 KiB flash at `0x0`, 32 KiB RAM, 2.4 GHz radio). Ships **debug-locked**, cleared by a device erase (original firmware is lost) |
| Panel | Pervasive Displays 2.06" family: **248 × 128, black/white/red**, UC81xx-style controller, 24-pin FPC, ~21 s full refresh |
| Power | three spring contacts (GND / **+3.3 V** / signal), no battery |
| Extras | RGB LED (painfully bright at full duty), one button (PB03), a printed NFC coil with **no NFC chip fitted** |
| Debug | SWD on test pads under the e-paper (fold the flex back): `tp-swclk-pa01`, `tp-swdio-pa02`, `tp-nreset` |

Full reference: [docs/hardware.md](docs/hardware.md), [docs/pinout.md](docs/pinout.md), [docs/display.md](docs/display.md).

## Quick start

1. **Check which board you have**: the silkscreen should read `ContRD010A` and the MCU marking `FG22 / C121GG`. Other boards sold under the same label differ: [docs/revisions.md](docs/revisions.md).
2. **Wire an SWD probe** (a Raspberry Pi Pico running debugprobe works) to the three debug pads plus 3.3 V and a *soldered* ground: [docs/flashing.md](docs/flashing.md).
3. **Unlock and flash**:
   ```bash
   scripts/setup.sh
   .venv/bin/python scripts/dci.py status        # LOCKED on a factory tag
   .venv/bin/python scripts/dci.py erase         # DESTRUCTIVE; then power-cycle the tag
   .venv/bin/pyocd flash --pack <Silicon Labs EFR32FG22 DFP .pack> -t efr32fg22c121f512gm40 --base-address 0 -f 1000000 firmware/eink_receiver/receiver.bin
   ```
4. **Draw something** (three ways, all ~21 s per refresh): [docs/control.md](docs/control.md)
   ```bash
   .venv/bin/python scripts/eink_draw.py --demo                         # 1. host bit-bangs the MCU's pins over SWD
   # 2. your own firmware on the EFR32 (scripts/build_fw.py, firmware/)
   # 3. a Pico drives the panel directly through the display test points, MCU held in reset
   .venv/bin/python scripts/make_frame.py photo.jpg frame.bin --dither && .venv/bin/mpremote cp frame.bin :frame.bin && .venv/bin/mpremote run scripts/pico_eink.py
   ```

## Ways to control it

| Method | Needs | Status |
|---|---|---|
| Host drives the MCU's GPIOs over SWD (`scripts/eink_draw.py`) | SWD probe | works |
| Custom firmware on the EFR32 (`firmware/`, `scripts/build_fw.py`, in-repo pyOCD target) | SWD probe, LLVM | works |
| External MCU (Pico) drives the panel through 7 test points (`scripts/pico_eink.py`) | Pico + 7 wires | works |
| Image over the rail signal contact (software UART on PB01) | sender that can drive the contact | written, **not working end to end** |
| Panel from its FPC with a breakout | FPC breakout + booster | planned |
| Original rail protocol, NFC, BLE | - | unknown / not done |

## Repository map

```
AGENTS.md          read this first if you are an AI agent (or want the short version of the rules)
docs/              hardware.md, pinout.md, display.md, flashing.md, control.md, revisions.md,
                   debug-unlock.md, epaper-breakout-plan.md, eswin-emu32vl170-research.md, research-log.md, images/
hardware/          photos/ (raw), netlist/ (traced SVG with named pads, netlist JSON, old->new id map)
firmware/          eink_receiver (draws frames received on PB01), led_demo, led_brightness  (source + .bin)
scripts/           SWD tooling (dci.py, eink_draw.py, pins.py, ...), Pico driver (pico_eink.py), frame builder (make_frame.py), build_fw.py
pyocd-target/      flash algorithm + pyOCD target for the EFR32FG22 (works without Silicon Labs' pack)
tools/             rename_netlist.py, make_annotated_images.py
```

## Further reading

Nothing below documents the ContRD010A directly; these are the closest write-ups and the ones that taught us the most. **Entries marked ⭐ concern this model name, this MCU or this panel family.**

### About this model, MCU or panel family

- ⭐ **TenOfNine, [imagotag-vusion-esl-reverse-engineering](https://github.com/TenOfNine/imagotag-vusion-esl-reverse-engineering)**: a VusionGroup `RFRTx026D` tag with the **same EFR32FG22** MCU (marking `FG22 / C121GG`), a 7.4" three-colour panel and a 24-pin FPC. SPI captures and tooling; docs in German.
- ⭐ **dbzx6r, [walmart-esl-flipper](https://github.com/dbzx6r/walmart-esl-flipper)** (`docs/VUSION_ESL.md`): names the **HRD3-0210-A** and describes a BLE tag with a Qualcomm QCC710 (BT SIG Electronic Shelf Label service, UUID `0x184D`). The chip marking it quotes (`QCC710 002 | BTRTx008a`) is the **BTRTx008A** variant, **not ContRD010A**; its claims are untested by us. See [docs/revisions.md](docs/revisions.md).
- ⭐ **Night-Traders-Dev, [SES-imagotag](https://github.com/Night-Traders-Dev/SES-imagotag)**: the **E300 2.1"** (`EDB2-0210-A`), Qualcomm QCC710, 248 × 128 panel, CR2477 cell. Same panel size class, different MCU.
- ⭐ **Pervasive Displays 2.06" family**: [product page](https://www.pervasivedisplays.com/products/2-06-e-ink-displays/) (248 × 128, 46.5 × 24.0 mm) and the `E2206KS0E1` specification (FPC pinout, reference booster circuit; on Mouser). Our red variant is not in the public table.
- ⭐ **FCC grantee [2ACQM](https://fccid.io/2ACQM)** (SES-imagotag): filings for the 2.1" family (`EDB1-0210-A`, `EDB2-0210-A`, ...); a test report under `2ACQM-HRC3-BT01-A` reportedly lists HRD3-0210-A tags with a rail controller. We could not open it (403); worth a look in a browser.
- ⭐ **shanislav, [GxEPD2_PervasiveDisplays](https://github.com/shanislav/GxEPD2_PervasiveDisplays)**: GxEPD2 driver classes for Pervasive/VUSION three-colour panels (other sizes).

### Other imagotag / Vusion tags (different MCUs)

- **Andrei Tatar, [imagotag-hack](https://github.com/andrei-tatar/imagotag-hack)**: 2.6"/2.2" BWR GL120 (CC2510, IL0373 panel, NT3H2111 NFC, W25X10CL flash). Pin map and datasheets. Its panel power is an active-low P-FET enable, like our PC06 power path.
- **Jirka Balhar, [Hacking SES imagotag E-ink Price Tag](https://blog.jirkabalhar.cz/2023/12/hacking-sesimagotag-e-ink-price-tag/)**: VUSION 2.6 BWR GU140 (CC2510, Pervasive `E2266JS0C2` panel); CC2510 removed and replaced by an RP2040-Zero. Different board from ours.
- **Jasper Devreker (Zeus WPI), [Reverse engineering e-paper tags](https://zeus.ugent.be/blog/22-23/reverse_engineering_epaper/)**: a G1 2.7" BW NFC tag with a debug-locked CC2510, dumped by **voltage glitching** with a Pico ([ZeusWPI/pico-glitcher](https://github.com/ZeusWPI/pico-glitcher)). Useful contrast: the EFR32FG22 needs no glitching because Silicon Labs allows a device erase.
- **BeatSkip, [SES-Imagotag-UU340](https://github.com/BeatSkip/SES-Imagotag-UU340)** (Axsem AX8052), [Axsem-sdcc-helloworld](https://github.com/BeatSkip/Axsem-sdcc-helloworld), [ESL-Modding](https://github.com/BeatSkip/ESL-Modding).
- **NLTD2010, [Imagotag-SES](https://github.com/NLTD2010/Imagotag-SES)** (CC2510 + GDEW0213Z16 + NT3H2111), **18nelli18, [Monopink](https://github.com/18nelli18/Monopink)** (flash the CC2510 of a VUSION 2.6 BWR GL420 with a Pico, no desoldering),
  **angrymew, [firmware-cc2510](https://github.com/angrymew/firmware-cc2510)**, **prime-axiom, [gl440-client-firmware](https://github.com/prime-axiom/gl440-client-firmware)**,
  **H0nz4k, [OpenVusion](https://github.com/H0nz4k/OpenVusion)** and **[VusionTagHwHack](https://github.com/H0nz4k/VusionTagHwHack)**, **Inkapa, [esl](https://github.com/Inkapa/esl)** (168 × 384 tri-colour panel on a Pi),
  **takizawaskyline, [GTag6](https://github.com/takizawaskyline/GTag6)**.

### General e-paper price-tag hacking

- **Dmitry Grinberg, [Hacking eInk Price Tags](https://dmitry.gr/?r=05.Projects&proj=29.%20eInk%20Price%20Tags)**: dumping and replacing firmware on several tags, and a detailed account of UC8151c / SSD1675 waveforms, greyscale and three-colour quirks.
- **Aaron Christophel (atc1441), [E-Paper_Pricetags](https://github.com/atc1441/E-Paper_Pricetags)** (incl. an Imagotag G1 4.4" BWR with an ESP32), [OpenEPaperLink](https://github.com/jjwbruijn/OpenEPaperLink) and his [Universal E-Paper Sniffer](https://hackaday.com/2022/06/15/a-handy-breakout-board-for-e-paper-hacking/), a bare 24-pin FPC passthrough for tapping panel traffic.
- Hackaday: [Driving three-colour e-paper pricetags with an Arduino](https://hackaday.com/2022/10/28/driving-three-color-e-paper-pricetags-with-an-arduino/), [Reverse engineering e-ink price tags](https://hackaday.com/2023/02/11/reverse-engineering-e-ink-price-tags/), [A deep dive into e-ink tag hacking](https://hackaday.com/2021/03/28/a-deep-dive-into-e-ink-tag-hacking/).
- **[hsbp.org/ePaper](https://hsbp.org/ePaper)**: a link collection (the pages above plus [epdiy](https://github.com/vroland/epdiy), an open e-paper driver library, and a [FricklePaper wiki page](https://wiki.section77.de/projekte/fricklepaper/einstieg) that did not load for us).
- **Silicon Labs** EFR32FG22 data sheet and AN1190 (Series 2 secure debug); **raspberrypi/[debugprobe](https://github.com/raspberrypi/debugprobe)**; **[pyOCD](https://github.com/pyocd/pyOCD)** (our [upstream report](https://github.com/pyocd/pyOCD/issues/2042) about the missing pack index entries).

## Contributing

Corrections and new findings welcome, especially: the rail protocol, other `ContRD` / `HRD3` revisions, the ContRD010C (ESWIN) debug story, radio firmware for the FG22, and a hardware-PWM LED dimmer.
Keep claims honest: mark inferences as *unverified* and add what you measured to [docs/research-log.md](docs/research-log.md).

## License

Copyright (C) 2026 George Stephanis. Licensed under the **GNU General Public License, version 2 or (at your option) any later version** (`GPL-2.0-or-later`, see [`LICENSE`](LICENSE)).
That covers the code, firmware, documentation, photos and netlists: if you build on this, share your changes under the same terms.

The exception is [`pyocd-target/`](pyocd-target/), which is **Apache-2.0** ([`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)) so it can be contributed upstream to pyOCD. Every source file carries an SPDX header saying which applies.
Apache-2.0 is compatible with GPLv3, which the "or later" clause lets you choose.

## AI disclosure

This project was done by George Stephanis **together with Claude Sonnet 5.5** (`claude-sonnet-5-5`, Anthropic), working in Claude Code, over **three calendar days (5-7 October 2026)**.
It was one long, continuing conversation, not a one-shot generation.

**Who did what.** George sourced the tags, soldered, probed with a multimeter, photographed the boards, traced the PCB pad by pad in
[circuit-tracer](https://github.com/georgestephanis/circuit-tracer), and did every physical step (wiring the probe, BOOTSEL, power-cycling, watching the LED and display and reporting what happened).
Claude researched, wrote the scripts, firmware and docs, ran the SWD and pyOCD tooling against the real tags, analysed the traced netlist, designed the experiments, renamed the pads, produced the annotated photos and assembled this repository.

**Time.** About **17 hours of wall-clock time** between the first and last activity of each day (roughly 9.5 h on 5 Oct, 6 h on 6 Oct, 1.7 h on 7 Oct), of which I estimate **around 10 hours of active hands-on work**.
Those figures come from the session timestamps and commit history, not a stopwatch. They undercount the human side: soldering, probing and tracing the board happen off-screen.
Two tags were used (the first was unlocked and flashed as a sacrificial unit; the second repeated the procedure and added the dimmed LED, the 248-column fix and the direct Pico drive).

**How far to trust it.** Anything described as working was run on real hardware. Inferences are marked *(unverified)*. The raw [research log](docs/research-log.md) keeps the wrong turns (for example the QFN32 pin-map assumption, the CS/DC swap, the inverted LED polarity),
which is why it is long. An AI can be confidently wrong, so check anything that could harm hardware (voltages, which pad is which) against your own board before powering it.
Corrections are welcome.
