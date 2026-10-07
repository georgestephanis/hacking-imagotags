# AGENTS.md: SES-imagotag HRD3-0210-A (ContRD010A) reverse-engineering repo

You are probably here to help someone **unlock, reflash, wire up or draw on** one of these shelf labels, or to extend what is known about the board. Read this file, then the docs it points to.
Everything here comes from real hardware work; the research log keeps the wrong turns. If you find something that contradicts a doc, trust a fresh measurement over this repo and **update the docs**.

## 0. Identify the board before doing anything

The eBay label **"HRD3-0210-A"** covers several different PCBs. Check the silkscreen and the MCU marking against [docs/revisions.md](docs/revisions.md):

- **ContRD010A, MCU `FG22 / C121GG ...` (Silicon Labs EFR32FG22, QFN40): everything in this repo applies.**
- ContRD010C (ESWIN EMU32VL170, RISC-V) and BTRTx008A (battery BLE tag, Qualcomm QCC710): **different chips; the pin map, firmware, debug pads, unlock procedure and pyOCD target do not apply.**
  The panel and its command sequence ([docs/display.md](docs/display.md)) probably do.

Ask the human for a photo of the MCU side if you cannot tell.

## 1. Ground rules (read before running anything on hardware)

1. **Never run a destructive step without the human's explicit go-ahead for that tag**: `scripts/dci.py erase` wipes the factory firmware permanently (it cannot be read out first), and flashing overwrites whatever is there.
2. **Never enable the debug lock** (DCI command `0x430C0000`). It is deliberately not implemented in `scripts/dci.py`; do not add it.
3. Power: the tag runs from **3.3 V** (never above 3.6 V on any pin). The Pico's pin 37 is `3V3_EN`, not a supply. Connect **ground first**, and solder it: a loose ground causes flaky SWD and brownout resets.
4. **PC06 (`tp-disp-pwr-en-pc06`) HIGH cuts the panel's power** and hangs the controller's power-on command. Drive it low or leave it floating.
5. Do not bridge the bare pads beside the big capacitors (original IDs `pad-front-57`/`58`): it shorted the supply once. `tp-boost-rail-a/b` may carry high voltage.
6. Several steps need a **human**: pressing BOOTSEL on the Pico, power-cycling the tag after an unlock, watching the LED or display. Ask; do not guess. The LED is **very bright**: use the dimmed firmware or leave `--led` off.
7. Only work on hardware the user owns. Do not publish or help to reproduce anything aimed at store-owned labels.

## 2. Facts you can rely on (details in docs/)

| Topic | Fact |
|---|---|
| MCU | EFR32FG22C121F512GM40, QFN40, Cortex-M33, **flash at `0x00000000`**, 512 KiB / 32 KiB RAM, ~19.1 MHz at reset. **Pin 1 = top of the left side** in `hardware/photos/mcu-side.jpg`, counter-clockwise |
| Debug | SWD: SWCLK = PA01 (`tp-swclk-pa01`), SWDIO = PA02 (`tp-swdio-pa02`), nRESET (`tp-nreset`), SWO = PA03. Factory tags are **debug-locked**; DCI device erase (`dci.py`) + a **power cycle** unlocks them |
| Display | Pervasive 2.06" BWR, UC81xx-like. **PC00 SDA, PC01 SCK, PC02 CS, PC03 D/C, PC04 RES, PA08 BUSY (low = busy), PC06 power (low = on)**. 248 × 128 visible; send 250 lines. Init: `0x01 03 00 2B 2B 03`, `0x06 17 17 17`, `0x04`, `0x00 CF`, `0x61 80 00 FA`, `0x50 77`, planes `0x10` (0 = black) and `0x13` (0 = red), `0x12` refresh (~21 s), `0x02` |
| LED | PD00 high = supply on; PB02 red, PB00 green, PB04 blue, all active-high. Dim by software PWM on PD00. **A pin left high stays on after release; drive it low to clear** |
| Button | PB03, active-low, internal pull-up |
| Springs | `spring-gnd`, `spring-vin-3v3` (centre, 3.3 V in), `spring-sig` -> PB01. Rail protocol unknown |
| NFC | coil present, **no NFC chip fitted** |
| Names | Pads are named in `hardware/netlist/contrd010a.svg` and `docs/pinout.md`; `docs/research-log.md` and old photos use the original auto-numbered IDs, mapped in `hardware/netlist/id-map.json` |

## 3. Recipes

Set up once: `scripts/setup.sh` (creates `.venv`; firmware builds also need `brew install llvm`). The Silicon Labs CMSIS pack must be downloaded **in a browser** (their server 403s scripts); or use `pyocd-target/pyocd_fg22.py`.
Detailed wiring tables are in [docs/flashing.md](docs/flashing.md) and [docs/control.md](docs/control.md).

| Goal | Do |
|---|---|
| Is the tag locked? (safe) | `.venv/bin/python scripts/dci.py status` |
| Unlock (destructive; ask first) | `dci.py erase`, then **ask the human to power-cycle**, then `dci.py status` should show the lock word `0x2` |
| Flash firmware | `pyocd flash --pack <DFP> -t efr32fg22c121f512gm40 --base-address 0 -f 1000000 -O adi.v5.max_invalid_ap_count=0 firmware/eink_receiver/receiver.bin` |
| Draw via the MCU (SWD) | `.venv/bin/python scripts/eink_draw.py IMAGE [--crop x0,y0,x1,y1] [--dither]` or `--demo`; add `--preview out.png --preview-only` to check without touching the tag |
| Draw via a Pico (MCU in reset) | wire per docs/control.md §3, flash MicroPython on the Pico (human holds BOOTSEL), `make_frame.py IMAGE frame.bin`, `mpremote cp`, `mpremote run scripts/pico_eink.py` |
| Build firmware | `python3 scripts/build_fw.py firmware/<name>/<file>.c [out.bin]`: one C file, position independent, **no globals, no const tables, no lookup-table `switch`**; flashes at `0x0` |
| Drive pins / LED | `scripts/pins.py SECONDS PD00=1 PB02=1` (host over SWD, halts the core) |
| Watch which pin follows a probe | `scripts/gpio_watch.py` |
| Restore the Pico as an SWD probe | human puts it in BOOTSEL, copy `debugprobe_on_pico.uf2` ([raspberrypi/debugprobe](https://github.com/raspberrypi/debugprobe) v2.3.1) |

## 4. Gotchas that have already cost hours

- QFN40, not QFN32. Flash base `0x0`, not `0x08000000`.
- With the lock on, normal AP reads fault ("No cores were discovered"); the DCI port (AP 1) still answers. That is expected, not a dead chip.
- SWD above ~20 kHz needs a solid ground; with one, 1 MHz is fine.
- pyOCD queues writes: read back or close the session, or a final write may never be sent.
- `scripts/eink_draw.py` halts the core; after it the tag's own firmware is not running until reset.
- The panel shows 248 of the 250 lines: a border at x = 249 will not appear.
- BUSY reads 0 before reset + power-on whatever the pull; do not wait for it to go high before the first reset.
- Holding nRESET low is what lets an external MCU drive the display lines; with the tag's firmware running they fight.
- The LED's PWM must not run inside the receiver's bit-sampling loop.
- The netlist tracing is **partial**: no connection recorded does not mean no connection (e.g. PA00 shows up on the VDD net, probably an artefact).

## 5. Open questions (good places to contribute)

The rail protocol on `spring-sig`; why the Pico-driven signal does not reach PB01 (what is the one-way element?); the "5C" diode and the transistors marked "ZV"; PA00 / PA07 / PC05 / PC07 / PD01-PD03 and the NFC footprint's use;
the 2.4 GHz antenna path and radio firmware; the ContRD010C (ESWIN) unlock and debug pads; hardware-PWM LED dimming; a clean upstream pyOCD target for the FG22.

## 6. How to extend the docs

- Put each new finding in [docs/research-log.md](docs/research-log.md) with the date, what was measured and how, and mark inferences *(unverified)*.
- Promote settled facts into [docs/hardware.md](docs/hardware.md), [docs/pinout.md](docs/pinout.md) or [docs/display.md](docs/display.md), and correct anything they replace.
- If you re-trace the board in [circuit-tracer](https://github.com/georgestephanis/circuit-tracer), note that `tools/rename_netlist.py` maps the **original auto-numbered IDs** of the current export (`tp-back-18` and so on): a fresh trace has new auto IDs, so update its mapping tables first. Then run `tools/make_annotated_images.py` to refresh the annotated photos.
- New source files get an `SPDX-License-Identifier: GPL-2.0-or-later` header (the Apache-2.0 exception is `pyocd-target/` only, which is meant to go upstream to pyOCD).
- Do not commit third-party artwork you draw on the panel, and do not commit vendor firmware dumps.
