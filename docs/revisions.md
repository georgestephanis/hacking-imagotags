# Board revisions: "HRD3-0210-A" is a label, not a board

Lots sold as **SES-imagotag HRD3-0210-A** contain different electronics. Identify yours by the PCB silkscreen (`imagotag ContRD010A`...) and the MCU marking before using anything in this repo.

| Board | MCU | Power | Status here |
|---|---|---|---|
| **ContRD010A** | Silicon Labs **EFR32FG22C121F512GM40** (QFN40, Cortex-M33). Marking `FG22 / C121GG / C0241T / 2344` | rail springs (GND, +3.3 V, signal) | **fully documented and working**: unlock, flash, display, LED, button |
| **ContRD010C** | **ESWIN EMU32VL170** (RISC-V RV32EC, 128 KB flash at `0x25000000`, J-Link supported). Marking `ESWIN EMU32VL170 -A1 A392K70102 2439AHA0`. The pin-1 dot is rotated 90° clockwise relative to rev A's. Missing the rev A diode at pads 51/52 | rail springs | **nothing here applies** (pin map, firmware, debug pads, DCI unlock, pyOCD target). Research notes: [eswin-emu32vl170-research.md](eswin-emu32vl170-research.md) |
| **BTRTx008A** | a 6 × 6 mm QFN-48 BLE-class SoC, **Qualcomm QCC710** per third-party notes (marking quoted as `QCC710 002 / BTRTx008a`, unverified by us) | **two coin cells**, no rail springs, NFC coil, PCB antenna | seen and partially traced by us, **not covered in this repo**. Same Pervasive panel and 24-pin FPC, so the display sequence in [display.md](display.md) should apply |

Do not assume the three share a debug interface or pad layout. The shared parts are the panel and the booster/FPC arrangement.

## Why this matters for other people's write-ups

- Third-party notes that attribute a **Qualcomm QCC710 / BLE ESL service** to "HRD3-0210-A" (see the further reading in the [README](../README.md#further-reading)) describe the BTRTx008A variant, not ContRD010A.
- The **E300 2.1"** tags (`EDB2-0210-A`) are another QCC710-based design with a 248 × 128 panel.
- Other Vusion/imagotag tags use yet other silicon: CC2510 (2.6" and 2.2" GL/GU boards), Axsem AX8052 (UU340), EFR32FG22 (a 7.4" `RFRTx026D` board).

## FCC filings

SES-imagotag's FCC grantee code is **2ACQM** (<https://fccid.io/2ACQM>; the fetch tools we used get 403, a browser works). 2.1" models filed include `EDB1-0210-A` (VUSION 2.1, granted 2023-08-28), `EWB1-0210-A`,
`EDG3-0210-A`, `EDB2-0210-A` (E300 2.1), `EWB2-0210-A`, `EDG5-0210-A` (V300 2.1) and `EDG6-0210-A`. We found **no filing under the model name HRD3-0210-A** itself. A TÜV test report under
`2ACQM-HRC3-BT01-A` reportedly lists HRD3-0210-A tags in its test setup with a "rail controller" running special continuous-transmit firmware; that is a lead we could not open, and it may describe the rail side of these tags.
EDB1-0210-A's public exhibits (internal photos, test setup photos, user manual, test report) show a 2402-2480 MHz radio, emission designator 1M04F1D (~1 Mbps FSK-class), 1.94 mW.
