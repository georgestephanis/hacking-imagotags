# Unlocking and flashing the EFR32FG22 on a ContRD010A tag

> **This destroys the tag's original firmware, permanently.** The factory image is debug-locked and cannot be read out; the only way in is a device erase.
> Only do this to tags you own. Expect to sacrifice the first tag while you learn.

## What you need

- A **CMSIS-DAP SWD probe**. Tested: a **Raspberry Pi Pico running `debugprobe_on_pico.uf2`** ([raspberrypi/debugprobe](https://github.com/raspberrypi/debugprobe) release `debugprobe-v2.3.1`). Silicon Labs' own 8-bit "USB Debug Adapter" cannot do SWD.
- A 3.3 V supply (the Pico's 3V3(OUT)), a ground, and four thin wires or probe pins. **Solder the ground**: a loose ground gave flaky SWD and brownout resets.
- Python 3, a virtualenv (`scripts/setup.sh`), and for building firmware Homebrew LLVM (`brew install llvm`).
- The debug pads are on the coil / test-pad side, **under the e-paper**. The panel's flex lets you fold it back while it stays connected.

## Wiring (Pico debugprobe)

| Pico pin | Signal | Tag pad |
|---|---|---|
| 4 (GP2) | SWCLK | `tp-swclk-pa01` |
| 5 (GP3) | SWDIO | `tp-swdio-pa02` |
| 2 (GP1) | nRESET | `tp-nreset` |
| 36 (3V3 OUT) | +3.3 V | **`spring-vin-3v3` (centre spring)** or `tp-vdd-2`. **Never Pico pin 37 (3V3_EN).** |
| 38 (GND) | GND | `tp-gnd-2` and/or `spring-gnd` |

![debug pads](images/test-pad-side.png)

## 1. Set up the host

```bash
scripts/setup.sh                       # .venv with pyOCD, Pillow, pyserial
.venv/bin/pyocd list                   # expect "Raspberry Pi Debugprobe on Pico (CMSIS-DAP)"
```

Silicon Labs' CMSIS pack must be downloaded **in a browser** (their server returns 403 to scripts): from
<https://www.silabs.com/support/resources.ct-software_cmsis-packs> get `SiliconLabs.GeckoPlatform_EFR32FG22_DFP.<version>.pack` (tested: `2025.12.1`).
Alternatively use the in-repo target that needs no pack: [`pyocd-target/`](../pyocd-target/README.md) (`pyocd_fg22.py`).

## 2. Check the lock (read-only)

```bash
.venv/bin/python scripts/dci.py status
```

A factory tag answers (DPIDR `0x6ba02477`, DCIID `0xdc11d`) and reports `debug lock hw status: LOCKED`, `secure debug: ENABLED`, `device erase allowed: yes`
(SESTATUS words `[0x20, 0x101020c, 0xffffffff, 0x27, 0xffffffff]`). While locked, every normal AP read faults (pyOCD says "No cores were discovered"); that does not mean the chip is dead.
Details and register facts: [debug-unlock.md](debug-unlock.md).

## 3. Erase and unlock (destructive)

```bash
.venv/bin/python scripts/dci.py erase
```

The secure element answers with length word `0x4` and the link then drops: normal. **Power-cycle the tag** (pull the 3.3 V wire and reconnect it; nRESET alone is not enough), then:

```bash
.venv/bin/python scripts/dci.py status      # expect debug lock word 0x2, "unlocked"
```

## 4. Flash

```bash
PK=~/Downloads/SiliconLabs.GeckoPlatform_EFR32FG22_DFP.2025.12.1.pack
.venv/bin/pyocd flash --pack $PK -t efr32fg22c121f512gm40 --base-address 0 -f 1000000 \
    -O adi.v5.max_invalid_ap_count=0 firmware/eink_receiver/receiver.bin
.venv/bin/pyocd commander --pack $PK -t efr32fg22c121f512gm40 -f 1000000 \
    -O adi.v5.max_invalid_ap_count=0 -c "reset" -c "status"       # "Running [Secure]"
```

The shipped `receiver.bin` blinks the LED dimly green at boot. To build your own, see [control.md](control.md) (`scripts/build_fw.py`).
`-O adi.v5.max_invalid_ap_count=0` only hides a harmless "Error probing AP#3" line.

## Gotchas that cost time

- **QFN40, not QFN32.** **Flash starts at `0x00000000`** on the FG22 (the FG23 uses `0x08000000`).
- **SWD is flaky above ~20 kHz with a poor ground**; with a solid ground 1 MHz is fine (`scripts/connect.sh` uses 20 kHz and retries).
- A debug-lock erase only takes effect after a **power cycle**.
- pyOCD queues register writes: a script that ends on a write may not flush it. Read back or close the session.
- A short debugger session halts the core and lowers its current draw, so voltages measured while halted are higher than when firmware runs.
- The pyOCD pack index lists the Silicon Labs pack but `pack install` finds nothing; use `--pack` with the manually downloaded file. Reported upstream: <https://github.com/pyocd/pyOCD/issues/2042>.
- Do **not** run the DCI "enable debug lock" command (`0x430C0000`); `dci.py` has no mode for it on purpose.
- Revision **ContRD010C** has a different MCU (ESWIN EMU32VL170, RISC-V); none of this applies. See [revisions.md](revisions.md).

## Going back to the factory state

There is no way back: the original firmware cannot be dumped from a locked part. Keep one untouched tag if you want to study its behaviour on a rail.
