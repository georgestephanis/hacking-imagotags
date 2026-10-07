# The e-paper panel

A **Pervasive Displays 2.06" three-colour (black/white/red)** panel family part (stickers `E2206…JS…E1`; the red `J` variant is not in Pervasive's public product table, only the BW `E2206KS0E1`
and a four-colour model are, so the identification rests on size, resolution and behaviour). Public facts for the family
(<https://www.pervasivedisplays.com/products/2-06-e-ink-displays/>): **248 × 128 pixels, 0.1875 mm pitch (135 dpi), active area 46.5 × 24.0 mm, module 57.75 × 29.5 × 0.85 mm**,
internal driving with an embedded waveform, a-Si TFT, SPI. A product specification for the BW sibling with the FPC pinout and reference booster circuit is on Mouser
(`1Pxxx_00_tentative_E2206KS0E1_20230901.pdf`; fetch it in a browser).

## Interface

24-pin 0.5 mm FPC, standard e-paper layout: SPI (SCLK, SDIN, CS, D/C), RES, BUSY_N, and the booster pins (GDR, RESE, VSH/VSL/VGH/VGL, VCOM). The booster components are on the tag board.
On the tag the 7 signals below are reachable at the test points. **The panel's BS pin must be grounded for 4-wire SPI** (it is, on the tag).

| Signal | MCU pin | Test point | Notes |
|---|---|---|---|
| SDA (MOSI) | PC00 | `tp-disp-sda-pc00` | |
| SCK | PC01 | `tp-disp-sck-pc01` | SPI mode 0, MSB first; 500 kHz works from a Pico |
| CS | PC02 | `tp-disp-cs-pc02` | CS and D/C look interchangeable for commands; data frames tell them apart |
| D/C | PC03 | `tp-disp-dc-pc03` | low = command, high = data |
| RES | PC04 | `tp-disp-res-pc04` | active low reset |
| BUSY | PA08 | `tp-disp-busy-pa08` | **low = busy**; the panel holds it low until reset + power-on |
| power path | PC06 | `tp-disp-pwr-en-pc06` | **drive LOW (or float) = panel powered; HIGH hangs the power-on command** |

## Geometry and data

- The controller is driven with **250 lines × 128 rows**, but only **248 columns are visible**: lines 248 and 249 (the connector end, on the right when the connector is at the right) are not shown.
  Anything drawn at x = 249 (a 1 px border, say) is lost, so compose images at 248 wide and pad with white.
- Orientation with the connector on the right: **x = line index 0..249 left to right, y = row 0..127 bottom to top.** 16 bytes per line, 250 lines = 4000 bytes per plane.
- Two planes: **`0x10` = black/white (bit 0 = black, 1 = white)**; **`0x13` = red (bit 0 = red, 1 = no red)**. Send both before refreshing.
- Dmitry GR's notes on UC8151c panels (see [further reading](../README.md#further-reading)) say black and red data must be sent in separate passes for finer waveform work; for plain three-colour drawing one pass of each plane is enough.

## Command sequence that works

Controller behaves like **UC8151 / UC81xx (BWR)**:

| Step | Command | Data |
|---|---|---|
| reset | RES low 20 ms, high, wait 100 ms | |
| power setting | `0x01` | `03 00 2B 2B 03` |
| booster soft start | `0x06` | `17 17 17` |
| power on | `0x04` | then wait for BUSY high (~70 ms) |
| panel setting | `0x00` | **`CF`** (`0F` gave partial, faded updates) |
| resolution | `0x61` | `128, 0, 250` |
| VCOM / data interval | `0x50` | `77` |
| black/white plane | `0x10` | 4000 bytes |
| red plane | `0x13` | 4000 bytes |
| refresh | `0x12` | BUSY low for ~18-22 s |
| power off | `0x02` | wait for BUSY high |

Implementations: [`scripts/eink_draw.py`](../scripts/eink_draw.py) (host drives the MCU's pins over SWD), [`firmware/eink_receiver/receiver.c`](../firmware/eink_receiver/receiver.c) (on the MCU),
[`scripts/pico_eink.py`](../scripts/pico_eink.py) (MicroPython on a Pico, direct SPI). A full refresh takes **~21.6 s** in all three.

## Behaviour worth knowing

- E-paper keeps its image with no power. The factory image ("BREZZA INSTANT WMR $49.97 ...") was still on the glass of the first tag.
- The controller's frame memory survives a hardware reset and power-off: a refresh with no new data re-shows the last upload, with black/red inverted relative to what was sent.
- The border drives red on this three-colour panel (a quick way to confirm a BWR panel).
- Do not poll BUSY before reset + power-on: it reads 0 whatever the pull-up (the panel drives it low).

## Replacing the MCU's role with another controller

- **From the FPC side:** a 24-pin 0.5 mm FPC breakout (Good Display DESPI-C02, Waveshare universal raw-panel driver board) plus the booster circuit. Notes and the panel's reference circuit are in [epaper-breakout-plan.md](epaper-breakout-plan.md).
  The FPC fingers face the board on the tag; the pin order mirrors if you flip the flex.
- **From the test points:** hold the tag's MCU in reset and drive the 7 test points, see [control.md](control.md).
