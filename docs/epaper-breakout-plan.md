# Plan: our own 24-pin e-paper breakout (instead of buying a DESPI-C02)

Status: **planning only; nothing designed yet.** Written 2026-10-06.

## Why design from the circuit, not clone the DESPI-C02

- The DESPI-C02 is a 24-pin 0.5 mm FPC connector + the controller's standard booster/charge-pump circuit + a 2.54 mm header. The *circuit* is the controller's published reference design; our board needs the values suited to **this panel**.
- Copying a commercial board's traces/layout from photos is error-prone and ethically/legally murkier than designing our own; the schematic is standard, the layout is simple.
- Ground truth for this panel: the tag's own board (rev A) already carries the working booster circuit next to the FPC connector (inductor, MOSFET, three small diodes, several caps, a sense resistor).

## Reference design (license-clear)

Adafruit's **2.13" eInk Bonnet** (https://github.com/adafruit/Adafruit-2-13in-eInk-Bonnet-PCB, Eagle files, **CC BY-SA**: attribution and share-alike if we derive from it). Booster/driver parts it uses for a 2.13" panel (values may differ for the 2.06" Pervasive panel; use only as a cross-check):
3x Schottky MBR0540 (SOD-123); inductor 10 uH; sense resistor 0.47 ohm (0805); N-MOSFET SOT-23 (IRLML-class); caps: 5x 1 uF/25 V, 1x 4.7 uF/25 V, 1 uF/10 V, 10 uF/10 V (0805); 24-pin 0.5 mm FPC connector; I2C pull-ups 100k.

## Panel facts from the Pervasive Displays product specification (read 2026-10-06)

Source: `1Pxxx_00_tentative_E2206KS0E1_20230901.pdf` (2.06" family, tentative, 28 pages, marked PDI Confidential; downloaded by the user from Mouser; **not stored in this repo** and not to be redistributed; only facts are recorded here).

Connector: 24-pin, 0.5 mm pitch, ZIF (HRS FH34SRJ-24S or STARCONN 6700S24 or compatible). Panel is driven over 4-wire SPI with `BS` tied to GND.

| Pin | Name | Type | Function / connection |
|---|---|---|---|
| 1 | NC | | |
| 2 | GDR | O | gate drive of the external N-MOSFET (booster) |
| 3 | RESE | I | booster current-sense input (0.47 ohm to GND in the reference circuit) |
| 4 | NC | | |
| 5 | VDHR | C | 1 uF/25 V to GND |
| 6, 7 | NC | | |
| 8 | BS | I | to GND (selects the interface: 4-wire SPI) |
| 9 | BUSY_N | O | busy output, **low = busy** (matches our finding on PA08) |
| 10 | RST_N | I | active-low reset |
| 11 | D/C | I | data/command |
| 12 | CSB | I | chip select |
| 13 | SCL | I | SPI clock |
| 14 | SDA | I | SPI data in |
| 15 | VDDIO | P | I/O supply |
| 16 | VDD | P | chip supply (reference-circuit test conditions: 3.0 V) |
| 17 | GND | P | ground |
| 18 | VDDD | C | internal regulator output, capacitor to GND |
| 19 | NC | | |
| 20 | VDH | C | 1 uF/25 V to GND |
| 21 | VGH | C | 1 uF/25 V to GND (booster output) |
| 22 | VDL | C | 1 uF/25 V to GND |
| 23 | VGL | C | 1 uF/25 V to GND (negative pump output) |
| 24 | VCOM | C | 1 uF/25 V to GND |

Reference circuit parts (Figure 5-1): **inductor 10 uH ATNR4010100MT +-20% 0.8 A; N-MOSFET MCH3478 SOT-23 30 V/2 A (RDS < 235 mohm, Vgs 2.5 V @ 0.5 A); three Schottky SS2040FL SOD-123FL (Vf 0.2-0.4 V, Vr > 25 V); sense resistor 0.47 ohm; one 4.7 uF/25 V; 1 uF/25 V capacitors on VDHR, VDH, VGH, VDL, VGL, VCOM, VDDD; supply decoupling 0.1 uF/16 V + 1 uF/6.3 V.** The figure labels the supply "Connect to Power Switch ... Connect to a transistor switch to prevent leakage current": the panel supply should be switchable (this is what PC06 does on the tag).
Cross-check: Adafruit's 2.13" bonnet netlist has the same topology: L (supply -> MOSFET drain / 4.7 uF flying cap / rectifier diode to VGH), the other two diodes form the negative pump (to VGL, one clamps to GND), 1 uF/25 V on each output, BS to GND. So their netlist is a verified skeleton for ours.

## Flex and connector facts (user photo + Hirose listing, 2026-10-06)

- The panel's flex carries the markings **`A1360146-00 / 2403 / 94V-0 / 02 55`** (the earlier "back-side" markings were on the flex, not the board), with pin numbers printed **`1` at the left and `24` at the right when the gold fingers face the viewer** (flex pointing away).
- On the original tag the **fingers faced the board** when connected (a bottom-contact arrangement).
- The panel datasheet's connector, **Hirose FH34SRJ-24S-0.5SH ((50) or (99) = packaging), is a top-and-bottom contact, back-flip, 0.5 mm, 1.0 mm tall, 14.0 mm long ZIF**, for flex thickness 0.3 +- 0.03 mm (https://www.hirose.com/product/p/CL0580-1255-6-50). Because it contacts both sides, the flex works either way up, but **numbering mirrors with orientation**: with fingers facing the PCB (the original arrangement) and the flex entering from the front, pin 1 is on the RIGHT and pin 24 on the LEFT when viewed from above. The footprint/silkscreen will mark pin 1 and pin 24 explicitly and the orientation must be verified by continuity against the tag's own connector (e.g. RES/PC04 -> panel pin 10) before ordering.

## What we still need

1. ~~The panel's FPC pinout and recommended circuit~~ **Done** (table above). Still unknown: the full register/command sequence for this iTC controller (we have the working sequence from our own experiments).
2. Which side of the flex carries the contacts (top vs bottom contact connector) and the connector's orientation.
3. Decide the target form factor (plain 2.54 mm header like the DESPI-C02, a Seeed XIAO footprint, castellated pads for an ESP32/nRF module, ...).

## Process (KiCad 9 is installed on this Mac: `kicad-cli`)

schematic -> netlist -> PCB layout (2 layers, ~30 x 40 mm) -> DRC -> Gerbers + BOM/CPL -> order 5-10 (JLCPCB/PCBWay) -> verify pin order by continuity against the known signals (PC00 SDA, PC01 SCK, PC02 CS, PC03 D/C, PC04 RES, PA08 BUSY on the tag board) **before** applying power.

## Economics (rough)

DESPI-C02 is ~$8.50-10 each. A custom board is ~$2-3 each in quantity, but a one-off run costs about the same as buying one or two plus time and risk; it pays off for ~10+ boards or when a custom form factor is wanted. Suggested: buy one DESPI-C02 now to bring up the software on an ESP32/nRF while the custom design is made.
