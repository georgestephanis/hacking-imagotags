# Series 2 debug lock: status check and device erase

Applies to EFR32FG22 (and other Series 2). Reference: Silicon Labs AN1190 (Series 2 Secure Debug) and AN1303,
and the `knieriem/openocd-efm32-series2` openocd config (`efm32s2.cfg`), from which the register facts below were taken.
`scripts/dci.py` implements this on a pyOCD CMSIS-DAP probe.

## Why normal access fails when locked

Debug lock leaves the SW-DP alive (DPIDR `0x6BA02477`, CTRL/STAT power-up acks `0xF0000000`) but the AHB-AP faults.
pyOCD reports "No cores were discovered" / "No ACK" on AP reads. That does **not** mean the chip is dead.

## The DCI access port

Series 2 puts lock/erase on its own AP, index **1** (the "DCI").

Sequence (all via the DP/AP of the probe):

1. SWJ line reset + JTAG→SWD sequence, read DPIDR, expect `0x6BA02477`.
2. `DP ABORT = 0x1E`, `DP CTRL/STAT = 0x50000000` (power up).
3. `DP SELECT = 0x01000000` (APSEL 1, bank 0).
4. `AP CSW (0x00) = 0x22000002`.
5. Read DCIID: `AP TAR (0x04) = 0x10FC`, read `AP DRW (0x0C)`, then `DP RDBUFF (0x0C)`. Expect `0x000DC11D`.

DCI registers (set via TAR, access via DRW):

| TAR | Register |
|---|---|
| `0x1000` | DCIWDATA (write command words) |
| `0x1004` | DCIRDATA (read response words) |
| `0x1008` | DCISTATUS: bit0 = WPENDING, bit8 (`0x100`) = RDATAVALID |
| `0x10FC` | DCIID |

Before writing, poll DCISTATUS until WPENDING = 0 and RDATAVALID = 0. Before reading, wait for RDATAVALID.

## Commands (each: write length word `8`, then the command word)

| Command word | Meaning |
|---|---|
| `0xFE010000` | Read SE status. Response: length word (`0x18` here), then status words. Debug-lock word is index 3 (index 7 if length is `0x28`). |
| `0x430F0000` | **Device erase** (wipes main flash/RAM; clears debug lock after a reset). Requires "device erase enabled". |
| `0x430C0000` | Enable debug lock. **Don't run this.** |

Debug-lock status word bits: `0x01` lock configured, `0x02` device erase enabled, `0x04` secure debug enabled, `0x20` lock active (hw).

## What we saw on this tag

Before: status words `[0x20, 0x101020c, 0xffffffff, 0x27, 0xffffffff]` → lock configured, erase allowed, secure debug on, hw locked.
After erase + **power cycle**: debug-lock word `0x2` → lock off, erase still allowed, unlocked. nRESET alone did not apply it.

The erase command's response is a length word `0x4` and then the connection drops (the chip resets). That's normal.

## Usage

```bash
.venv/bin/python scripts/dci.py status      # read-only
.venv/bin/python scripts/dci.py erase       # DESTRUCTIVE: wipes flash; power-cycle afterwards
```
