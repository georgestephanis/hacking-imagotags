# pyOCD support for the Silicon Labs EFR32FG22 (flash algorithm + target)

> **You probably do not need this.** Stock pyOCD (0.45.1 tested) flashes the EFR32FG22 with Silicon Labs' **official CMSIS pack** passed by hand:
> `pyocd flash --pack SiliconLabs.GeckoPlatform_EFR32FG22_DFP.<version>.pack -t efr32fg22c121f512gm40 ...`. That route is faster (~43 kB/s against ~27 kB/s here) and has mass erase,
> which this target lacks. What fails is *discovering* the pack: `pyocd pack find/install` returns nothing for the Silicon Labs Series 2 devices and silabs.com returns HTTP 403 to scripts, so the pack must be
> downloaded in a browser. We reported that upstream as **[pyocd/pyOCD#2042](https://github.com/pyocd/pyOCD/issues/2042)** (text in [`../docs/pyocd-issue-draft.md`](../docs/pyocd-issue-draft.md)), and
> because the official route works we are **not** proposing this target for upstream. See "pyOCD and the Silicon Labs pack" in [`../docs/flashing.md`](../docs/flashing.md).
>
> This directory is an independent, self-contained alternative we wrote **before** we found the pack worked: our own flash algorithm and a builtin-style target, usable with no pack at all.

pyOCD itself ships no built-in target for the EFR32FG22 (Series 2, Cortex-M33); the pack is how it learns about the part. This directory supplies one without the pack:

| File | What it is |
|---|---|
| `fg22_algo.c` | The on-target **flash algorithm** (`Init`, `UnInit`, `EraseSector`, `ProgramPage`), written against Silicon Labs' MSC registers. Position independent, no libraries. |
| `build_algo.py` | Compiles it (Homebrew LLVM, no linker needed) and generates the two files below. |
| `target_EFR32FG22C121F512GM40.py` | **pyOCD builtin-style target** (for upstream: `pyocd/target/builtin/`). Relative imports, as in the other builtin targets. |
| `pyocd_fg22.py` | The same target as a **standalone launcher** (absolute imports): registers the target at runtime, then runs the normal pyOCD CLI. |

Verified on an EFR32FG22C121F512GM40 (SES-imagotag HRD3-0210-A tag) through a Raspberry Pi Pico running debugprobe: `pyocd flash` erased 3 x 8 KiB pages and
programmed 20 KB of random data (20 x 1 KiB pages, ~27 kB/s, 1 MHz SWD); a read-back matched byte for byte. `pyocd erase -s` also works.

## Use it today (no pyOCD changes needed)

```bash
pip install pyocd
python pyocd-target/pyocd_fg22.py flash -t efr32fg22c121f512gm40 --base-address 0x0 -f 1000000 firmware.bin
python pyocd-target/pyocd_fg22.py erase -t efr32fg22c121f512gm40 -s 0x10000+0x6000
python pyocd-target/pyocd_fg22.py cmd   -t efr32fg22c121f512gm40 -O connect_mode=attach -c "read32 0 8"
```

(`pyocd_fg22.py` accepts every normal pyOCD subcommand and option.)

## Contributing it upstream (not currently planned)

1. Copy `target_EFR32FG22C121F512GM40.py` to `pyocd/target/builtin/`.
2. In `pyocd/target/builtin/__init__.py` add:
   ```python
   from . import target_EFR32FG22C121F512GM40
   ...
       'efr32fg22c121f512gm40': target_EFR32FG22C121F512GM40.EFR32FG22C121F512GM40,
   ```
3. Other FG22/BG22/MG22 variants differ in flash size and the memory map only; the algorithm is the same MSC sequence (check each part's flash size/page size in its header).

### Still to do before a PR
- **Mass erase** (`pc_eraseAll`): not implemented; pyOCD falls back to sector erases. The ERASEMAIN0 path in Silicon Labs' em_msc.c shows the extra unlock needed.
- **Debug-locked parts:** this target cannot unlock a secure-debug part. See `docs/debug-unlock.md` (DCI device erase) for the procedure we used.
- **User-data and lock-bit regions** (`0x0FE00000`, `0x0FE04000`) are not in the memory map.
- **Other xG22 family members:** only the C121F512GM40 has been tested. Flash sizes/RAM sizes need checking per part.
- **A CMSIS-Pack route** would let `pyocd pack install` do this; building an ELF `.FLM` needs a linker (not available in this setup).
- **Known warning:** with the core running firmware, `connect_mode=halt` prints "Timed out waiting for core to halt after reset"; flashing still works. Using `-O connect_mode=attach` avoids the reset.

## Regenerating

```bash
brew install llvm            # Homebrew LLVM provides the Thumb-2 backend and llvm-objcopy
python pyocd-target/build_algo.py
```
Constants: algorithm loaded at `0x20000000`, stack top `0x20000700`, two 1 KiB page buffers at `0x20000800` and `0x20000C00` (32 KiB RAM total).
