# ESWIN EMU32VL170 (ContRD010C's MCU): what is publicly known

Research done 2026-10-05 (late), by web search only; nothing was tested on hardware. Marking on the C board's MCU:
`ESWIN / EMU32VL170 / -A1 / A392K70102 / 2439AHA0` (date code 2439 = 2024 week 39). The pin-1 dot is rotated 90° clockwise relative to the A board.

## Confirmed by sources

| Fact | Source |
|---|---|
| 32-bit **RISC-V, RV32EC** microcontroller family "EMU32VL17x" | SEGGER KB: https://kb.segger.com/ESWIN_EMU32VL170 |
| **128 KB internal flash at `0x25000000`**; separate **7 KB bootloader area at `0x24000000`** | SEGGER KB (same page) |
| Has a **watchdog** (the J-Link flash routine feeds it); "uses normal RISC-V reset, no special handling necessary" | SEGGER KB (same page) |
| **J-Link and Flasher support it** (also listed: ESWIN EAM2011 and ECR2560) | https://www.segger.com/supported-devices/eswin/ |
| An evaluation board exists ("EMU32VL170 TEST BRD"); the SEGGER setup text says to connect the J-Link to connector J88 and power via J91 (no pinout given) | https://kb.segger.com/ESWIN_EMU32VL170_TEST_BRD |
| Package **QFN28, 4 x 4 mm**; the part is orderable as a JLCPCB/LCSC "new arrival" (C9900054450), with no datasheet on the listing | https://jlcpcb.com/partdetail/-EMU32VL170/C9900054450 |

## Context (not specific to this chip)

- ESWIN Computing (北京奕斯伟计算技术) is a Beijing RISC-V company (application processors, display and power-management chips, automotive MCUs). Its website lists a family of 32-bit RISC-V CPU IP cores, including very small ones (**E100**: RV32 (E/I)(M)(C), 2-stage; **E301**: RV32 EMC, 3-stage; **ES000**: security-oriented RV32 EMC/Zc): https://www.eswincomputing.com/en/risc.html . It is a *guess* that the EMU32 uses one of these small cores; no source ties them together.
- The larger ESWIN core page (E330) says it has a **JTAG/cJTAG debug interface**: https://www.eswincomputing.com/en/risc/info/19.html . That suggests ESWIN's cores use standard RISC-V-style JTAG/cJTAG debug, but this is inferred from a different core, not confirmed for the EMU32VL170.

## Not found (despite searching English and Chinese)

- A **datasheet, reference manual, SDK or pinout** for the EMU32VL170 (neither on ESWIN's site nor on the part listing).
- Any **open-source tool support**: nothing for OpenOCD, probe-rs or pyOCD (pyOCD is Arm-only anyway); no GitHub repository or code mentioning the part name.
- Whether the chip has a **UART/serial bootloader** (the 7 KB bootloader area is suggestive but unconfirmed), what its **read protection / lock** behaviour is, which **debug interface and pins** it exposes, or its **RAM size**.
- Any teardown or write-up of the part inside an electronic shelf label.

## What this implies

- **Reprogramming revision C is plausible but harder than A**: it needs either a **SEGGER J-Link** (the only confirmed debug path) or luck with a generic RISC-V debugger, plus tracing C's debug pads from scratch. QFN28 is a small package, so debug pins are probably shared with GPIO and the board may only expose 2-4 pads; that matches "cJTAG or JTAG" but is unverified.
- Documentation is the bigger obstacle than hardware: without register-level docs we could not write drivers or a flash routine the way we did from Silicon Labs' public headers. A **J-Link can still read, erase and write the flash and halt the CPU**, so firmware could be built with a plain RISC-V toolchain once the memory map and peripherals are probed experimentally (as we did on A).
- Lower-effort first steps if you want to pursue C:
  1. Photograph the MCU area and trace which pads reach the 28 pins (pin 1 is rotated, so mark it); look for 4-5 unlabeled pads in a row.
  2. Check whether the board has a footprint for a header or pogo pads near the chip (we found a dense test-pad field on A).
  3. Ask ESWIN / the seller for documentation, or check the SEGGER KB's example projects (the KB mentions example projects for the part).
  4. Borrow or buy a J-Link EDU Mini for the first connection attempt.
- It is *not* necessary for any of the Silicon Labs work: everything for revision A stands on its own.

## Search log (so nobody repeats it)

Queries tried: "ESWIN EMU32VL170 microcontroller"; "EMU32VL170 datasheet ESWIN RISC-V RV32EC MCU 128KB flash package"; "ESWIN EMU32 electronic shelf label ESL MCU RISC-V low power 2.4GHz"; "EMU32VL170 OpenOCD OR probe-rs OR UART bootloader OR ISP programming"; Chinese "奕斯伟 EMU32VL170 MCU 电子价签 RISC-V 芯片"; "eswincomputing.com MCU EMU32 …"; "ESWIN ECR2560 OR EAM2011 OR EMU32VL170 datasheet SDK documentation download"; GitHub repo/code search for "EMU32VL170", "EMU32VL17", "ESWIN EMU32" (no results).
