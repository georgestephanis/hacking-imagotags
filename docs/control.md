# Ways to control a ContRD010A tag

All of these assume the tag has been unlocked and (for 2 and 3) flashed, see [flashing.md](flashing.md). Pins and pads: [pinout.md](pinout.md).

| # | Method | Needs | Status |
|---|---|---|---|
| 1 | Host drives the MCU's GPIOs over SWD | SWD probe, no firmware | works |
| 2 | Your own firmware on the EFR32 | SWD probe, LLVM | works (LED, button, display); rail receiver untested |
| 3 | An external MCU drives the panel through the display test points | Pico/ESP32 + 7 wires, MCU held in reset | works |
| 4 | Drive the panel from its FPC with a breakout | FPC breakout, booster | not built, plan in [epaper-breakout-plan.md](epaper-breakout-plan.md) |
| 5 | The original rail protocol | a rail, or a logic analyser on one | unknown |
| 6 | NFC / BLE | NFC IC (not fitted) / radio firmware | not done |

## 1. Host-driven over SWD (no firmware needed)

The host halts the core and bit-bangs the MCU's GPIO registers through the debug port (`scripts/swdburst.py`, ~16k writes/s).

```bash
.venv/bin/python scripts/eink_draw.py --demo                           # draws a test card (~35 s)
.venv/bin/python scripts/eink_draw.py picture.jpg --crop x0,y0,x1,y1 --dither
.venv/bin/python scripts/eink_draw.py --demo --preview p.png --preview-only   # no tag needed
.venv/bin/python scripts/pins.py 8 PD00=1 PB02=1                       # drive pins for 8 s: PD00+PB02 = red LED
```

The image is fitted to 248 × 128 and quantised to black, white and red. `--led` shows progress on the LED but **cannot dim it** (leave it off; the core is halted so there is no PWM).
Other tools: `button_watch.py`, `gpio_watch.py` (which pin follows something you wiggle), `gpio_scan.py`, `disp_probe.py`, `eink_uc81.py` (display bring-up patterns), `signal_test.py`.

## 2. Your own firmware on the EFR32

`scripts/build_fw.py` compiles **one C file** with Homebrew LLVM (Cortex-M33), extracts the code, and prepends a vector table. There is no linker, so the program must be
**position independent with no global data and no constant tables** (no `static` arrays, no `switch` that the compiler turns into a lookup table, no string literals). Use absolute
addresses for RAM buffers; the stack is at the top of the 32 KiB RAM. The image is flashed at `0x00000000`.

```bash
python3 scripts/build_fw.py firmware/led_brightness/led.c firmware/led_brightness/led.bin
```

| Firmware | What it does |
|---|---|
| `firmware/led_demo` | button-cycled red -> green -> blue -> off |
| `firmware/led_brightness` | green at 100 / 60 / 40 / 25 / 10 % duty, 3 s each (the test that picked 10 %) |
| `firmware/eink_receiver` | boots (dim green blink), then waits for an image frame on PB01 (the signal contact), draws it, and blinks the result (red = bad frame, green = done) |

**LED dimming.** The LED has one supply switch (PD00) for all three colours, so brightness is software PWM on PD00: ~1.16 kHz (period 2^14 cycles of the ~19 MHz clock), 10 % duty. `led_tick()` in
`receiver.c` does it and must be called often wherever timing is not critical (delays, BUSY waits, the plane upload). **The receive loop does not tick** (it would disturb bit sampling), so the LED is off while receiving.
Hardware PWM through the TIMER peripheral and GPIO routing would be cleaner but was not tried.

**Image over the rail signal contact** (`receiver.c`, `scripts/send_image.py`): a software UART receiver on PB01 with auto-baud (~2400-230400 baud 8N1). Frame: `0x55` sync, `A5 5A`, 8000 payload bytes
(black/white plane 4000 + red plane 4000), CRC-16/CCITT-FALSE (hi, lo); only a good CRC triggers the refresh. **Not working end to end yet:** a Pico pin wired to the spring contact does not reach PB01
(the contact sits at ~2.25 V under load and the one-way stage leaves PB01 below its input threshold). Next steps: bypass test with the sender on `tp-sig-pb01`, then a 3.3 V buffer (74LVC1G125) at the contact.

## 3. An external MCU drives the panel directly (tested with a Pico)

The seven display signals are available at test points on the right side of the coil side; they also reach the EFR32's pads, which are high-impedance while it is **held in reset**.
So an external MCU can drive the panel with the tag's own booster and the same command sequence.

| Tag test point | Signal | Pico GPIO (pin) |
|---|---|---|
| `tp-disp-pwr-en-pc06` | panel power path (drive low) | GP16 (21) |
| `tp-disp-cs-pc02` | CS | GP17 (22) |
| `tp-disp-sck-pc01` | SCK | GP18 (24) |
| `tp-disp-sda-pc00` | SDA / MOSI | GP19 (25) |
| `tp-disp-dc-pc03` | D/C | GP20 (26) |
| `tp-disp-res-pc04` | RES | GP21 (27) |
| `tp-disp-busy-pa08` | BUSY (low = busy) | GP22 (29) |
| `tp-nreset` | tag nRESET, **hold low** | GP1 (2) |
| `tp-gnd-*` | ground | GND (23, 28 or 38) |
| `spring-vin-3v3` / `tp-vin-3v3-*` | +3.3 V | 3V3(OUT) (36) |

GP17-GP19 are the Pico's hardware SPI0. Put **~330 Ω in series with each Pico-driven line** (the tag's rail is ~2.9 V and the Pico drives 3.3 V). The PC06 wire is optional: the panel works with PC06 floating when the MCU is in reset.

The Pico must run something that can drive GPIOs: the debugprobe firmware cannot. Flash MicroPython (hold BOOTSEL while plugging in, copy `RPI_PICO-*.uf2` to `RPI-RP2`), then:

```bash
.venv/bin/pip install mpremote
.venv/bin/python scripts/make_frame.py --demo-pico frame.bin --preview preview.png
# or:   make_frame.py photo.jpg frame.bin --dither
.venv/bin/mpremote cp frame.bin :frame.bin
.venv/bin/mpremote run scripts/pico_eink.py        # ~22 s, prints "refresh took ... ms"
```

To use the Pico as an SWD probe again, put it back in BOOTSEL and flash `debugprobe_on_pico.uf2` (a running debugprobe cannot reboot itself into BOOTSEL). The same wiring works from an ESP32 or any 3.3 V MCU; port `scripts/pico_eink.py`'s command sequence.

## 4. From the FPC

Unplug the flex from the tag and use a 24-pin 0.5 mm FPC breakout. You then supply the booster yourself (Pervasive's reference: 10 µH inductor, MCH3478 MOSFET, three SS2040FL Schottky diodes, 0.47 Ω sense resistor,
4.7 µF + 1 µF/25 V capacitors); the tag's own booster is the easier source of those parts. See [epaper-breakout-plan.md](epaper-breakout-plan.md) and [display.md](display.md).

## 5. The rail protocol

Unknown. The signal contact idles at ~0 V (pulled down on the tag) and reaches PB01 (deep-sleep wake). Capture it on a real rail with a logic analyser (an untouched tag and a store rail or a gateway are needed)
before writing a receiver for it. [The FCC filings](../README.md#further-reading) for these tags describe the 2.4 GHz radio, not the rail.

## 6. NFC and radio

There is no NFC chip. The footprint's data pins are PA05 and PD03; an I2C NFC tag IC such as NXP NT3H2111 or ST25DV is the likely populated variant *(unconfirmed)*. The EFR32FG22 has a 2.4 GHz radio (BLE and proprietary), but
RF2G4_IO (pin 14) and its matching network were not traced and no radio firmware has been tried; Silicon Labs' Simplicity SDK would be the starting point.
