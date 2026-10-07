**Title:** Silicon Labs Series 2 packs (e.g. EFR32FG22) are listed in the index but `pyocd pack find/install` shows no such devices; works when the .pack is obtained by hand

### Disclosure: AI-assisted

This report was written by **Claude** (Anthropic's model *Claude Sonnet 5.5*, `claude-sonnet-5-5`, via the Claude Code CLI) while working with **George Stephanis (@georgestephanis)**, who owns and wired up the hardware and observed the results. The model ran the commands and wrote this text. Please tell us if you have a policy for AI-assisted reports or contributions; I could not find one in CONTRIBUTING.md, the developers' guide, README or the issue tracker.

### Summary

On pyOCD 0.45.1 (macOS, Raspberry Pi Pico running `debugprobe` v2.3.1 as a CMSIS-DAP probe) an **EFR32FG22C121F512GM40** could not be found through the pack tooling, so we initially concluded there was no pack and even started writing a custom flash algorithm. In fact:

- The Keil index **does** list `GeckoPlatform_EFR32FG22_DFP` 2025.12.1 (and the other Series 2 families: BG21/22/24/26/27/29, MG21/22/24/26/27/29, FG23/25/28, EFM32PG22/23/26/28 ...). Silicon Labs' engineer said in #1847 that 2025.12.1 fixes the memory-region and flash-loader problems.
- `pyocd pack update` completes with no error, yet `pyocd pack find EFR32FG22`, `pack find BG22`, `pack find EFR32BG22C224F512GM32` and `pack install EFR32FG22C121F512GM40` all report *No matching devices*, while `pack find EFM32` returns 42 older Silicon Labs devices.
- Scripted requests to the pack/pdsc URLs on silabs.com (e.g. `https://www.silabs.com/documents/public/cmsis-packs/SiliconLabs.GeckoPlatform_EFR32FG22_DFP.2025.12.1.pack`) return **HTTP 403** from here (curl with a browser User-Agent, and also with a Referer). The same file downloads fine in a browser from Silicon Labs' CMSIS-pack resources page, so this may be bot protection that expects a cookie or similar (a plain Referer didn't help). I **can't tell whether that 403 is why pyOCD's index lacks these devices**, only that both are true in our environment.

**Concrete numbers** (after a fresh `pyocd pack update`; cache at `~/Library/Application Support/cmsis-pack-manager`):
- The cache holds 1674 `.pdsc` files for 1823 index entries.
- **0 of the 86 non-deprecated `SiliconLabs` entries are in the cache** (all of them, every Series 2 family); no `SiliconLabs.*.pdsc` file exists at all.
- Nearly every other vendor is complete; the few other misses are single entries (Sinowealth 2/2, ASN 1/1, SodiusWillert 1/1, Clarinox 1/1, Zilog 1/1, Puya 1/7, Cmsemicon 1/37).
- `pack update` printed no error or warning, even with `-vv`.

### With the pack obtained manually, pyOCD works well

`pyocd flash --pack SiliconLabs.GeckoPlatform_EFR32FG22_DFP.2025.12.1.pack -t efr32fg22c121f512gm40 --base-address 0x10000 -f 1000000 random.bin` (20000 random bytes):
*Erased 24576 bytes (3 sectors), programmed 24576 bytes (3 pages) ... at 42.79 kB/s*; a read-back of the same range was byte-for-byte identical; `pyocd erase -s 0x10000+0x6000` also worked.

Two small observations:
- Every connect prints `Error probing AP#3: SWD/JTAG communication failure (WAIT ACK)`; `-O adi.v5.max_invalid_ap_count=0` (the workaround mentioned in #1847) removes it and everything still works.
- With a program running on the chip, `connect_mode=halt` prints *Timed out waiting for core to halt after reset (state is RUNNING)*; flashing still succeeds.

### Questions / suggestions

1. Does the pack manager silently drop descriptors it can't fetch? If so, could `pack update` / `pack find` report which packs failed to download, so users aren't left with an empty result?
2. Is there a recommended way to get Silicon Labs' Series 2 packs when `silabs.com` blocks scripted downloads (documenting `--pack <manually downloaded file>` somewhere, a mirror in the index, ...)?
3. (Side note) A **debug-locked** Series 2 part makes pyOCD report "No cores were discovered"; the pack has no debug sequences to unlock it. Unlocking needs the Series 2 DCI (AP index 1) "device erase" over SWD (described in Silicon Labs AN1190/AN1303). Probably a separate feature request; mentioning it in case it helps others who hit the same wall.

We also wrote an independent flash algorithm against the MSC registers before finding the pack works; it flashes correctly but is slower (27 kB/s) and has no mass erase, so we are **not** proposing it unless you want it.

### Related issues
- #1223 `pack update` fails due to invalid certificates and 404 errors (2021; same kind of symptom for other vendors, with TLS-certificate causes)
- #1847 EFR32BG22: memory regions must have a non-zero length (Silicon Labs fixed the DFP; see the maintainers'/vendor discussion)
- #1642 Silabs EFR32BG24 stopped working (Series 2 errors; workaround was a custom built-in target)
- #1637 Cortex-M33 session init / AP address error (a user reporting a similar-looking problem on an EFR32BG24)
- #280 Target Support EFM32 (earlier history of Silicon Labs support requests)
