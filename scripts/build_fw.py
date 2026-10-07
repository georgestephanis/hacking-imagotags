#!/usr/bin/env python3
"""Build a tiny position-independent bare-metal image for the EFR32FG22 without a linker.

usage: build_fw.py firmware/<name>/<file>.c [out.bin]

Compiles one C file with Homebrew LLVM for Cortex-M33, extracts the machine code (.text) with llvm-objcopy, checks there are no
relocations, and prepends a 16-word vector table (initial SP at the top of the 32 KB SRAM; every exception except reset points at a
`b .` hang loop; reset points at the function named `reset`, wherever the compiler put it). Needs: brew install llvm.
Constraints (there is no linker): the whole program must be position independent, so no global/static data and no const arrays
(they end up in other sections and need relocations); helpers must be `static` functions in the same file (calls between them are
resolved by the assembler); use absolute addresses for RAM buffers. The result is meant to be flashed at 0x00000000.
"""
import os, struct, subprocess, sys

LLVM = os.environ.get("LLVM_BIN", "/opt/homebrew/opt/llvm/bin")
SRAM_TOP = 0x20008000
CODE_OFF = 0x44            # 16 vectors (0x40 bytes) + 4-byte hang loop

def run(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout

def main():
    src = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".bin"
    obj = os.path.splitext(src)[0] + ".o"
    run(f"{LLVM}/clang", "--target=thumbv8m.main-none-eabi", "-mcpu=cortex-m33", "-Os", "-ffreestanding", "-fno-builtin",
        "-fno-pic", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-nostdlib", "-Wall", "-Wextra", "-c", src, "-o", obj)
    relocs = run(f"{LLVM}/llvm-readelf", "-r", obj)
    if "'.rel.text'" in relocs:      # relocations against our code (unwind-table ones in .ARM.exidx are ignored: that section is not extracted)
        sys.exit("code has relocations; this build only supports position-independent programs without data sections:\n" + relocs)
    sections = run(f"{LLVM}/llvm-readelf", "-S", obj)
    extra = [n for n in ("rodata", "data", "bss") if f".{n}" in sections.replace(".rodata.str", "")]
    if extra: sys.exit(f"object has data sections ({extra}); remove static/const data (see the constraints in this script's docstring)")
    code_bin = obj + ".code"
    run(f"{LLVM}/llvm-objcopy", "-O", "binary", "-j", ".text", obj, code_bin)
    code = open(code_bin, "rb").read()
    code += b"\x00" * (-len(code) % 4)
    entry = None
    for line in run(f"{LLVM}/llvm-nm", "--defined-only", obj).splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == "reset": entry = int(parts[0], 16)
    if entry is None: sys.exit("no function named 'reset' (the entry point) in the object")
    vec = [SRAM_TOP, ((CODE_OFF + entry) | 1)] + [0x40 | 1] * 14       # reset -> entry; all other exceptions -> hang loop at 0x40
    img = struct.pack("<16I", *vec) + b"\xfe\xe7\xfe\xe7" + code
    open(out, "wb").write(img)
    print(f"{out}: {len(img)} bytes (code {len(code)} bytes at {CODE_OFF:#x}, reset entry +{entry:#x})")

main()
