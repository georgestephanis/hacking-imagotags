> **Raw research log**, kept in the order things happened, including wrong turns and corrections (later entries override earlier ones).
> Pad and net IDs in this log are the **original auto-numbered ones** (`tp-back-18`, `pad-front-122`, `NET16`...). The renamed IDs used everywhere else in this repo are mapped in
> [`../hardware/netlist/id-map.json`](../hardware/netlist/id-map.json) (old -> new). References to `scripts/gen_pinmap.py`, `docs/pinmap.md` and the project's old layout are historical.
> The BTRTx008A analysis mentioned in places is not part of this repository.

# Log

Newest at the bottom. Facts first; corrections are noted where an earlier assumption was wrong.

## 2026-10-05

- Model HRD3-0210-A (SES-imagotag/Vusion). Board silkscreen `imagotag ContRD0?0A`. MCU marking `FG22 / C121GG / C0241T / 2344`
  → EFR32FG22C121, **QFN40** (initially assumed QFN32; corrected once the SVG footprint showed 10 pads per side).
- Related public teardowns: NLTD2010/Imagotag-SES (CC2510), BeatSkip/SES-Imagotag-UU340 (AX8052), TenOfNine/imagotag-vusion-esl-reverse-engineering
  (EFR32FG22 on a 7.4" tag). Only the last shares our MCU.
- Panel: long thin chip-on-glass e-paper, 24-pin FPC, label `KE2206JSKE1 / SPP2DC1 / 7MADCM6859`. Not a standard 2.13" Waveshare size
  (an earlier assumption of GDEW0213Z16 was wrong). Booster components (inductor, MOSFET, diodes) are on the main board near the FPC.
- Debug-pad side has an RGB LED (top-left corner), an NFC antenna coil, and ~50 round test points covering almost every GPIO.
- Traced the board with circuit-tracer; SVG has an embedded netlist. Pin-1 orientation: top of the left side in `mcu-side.jpg`,
  counter-clockwise numbering. Verified in the SVG by pin 13 (RFVSS) being on GND — but that GND came from a user-marked via, so not independent —
  and pin 15 (PAVDD) being on the big supply net (independent). Quick multimeter checks still recommended: pin 1 ↔ `tp-back-43`, pin 11 ↔ `tp-back-23`.
- Silicon Labs 8-bit USB Debug Adapter can't do SWD. Used a Raspberry Pi Pico + debugprobe v2.3.1 (CMSIS-DAP) instead.
- First power attempt shorted the rail to ground via a bad solder joint on the bare pads; moved to `tp-back-31` for +3.3 V.
- With power fixed: DPIDR `0x6BA02477` reads OK (at 20 kHz) → SWCLK/SWDIO wiring and the pin map are right.
  AP reads all fault → secure debug lock.
- Read the lock state over DCI: locked, secure debug on, device erase allowed. Wiped the tag (authorised: spares available).
  Needed a **power cycle** to take effect.
- Post-unlock: CPUID `0x410FD214` (Cortex-M33 r0p4); core in Lockup (empty flash); flash at `0x00000000` all `0xFFFFFFFF`;
  `0x08000000` reads zeros (wrong base for this family). `0x0FE08000` (device info page) is readable.
- SWD only reliable at ~20 kHz so far.

### RGB LED hypothesis (user, 2026-10-05)

User believes MCU pins 16, 18, 20 (PB04, PB02, PB00) drive the three RGB LED channels through series resistors,
with a common ground. Netlist supports the front half: pads 96/98/100 → 168/169/171 (NET61/62/10), each paired with
a 0.3×0.3 mm pad at 0.6 mm pitch (167/170/172, nets NET100/101/102 — untraced), likely 0201 resistors at ~(2744–2785, 795) on the MCU side.
Not yet traced: the LED pads on the test-pad side and the common pin (cathode vs anode decides drive polarity).
Plan: halt the core and poke GPIO registers via the debugger to confirm colours (needs EFR32xG22 RM register addresses).

### Re-trace (2026-10-05, 15:19 export)

- **nRESET confirmed in the netlist:** MCU pin 11 (pad-front-82) ↔ tp-back-23 via via-41.
- Four test points of the 2x2 block near the LED (tp-back-4/5/6/7) are now joined by vias to MCU-side pads:
  tp-back-4 ↔ pad 173, tp-back-5 ↔ pad 159, tp-back-6 ↔ pad 131, tp-back-7 ↔ pads 175 and 177 (two pads, one node).
  Role not yet known — candidates are the LED channels / common, or something else. Pin 16/18/20 → pads 168/169/171 chain unchanged.
- Net labels are renumbered on every re-save; compare by connectivity, not NETn names.

### LED feed pads (user, 2026-10-05)

User reports the 2x2 test-point block is the three R/G/B LED feeds plus one unused pad; `tp-back-5` goes to an unpopulated component.
So: **tp-back-4 (pad 173), tp-back-6 (pad 131), tp-back-7 (pads 175/177)** are the three LED channel feeds (colour order unknown);
**tp-back-5 (pad 159)** is the unused one. Which MCU pin drives which colour is still untested.
Test plan: halt the core, enable the GPIO clock, drive PB00/PB02/PB04 one at a time and watch the LED.

### LED test attempts and the brownout finding (2026-10-05, afternoon)

- Driving PB00/PB02/PB04 high/low from the debugger (scripts/gpio_poke.py) showed no light. **Those tests are not conclusive:** the chip resets
  ~0.1 s after every debugger connect, so GPIO state set via SWD is wiped almost immediately.
- Cause: `EMU_RSTCAUSE` (0x40004094) reads `0x81` = POR + **DVDDBOD (brownout)**. DHCSR `0x180001` = core in lockup (empty flash). Resets happen even with the core halted.
  The rail is dipping when the debug domain powers up — power from the Pico 3V3 via jumpers into NET14 (tp-back-31) is marginal.
  Also explains the flaky SWD link at anything above ~20 kHz and the sporadic "No ACK".
- Fixes to try: measure NET14 at the tag while connecting (should hold >= ~3.0 V); add a 47–100 µF cap across VDD/GND at the pads; shorter/thicker power wires;
  or a separate 3.3 V supply. Then retest LED pins; scripts/gpio_scan.py scans the other GPIOs once the supply is stable.
- Register addresses used (from Silicon Labs simplicity_sdk `efr32fg22*.h`): CMU_S 0x40008000 (CLKEN0 +0x64, GPIO = bit 26), GPIO_S 0x4003C000
  (port stride 0x30: CTRL, MODEL +4, MODEH +0xC, DOUT +0x10, DIN +0x14), EMU_S 0x40004000 (RSTCTRL +0x90, RSTCAUSE +0x94),
  WDOG0_S 0x4A018000. EMU RSTCAUSE bits: 0 POR, 1 PIN, 3 WDOG0, 5 LOCKUP, 6 SYSREQ, 7 DVDDBOD, 9 DECBOD, 10 AVDDBOD, 16 DCI.
- User idea: test the LED independent of the MCU by feeding 3.3 V through a series resistor into tp-back-4/6/7.

### RGB LED confirmed by hand (user, 2026-10-05, ~15:40)

- LED is **common anode** (shared pad on the supply side, ends at pad-front-127 / a passive). Each colour lights when its channel pad is pulled **low**:
  **tp-back-4 = red, tp-back-6 = green, tp-back-7 = blue** (channel pads = LED back-side pads 286 / 285 / 287).
- Firmware implication: LED colour ON = pin driven LOW; OFF = high or released. Earlier debugger tests drove pins HIGH, which would have turned the LED off even without the resets.
- tp-back-5 (pad-back-291 / pad-front-159) goes to an unpopulated footprint — maybe IR LED/receiver or light sensor (unknown, guess).
- Still unknown: which MCU pin drives which colour. Hypothesis PB04/PB02/PB00 (pins 16/18/20 → pads 168/169/171 → 167/170/172), not yet traced to the channel pads.

### LED channel -> MCU pin mapping (user tracing, 2026-10-05)

User: three parallel component clusters end in trace-front-113 / 112 / 111 (LED side); the matching traces on the MCU side are
trace-front-115 / 116 / 117, which connect directly to MCU pins 16 / 18 / 20. In matching order:

| MCU pin | GPIO | MCU-side trace | LED-side trace | test point | colour |
|---|---|---|---|---|---|
| 16 | PB04 | trace-front-115 (pad 168) | trace-front-113 | tp-back-7 | **blue** |
| 18 | PB02 | trace-front-116 (pad 169) | trace-front-112 | tp-back-4 | **red** |
| 20 | PB00 | trace-front-117 (pad 171) | trace-front-111 | tp-back-6 | **green** |

Active-low (common anode): drive the pin LOW to light it. Netlist verifies each end; the pairing across the intermediate passives is from the user's layout reading.
Not yet verified on the chip (blocked by the brownout resets). `scripts/gpio_poke.py led r|g|b|off` implements it.

### LED anode is probably switched (user, 2026-10-05)

User: as the LED is common-anode and the design is low-power, the anode is likely not normally powered. So lighting a colour needs the **anode supply enabled** plus the colour pin driven low;
the colour pins alone cannot light it (which also fits the earlier "no light" tests, besides the brownout resets).
Common net = pad-back-288/289/290/292 + pad-front-127 (+ via-59/60); pad-front-128 (other side of that passive) is untraced.
To find the source: continuity from the LED common / pad 127 / pad 128 to the GPIO test points (try tp-back-20 / PA06 first), and measure the common's idle voltage.
`gpio_poke.py led` will need an extra "anode on" pin once found.

### Pin 32 / VREGVDD and the LED common (user scan, 2026-10-05)

User's scan suggests MCU pin 32 is tied into the LED common anode. Pin 32 = **VREGVDD** (DC-DC regulator input supply, QFN40 pin 32), pad-front-108, which in the saved netlist shares only pad-front-229 (small passive) — the link to the LED common (NET with pad-back-288/289/290/292, pad-front-127) is NOT in the SVG yet.
Hypothesis: VREGVDD is a separate raw-supply rail from the NET14 rail we feed via tp-back-31. That would explain (a) the common anode looking unpowered and (b) the DVDD brownout resets (RSTCAUSE 0x81) if the DC-DC input is unpowered.
To check: measure pin 32 / pad 229, the LED common, and DVDD (pin 34) with the tag powered through NET14; if ~0 V, feed 3.3 V into the VREGVDD/LED-common rail as well (e.g. via the big LED common pad pad-back-288) and retry.

### Push button confirmed on PB03 (2026-10-05, 16:00)

MCU pin 17 = PB03 (`tp-back-24`, pad-front-97). `scripts/button_watch.py`: PB03 as input with internal pull-up reads 1 at rest, 0 while the button is held; 10 presses in 40 s, clean transitions (taps ~0.2 s, holds 1–2 s).
So it is an **active-low button to ground**, no external pull-up needed. Purpose unknown (programming? pairing? rail/mount detect?).

### LED observations so far

- With the three colour pins driven HIGH (LED should be off) the user still sees a dim red/green glow that shifts on its own ("went to green, now red again"). So the glow isn't coming from PB00/PB02/PB04 as hypothesised;
  pulsing "blue" x3 showed nothing. Pin->colour mapping unconfirmed. Test with all pins hi-Z / high / low (12 s each) pending the user's observations.

### LED brightness findings (2026-10-05, 16:00-16:15)

- After the ground wire was resoldered (to tp-back-39) the chip stays up and SWD is reliable up to 1 MHz (5/5 connects); the brownout resets stopped. The earlier flaky link/brownouts were a loose ground.
- Common anode measures 3.3 V (same as VCC) with a meter, but the LEDs are very dim when driven through the board and bright when the user feeds 3.3 V into the anode directly through the same resistor.
  => the anode feed is high-impedance (likely the small passive pad-front-127/128, or a switch not enabled).
- Blue never lights; red/green dim — consistent with a starved anode (blue needs ~3 V forward voltage).
- Colour pins: PB02 driven HIGH lit red (dim) and it stayed on after the pin was released; holding all three LOW lit nothing. Suggests a low-side switch (gate holds charge) with active-HIGH control. Not yet confirmed per-colour.
- Careful: pyOCD queues writes — a script that ends on a write without reading/closing may not flush it (caused a "released" pin to stay driven). Scripts now read back / close.
- Next: with a cathode grounded through a resistor, scan GPIOs high then low (scripts/gpio_scan.py) to find what enables the anode path.

### Photo review of the LED drive circuitry (2026-10-05, from the photos embedded in the SVG)

Overlays: `docs/images/overlay_leds_mcuside.png`, `docs/images/overlay_left.png` (pad IDs drawn on the embedded photo, front/MCU side).
- Each colour channel is the same 3-part cluster, left to right: **green (pads 129-134 / 171-172), red (133/134/173/174 / 169-170), blue (175-178 / 167-168)**.
  Per channel: a small populated 0201 resistor pair at the bottom (171/172, 169/170, 167/168), a **small dark 3-legged part with a marking (transistor-like)** above it,
  and a pair of 0201 pads above that (131/132, 173/174, 177/178 populated; 129/130, 133/134, 175/176 appear **unpopulated/bare** — blue has an unpopulated footprint in parallel).
  The transistors' pins are **not** recorded as pads in the SVG, which is why the pin → LED trace can't be followed through them.
- That fits the observed behaviour: pin HIGH turns the colour ON (switch), the state persists when the pin is released (gate charge), and the LED brightness depends on the anode feed.
- Left of the channels is a second cluster of two more transistors plus small passives (pads 139-146, 151/152, 154-156); pad 145 is on the VDD net (NET14), so it looks like a **high-side switch for the LED common anode**.
  Pads 127/128 (the LED common's passive) look like an **unpopulated pair** (bare solder, no body) beside a populated part whose pads are not in the SVG.
- Test points on that cluster: tp-back-8 (pad 140), tp-back-9 (pads 144/148/154), tp-back-11 (pads 143/155).

### RGB LED fully solved (2026-10-05, 16:16-16:18)

Tested with `scripts/pins.py` (one pin pair at a time, user watching):
- **PD00 (MCU pin 40, tp-back-36) = LED anode enable.** PD00 high + PB02 high = BRIGHT red; PB02 high + PD00 low = dim red (the dim glow we kept seeing).
- **PB02 (pin 18) = red, PB00 (pin 20) = green, PB04 (pin 16) = blue.** All **active-high**, each through a transistor stage (a dark 3-legged part per channel, marked "ZV" per the user; not identified).
  With PD00 high: PB00 = bright green, PB04 = bright blue.
- So the earlier "pins low = on" assumption was wrong; the LED is common-anode but behind a high-side enable (PD00) and low-side transistors driven active-high.
- A colour pin released after being driven high leaves the channel on (gate holds charge); drive it low for ~2 s to clear.
- Found via photo review: pad 156 (net with tp-back-36 / MCU pin 40) sits at the lower transistor of the left cluster.

### Display interface pins (user, 2026-10-05)

Apart from power and ground, the only MCU pins whose traces head toward the e-ink display connector are **1, 2, 3, 4, 5 (PC00-PC04) and 29 (PA08)** — six signals, which matches a typical SPI e-paper interface
(MOSI/SDA, SCLK, CS, D/C, RES, BUSY). Which is which is still unknown; BUSY will be the one input. Plan: identify by driving/reading them against the panel once we can run code.

### First flashed program (2026-10-05)

- `firmware/led_demo/led.c` built with `scripts/build_fw.py` (Homebrew LLVM, no linker: position-independent single function + generated vector table) -> 248-byte image.
- `scripts/flash_msc.py` drives the MSC registers over SWD (halt, MSC clock, unlock, WREN, erase 8 KiB page, WDATA burst + WRITEEND, verify, SYSRESETREQ): **erase + program + verify OK** on first try.
- After the reset the core runs from flash (RSTCAUSE 0x43 = POR+PIN+SYSREQ, no lockup, GPIO config as set by the program, button cycles the LED colours).
- Next: turn the MSC sequence into a real on-target flash algorithm + pyOCD target so `pyocd flash` works without custom scripts.

### LED mapping re-verified with single-pin tests (2026-10-05, 16:24-16:25)

PD00 high + only PB00 high = **green**; PD00 high + only PB04 high = **blue** (dimmer than red/green: blue needs ~3 V forward voltage on a 3.3 V rail).
PB02 = red (earlier). The demo firmware cycles red -> green -> blue -> off.

### pyOCD flash algorithm + target (2026-10-05, ~16:40)

- `pyocd-target/fg22_algo.c` -> `build_algo.py` -> `target_EFR32FG22C121F512GM40.py` (builtin style) and `pyocd_fg22.py` (standalone launcher that registers the target then runs the pyOCD CLI).
- Verified with `pyocd flash --base-address 0x10000` of 20000 random bytes: 3 sectors erased, 20 pages programmed (~27 kB/s), read-back identical; `pyocd erase -s` cleaned up. The demo firmware at page 0 untouched and still running.
- One bug on the way: a `None` value for the optional `pc_eraseAll` makes pyOCD's API validity check raise TypeError — omit the key instead.
- See `pyocd-target/README.md` for how to use it and what is still needed for an upstream PR.

### E-ink panel bring-up (2026-10-05, 17:00-17:50)

Method: puppeting the MCU pins from the host (scripts/disp_probe.py, eink_pon_scan.py, eink_uc81.py; swdburst.py = fast repeated register writes, ~16k writes/s).
- Only six MCU pins reach the panel connector (user): PC00-PC04 (pins 1-5) and PA08 (pin 29). They idle LOW whatever the internal pull (held down by the panel side).
- **RES = PC04, BUSY = PA08 (active low: low = busy/in reset, high = idle).** Found by pulsing each pin low and watching for responses: only PC04 pulses made PA08 rise (3/3).
- **SCK = PC01, SDA = PC00; CS/DC = PC02/PC03** — bit-banging command 0x04 (UC81xx power-on) made BUSY drop for exactly two assignments: (CS=PC02, DC=PC03) and (CS=PC03, DC=PC02), which are electrically identical for a bare command. Using CS=PC02, DC=PC03 so far; **it works** (data arrives), but which is truly CS vs DC is unresolved because both orders drive both low for commands — a data byte would tell them apart.
- **PC06 (pin 7, tp-back-40) is the display power path**: with PC06 driven HIGH the power-on command (0x04) never completes (BUSY stuck low); with PC06 LOW or released it completes in ~70 ms. Use `--power 6 --power-level 0`.
- Controller behaves like **UC8151/UC81xx** (BWR): PWR 0x01, booster 0x06, PON 0x04, PSR 0x00, resolution 0x61, 0x50, data 0x10 (black/white plane) and 0x13 (red plane), refresh 0x12, off 0x02; refresh takes ~17.7 s (BUSY low).
- The panel still showed the **original retail image** ("BREZZA INSTANT WMR $49.97 ... 0510"): e-paper keeps its last image.
- First refreshes with PSR 0x0F + wrong size only overwrote a band and faded the old image (partial waveform; border drove red = BWR panel confirmed). PSR **0xCF** (Good Display 2.13in BWR value; RES bits select a bigger scan area) + 212x104 gives a proper full-screen refresh (screen flickered and cleared).
- Shape: ~2:1 (212x104 or 250x122 likely). Test pattern `--pattern frame --id N` draws border, 32 px ticks, origin/opposite-corner squares and N dots to identify attempts.

### Display solved enough to draw (2026-10-05, ~18:00)

- **Panel: 250 x 128 pixels, black/white/red.** 16 bytes per line, 250 lines. Calibration pattern (`--pattern calib`): all 128 rows (y 0..127) are visible; the last 2-3 columns at each end are partly under the frame (vertical lines visible up to x=247, left border thin).
- Orientation with the connector on the right: x = line index 0..249 left to right; y = 0..127 **bottom to top**.
- **Colour planes:** command 0x10 plane: bit 0 = black, 1 = white. Command 0x13 plane: bit 0 = **red** (confirmed: a solid red rectangle), bit 1 = no red.
- Full working sequence: reset (RES low 20 ms, high, 100 ms); 0x01 [03 00 2B 2B 03]; 0x06 [17 17 17]; 0x04 + wait BUSY high (~70 ms); **0x00 [CF]** (0x0F caused partial/faded updates); 0x61 [128, 0, 250]; 0x50 [77]; 0x10 + 4000 bytes; 0x13 + 4000 bytes; 0x12 refresh (BUSY low ~17.7 s); 0x02 power off.
- Display power path PC06 must be LOW (high hangs the power-on command).
- Retail image from the original firmware was still on the glass ("BREZZA INSTANT WMR $49.97").
- `scripts/eink_draw.py [IMAGE|--demo] [--led]` converts any image to the three colours and shows it (host-driven over SWD, no firmware needed); LED shows progress (red reset, yellow init, green sending, blue refreshing, white done).
- Still unresolved: whether PC02 is CS and PC03 is D/C or the reverse (both orders worked for the tested commands; image data worked with CS=PC02, DC=PC03).

### CS vs DC resolved (2026-10-05, ~18:20)

Swapped roles (--cs 3 --dc 2) and drew the framed pattern with 5 dots: **no pattern appeared** — commands still worked (both lines low) but data frames, which hold only the real CS line low, were ignored.
=> **PC02 (MCU pin 3) = CS, PC03 (MCU pin 4) = D/C.** Full panel pin map: PC00 = SDA/MOSI, PC01 = SCK, PC02 = CS, PC03 = D/C, PC04 = RES, PA08 = BUSY (active low), PC06 = display power path (drive low).
Side observation: the controller's frame memory survives a hardware reset and power-off; a refresh without new data re-shows the last uploaded image, with black/red inverted relative to what was sent (old-data/new-data comparison).

### Spring contacts and the rail signal (user + tests, 2026-10-05, ~18:05)

- User: tp-back-12 (and therefore **pad-front-122**) reads **3.3 V**; **pad-front-121** = ground; **pad-front-123** = a third contact believed to be a **signal line** (the tag clips onto a shelf rail with ground / VCC / signal, like store rail-powered tags that are powered and reprogrammed in place). Also explains why there is no coin-cell holder.
- Test (`scripts/gpio_watch.py`, all free GPIOs as inputs, user tapping contact 123 through a resistor): with pull-ups and ground taps: no changes. With pull-downs and later 3.3 V taps: **only PB01 (MCU pin 19, pad-front-99, tp-back-33) responded** (72 transitions, bouncing, starting when the user switched to 3.3 V).
  => contact 123 reaches **PB01**, one-way (passes high, resists being pulled low: probably a diode or similar stage).
- Datasheet alternate-function table: **PB01 = EM4WU3 and the button PB03 = EM4WU4** are deep-sleep (EM4) wake-up pins — consistent with a tag that sleeps and wakes on rail activity or a button press. Other wake-capable pins: PC00 (WU6), PC05 (WU7), PC07 (WU8).
- Pins still unassigned: PA00 (21), PA03-PA07 (24-28), PC05 (6), PC07 (8), PD01-PD03 (38-40); NFC front end and coil still unidentified.

### NFC: there is no NFC chip on this board (2026-10-05, ~18:30)

User: the NFC antenna seems to trace back to MCU pins 26 (PA05) and 37 (PD03). What the netlist and photo (docs/images/overlay_ant_footprint.png) show:
- The coil's two ends land on nets NET153 / NET154, each shared by **three bare pad pairs** (pads 249/251/253 and 250/252/254: three parallel optional parts across the coil, likely tuning capacitors) and by pads **278 / 277** of an **8-pad footprint** the user labelled `ANT?` (pads 277-284).
- **Every pad in that area is bare solder: the footprint is unpopulated. No NFC IC is fitted.**
- The footprint's other pads: **282 = MCU pin 26 (PA05, tp-back-27)** with a bare pad 242 below it; **283 = MCU pin 37 (PD03, tp-back-29)** with bare pad 256 below it (likely I2C pull-up footprints); 279 = tp-back-37 / pad 245 (a third signal, maybe field-detect); 280, 281, 284 untraced.
- The coil does not appear to connect to the MCU pins directly: the pins reach pads 282/283 next to the antenna pads, as the data pins of a footprint for a tag IC would (an I2C NFC tag IC such as NXP NT3H2111 / ST25DV is the likely populated variant; unconfirmed).
- Test: PA05 and PD03 both follow internal pull-up/pull-down (no external pull-ups, nothing driving them): consistent with an empty footprint.
- To confirm the coil is not wired to the pins: multimeter continuity from a coil end (pad 277/278) to tp-back-27 and tp-back-29 should show no connection.

### RFID vs NFC (user question, 2026-10-05, ~18:35)

The coil is almost certainly **HF (13.56 MHz) RFID/NFC-band**, not low-frequency 125 kHz RFID: printed spiral ~34 x 9 mm, ~6 turns (rough guess 1-3 uH), plus **three parallel bare capacitor footprints** (pads 249-254) across it, i.e. a tuning network for ~50-150 pF.
The protocol (ISO 14443 vs 15693, tag IC vs reader IC) is decided by the unfitted chip; an I2C NFC tag IC (NT3H21xx / ST25DV-class) is a guess consistent with MCU pins PA05/PD03 reaching two pads of the footprint.
To verify: an LCR meter on the coil ends (pad 277 / 278) should read a few uH.

### NFC wrap-up (user, 2026-10-05, ~18:50)

- NFC: parked. Findings so far: HF-band coil, three bare tuning-capacitor footprints, an empty 8-pad IC footprint (277-284), PA05/PD03 wired to two of its pads; **no NFC chip visible anywhere on the board**. Inductance not measured (DSO-TC3 resonance method or LC meter would do it).
- Board revisions (user, ~18:55): the board we have been working on is **ContRD010A**; the second one the user took apart is **ContRD010C** — another revision of the same controller-board family, not a different product. Differences between A and C may be informative.
  Observed so far: on **C the component between pad-front-51 and pad-front-52 is unpopulated**; on **A** a dark SMD part is fitted there, linking spring contact 122 / net NET12 to net NET46. Function still unknown.
  Worth comparing on C: whether an NFC IC (or the tuning capacitors at pads 249-254 / the 8-pad footprint 277-284) is fitted, the 2x2 block 237-240, the LED-switch cluster, and the display connector area.

### A vs C comparison (user, ~19:00)

- The 8-pad footprint (277-284) is **unpopulated on both A and C**, and the surrounding population is similar. NFC is evidently not fitted on either revision.
- Pads **237-240 are unpopulated on both** A and C.
- So far the only difference found between ContRD010A and ContRD010C is the part between **pad-front-51 and pad-front-52** (fitted on A, absent on C).

### The part at pad-front-51/52 (user, ~19:05)

Marking on the fitted part on ContRD010A: **"5C" followed by a sideways T**. A web search only shows "5C" listed in one maker's SMD-code table for small two-terminal diode packages (SOD-123/323/523); SMD codes are not unique across manufacturers, so this is a hint that it may be a diode, **not an identification**. A diode test across pads 51/52 (forward drop one way, open the other = diode; same both ways = resistor/jumper) would settle it.

### Part at pad-front-51/52 measured (user, ~19:10; corrected ~19:15)

Component tester: **diode, arrow pointing left (pad 51) to right (pad 52)**, so anode on pad 51 (net NET46), cathode on pad 52 (net NET12 / spring contact 122). Marking "5C" + sideways T. Not populated on ContRD010C.
**Retracted:** the "Vf = 4.35 V" first reported was the tester's own battery voltage on its screen, not the diode's forward voltage, so the Zener/TVS-clamp hypothesis has no support. The real Vf (and Ir, "3.3 uA" is unverified too) still needs re-reading.
Open questions: real forward voltage (Schottky ~0.2-0.4 V vs silicon ~0.6-0.7 V); what NET46 is (the anode side); the voltages on pad 51 and pad 52 with the tag powered from the Pico (contact 122 / tp-back-12 reads 3.3 V).

### pyOCD: the official Silicon Labs DFP works (2026-10-05, ~19:50) — supersedes the builtin-target idea

- I had claimed pyOCD's pack index lacked EFR32 Series 2 devices. **Wrong:** the Keil index lists `GeckoPlatform_EFR32FG22_DFP` 2025.12.1 (and the other Series 2 families), and Silicon Labs' engineer stated on pyocd/pyOCD#1847 that DFP 2025.12.1 fixes the earlier memory-region and flash-loader problems.
- In our environment `pyocd pack find EFR32FG22` etc. return **no devices** (while `pack find EFM32` finds 42 older Silicon Labs devices). Scripted requests to silabs.com for the Series 2 .pdsc/.pack return **HTTP 403** (curl, browser user agent, and with a Referer); cause for pyOCD's behaviour unverified.
- The user downloaded `SiliconLabs.GeckoPlatform_EFR32FG22_DFP.2025.12.1.pack` (10.9 MB, from Silicon Labs' CMSIS-pack resources page) in a browser. It contains Flash/GECKOS2.FLM (Keil style) covering EFR32FG22C121F512GM40 (512 KiB), no debug sequences.
- **Stock pyOCD 0.45.1 with `--pack <file> -t efr32fg22c121f512gm40` works on our tag:** flash of 20000 random bytes at 0x10000: erased 3 sectors, programmed 24576 bytes at **42.8 kB/s**; read-back identical; `pyocd erase -s` works.
- `-O adi.v5.max_invalid_ap_count=0` removes the "Error probing AP#3" message (workaround from #1847), reads still work.
- Consequence: our hand-written algorithm/target (pyocd-target/) is **not needed** for FG22 if the pack can be obtained; it remains an independent cross-check (slower, 27 kB/s, no mass erase). The upstream PR was not made; an issue about pack discoverability/403 is the better contribution (draft in docs/pyocd-issue-draft.md).
- A fork `georgestephanis/pyOCD` was created while preparing the PR; nothing was pushed to it.

### Issue posted to pyOCD (2026-10-05, ~20:10)

- Posted as **https://github.com/pyocd/pyOCD/issues/2042** (from George's account, AI assistance declared: Claude Sonnet 5.5 via Claude Code): "Silicon Labs Series 2 packs (e.g. EFR32FG22) are listed in the index but `pyocd pack find/install` shows no such devices; works when the .pack is obtained by hand". Body: docs/pyocd-issue-draft.md (+ attribution line). Cross-links #1847, #1642, #1637, #280, #1223.
- Key data in it: after `pack update`, 0 of 86 non-deprecated SiliconLabs descriptors are in pyOCD's cache (1674 of 1823 total present); scripted requests to silabs.com return 403; the official FG22 DFP 2025.12.1 flashes/erases/reads back correctly on the tag via `--pack`.
- The fork georgestephanis/pyOCD (created while preparing the abandoned PR; no commits of its own) could NOT be deleted from the CLI: the gh token lacks the `delete_repo` scope. Delete it in the web UI (repo Settings > Danger Zone) or run `gh auth refresh -h github.com -s delete_repo` and then `gh repo delete georgestephanis/pyOCD --yes`.

### Image-receiver firmware (2026-10-05, ~20:50)

Goal (user): firmware so the tag can be wired to ground / 3.3 V / signal (the three spring contacts) and sent new images.
- `firmware/eink_receiver/receiver.c` (2424 bytes): software UART receiver on PB01 (the signal contact; one-way/diode-like path, so the pin's internal pull-down is used) with **auto-baud on a 0x55 sync byte** (timed with the DWT cycle counter; core clock measured 19.12 MHz), 8N1, ~2400-230400 baud.
  Frame: `0x55`, `A5 5A`, 8000 payload bytes (black/white plane 4000 + red plane 4000, as built by `scripts/eink_draw.py`), CRC-16/CCITT-FALSE (hi, lo). Only a good CRC triggers the ~18 s refresh. LED: green boot, blue receiving, red bad frame, white refreshing, green done.
- `scripts/build_fw.py` now handles multi-function programs (entry = function `reset`, located via llvm-nm; rejects relocations and data sections). The LED demo image is unchanged.
- `scripts/send_image.py PORT [IMAGE|--demo] [--baud 38400] [--crop ...]` builds the frame and writes it to any serial TX (CRC self-test: 0x29B1 for "123456789"). `scripts/eink_draw.py` is now importable (main guard).
- Flashed to the tag with stock pyOCD + the official DFP (`pyocd flash --pack ... --base-address 0 receiver.bin`, 8 KiB page erased/programmed, vector table read back OK) and the chip reset.
- Pico debugprobe UART: TX = **GP4 (pin 6)**, RX = GP5, USB serial `/dev/cu.usbmodem1302`.
- Not yet tested end to end (needs the Pico TX wired to pad-front-123 / the signal contact).

### Receiver test: signal path investigation (2026-10-05, ~20:10)

- Wired the Pico debugprobe's UART TX (GP4, pin 6) straight to the signal spring contact (pad-front-123; user says no series resistor). Sending the full demo frame with `send_image.py` (38400 baud): no LED change, panel unchanged.
- Tap test re-run (3.3 V from the rail to the contact, `gpio_watch.py`): **PB01 follows** (40 transitions), so the contact -> PB01 path works for a stiff 3.3 V source.
- `signal_test.py` (halt the core, poll PB01 over SWD while the Pico sends 0x55 at 300 and 9600 baud, idle level read with the port open): **0 transitions, idle reads 0**, even though the user's DSO-TC3 sees a 4.8 kHz square wave at the contacts (9600 baud 0x55).
- User's scope reading at the contacts: **about -1.4 V to +1.1 V (~2.5 V peak to peak)**, probably AC-coupled (centered on 0), but the amplitude is below the expected 3.3 V.
- Hypothesis (unverified): the signal contact line is **loaded**, so the Pico's weak (default ~4 mA) output sags to ~2.5 V; after the one-way element PB01 sees ~2 V, below its ~0.7 x VDD (~2.3 V) input threshold. The 3.3 V rail taps worked because they are stiff.
- To check: resistance signal contact <-> ground contact with the tag unpowered; DC-coupled scope levels at the contact; idle DC level. To test the receiver independent of this: drive PB01 directly via its test pad tp-back-33.

### Power through the center contact works; diode orientation corrected (2026-10-05, ~20:30)

- With the Pico's 3V3(OUT) on the **center contact (pad-front-122)** and ground common, and nothing on tp-back-31, the tag **boots** (receiver firmware: green blink). So **contact 122 is a power input**.
- With the tag powered from the test points, the center contact measured **2.92 V** (earlier idle reading 3.3 V): consistent with the board supply being ~0.4 V (a Schottky drop) below the contact when current flows, i.e. the 5C diode between pads 51/52 sits between the contact and the board supply. The component tester's "arrow" orientation therefore did not map to the pad assignment as I assumed; the direction of conduction contact -> board is what the boot test shows. Chip VDD when powered through the contact is therefore ~2.9 V (input threshold ~0.7 x VDD ~ 2.0 V).
- Signal contact with GP4 connected: **2.25 V** DC at the contact (user, meter, vs the ground contact): the Pico pin sags (line loaded). `signal_test.py` still sees **0 transitions on PB01** at 9600 and 38400 baud with the tag powered through the contact.
- Next: DC level at tp-back-33 (PB01 pad) with GP4 on the contact; then GP4 -> tp-back-33 for an end-to-end test of the receiver/display bypassing the contact circuit.

### Signal contact measurements and end of session (2026-10-05, ~21:00)

- Signal contact (`pad-front-123`) with nothing connected, tag powered through the centre contact: **about -0.15 to -0.2 V relative to the ground contact**, i.e. the line idles low (pulled down on the tag; the small negative is a ground offset).
- Centre contact, tag powered from the Pico 3V3 via tp-back-31: 3.3 V idle; **2.92 V while the receiver firmware runs**; ~3.1 V while the core is halted (less current, smaller diode drop). Consistent with a ~0.4 V diode between the contact and the board supply.
- Tag powered **through the centre contact alone boots** the receiver firmware (green blink): the centre contact is a real power input.
- Signal contact driven by the Pico's UART TX (GP4): scope sees the wave there (AC-coupled reading about -1.4 V to +1.1 V, ~2.5 Vpp; DC level ~2.25 V), but `signal_test.py` sees **no transitions on PB01** at 300, 9600 and 38400 baud, with the tag powered either way. Hypothesis: GP4 sags into the loaded line and PB01 sees < ~2 V (below its input threshold). A direct 3.3 V tap to the contact does move PB01.
- `scripts/setup.sh` now installs pyOCD + Pillow + pyserial into `.venv` (verified: scripts import, CRC self-test 0x29B1). The session's own scratch venv is gone; use `.venv`.
- Debug probe unplugged at the end of the session.

**Resume here:**
1. Move GP4 to `tp-back-33` (PB01's pad), power the tag via the centre contact, run `.venv/bin/python scripts/send_image.py /dev/cu.usbmodemXXXX --demo --baud 38400`. Expect blue -> white (~18 s) -> green and the demo card on the panel.
2. If that works: build/measure a proper driver for the contact (buffer or high-side stage).
3. Housekeeping: delete the fork georgestephanis/pyOCD (needs the `delete_repo` scope or the web UI); watch pyocd/pyOCD#2042 for a reply.
4. Optional explorations: sweep the unassigned pins; wake-from-sleep on PB01 / PB03; coil inductance; the "5C" diode.

### ContRD010C uses a different MCU (user, 2026-10-05, late)

The MCU on the **C revision** is marked **`ESWIN / EMU32VL170 / -A1 / A392K70102 / 2439AHA0`** (date code 2439 = 2024 week 39), not a Silicon Labs part.
From public sources (SEGGER J-Link knowledge base, https://kb.segger.com/ESWIN_EMU32VL170; a JLCPCB/LCSC listing exists for the part): ESWIN **EMU32VL17x** is a **RISC-V RV32EC** microcontroller with **128 KB flash at `0x25000000`**, a **7 KB bootloader area at `0x24000000`**, a watchdog (fed during flash programming) and a normal RISC-V reset; J-Link supports both flash banks. The page does not say which debug interface (JTAG / cJTAG / SWD-like) it uses.
Consequences: revision C is a different design (second-sourced/cost-reduced MCU), so **none of the firmware, pin map, debug pads or the Series 2 DCI unlock carries over**; pyOCD (Arm-only) won't support it. Anything on C would need its own tracing and a RISC-V-capable debugger (J-Link, or an OpenOCD RISC-V setup).
This also explains why the part at pads 51/52 and other population differs between A and C: they are distinct board designs sharing a product line and (apparently) the e-paper panel / mechanical layout.
- Orientation (user): on the C board the MCU's **pin-1 dot is rotated 90 degrees clockwise relative to the A board** (relative to the PCB). Anyone comparing the two boards' pad positions or tracing C must account for the chip being turned a quarter turn; the ESWIN part's package and pin count are not yet recorded (its pinout/debug pins unknown).

### Overnight research on the ESWIN EMU32VL170 (2026-10-05, late)

Web research only (no hardware): RISC-V RV32EC, QFN28 4x4, 128 KB flash at 0x25000000, 7 KB bootloader at 0x24000000, watchdog, J-Link/Flasher supported; **no datasheet, SDK, pinout or open-tool support found** (English and Chinese searches, GitHub). Details, sources and a search log in `docs/eswin-emu32vl170-research.md`. Conclusion: reprogramming rev C is plausible with a J-Link but needs its debug pads traced and has no public docs.

### Markings on the e-paper's flex cable (user, 2026-10-06)

User read: **`E528827 MBHT01`** plus a logo like a mirrored "R" fused with a "U" (= the **UL Recognized Component mark**).
UL file number **E528827 = Shenzhen People Electronics Co., Ltd.**, UL category ZPXK2 "Wiring, Printed - Flexible Material Constructions - Component" (https://productiq.ulprospector.com/ja/profile/5150718/zpxk2.e528827?term=ZPXK2&page=15).
So these markings are on the display's **flex cable (FPC)** and name its maker; "MBHT01" is probably the FPC's own part code (nothing public found). They do not identify the e-paper glass vendor or the controller.
Better identification ideas: measure the active area in mm (with 250x128 px gives the pixel pitch), inspect the driver IC bonded on the glass edge, and decode the sticker `KE2206JSKE1 / SPP2DC1 / 7MADCM6859`.

### More markings and an FCC lead (user + research, 2026-10-06)

- Back-side markings (user): `A1360146-00 / 2403 94V-0 / 02 55`. Interpretation: `2403` = date code YYWW (2024 week 3); `94V-0` = UL 94 flammability rating of the board/flex material; `A1360146-00` = a part/drawing number with revision suffix (no public hits); `02 55` = lot/position code (unknown). Which part carries them (flex cable vs main board) was not stated.
- **FCC filings exist for these tags.** Grantee code **2ACQM** (SES-imagotag GmbH / VusionGroup GmbH, Fernitz-Mellach, Austria); browse https://fccid.io/2ACQM (fetch tools get 403; the app's built-in browser works).
  2.1" models filed: EDB1-0210-A (VUSION 2.1, granted 2023-08-28), EWB1-0210-A (2.1 WP, 2023-12-11), EDG3-0210-A (2024-06-04), EDB2-0210-A (E300 2.1, 2025-04-02), EWB2-0210-A (E300 2.1 WP, 2025-04-14), EDG5-0210-A (V300 2.1, 2025-02-26), EDG6-0210-A. **No filing with the model name HRD3-0210-A was found** (that name may not be the US-filed one).
  EDB1-0210-A: 2402-2480 MHz DTS, emission designator 1M04F1D (~1 Mbps FSK-class), 0.00194 W; public exhibits: internal photos (PDF 1.5 MB), external photos, test setup photos, user manual, test report; block diagram and schematics are confidential (metadata only).
- Hypothesis (unverified): later 2.1" filings (2024-2025) might show the ESWIN-based board (rev C, date code 2439 = Sept 2024). The internal-photos exhibits could confirm which MCU/board each model uses.

### The e-paper panel is (almost certainly) a Pervasive Displays 2.06" (2026-10-06)

- User: the flex has **24 pins** (confirmed). Stickers on the reverse of a display: `SE2206JS0E1 / SPP2AC1 / U00E2T0VV9M`; the first panel's sticker (earlier) was `KE2206JSKE1 / SPP2DC1 / 7MADCM6859`.
- The sticker codes (`E2206...JS...E1`) match **Pervasive Displays' 2.06" family** (their listed models: E2206KS0E1 black/white fast-refresh wide-temperature; E2206QS061 four-colour Spectra 4). Public facts for the family (https://www.pervasivedisplays.com/products/2-06-e-ink-displays/): **248 x 128 pixels, 0.1875 mm pitch (135 dpi), active area 46.5 x 24.0 mm, outline 57.75 x 29.5 x 0.85 mm, internal driving with embedded waveform ("iTC")**, a-Si TFT, SPI. This matches our measurements: 128 rows, ~248 columns visible (we drove 250 lines; the last columns were hidden/ignored), controller with its own OTP waveform.
- Our panels are black/white/**red** (the `J` variant is presumably a red version; I found no public listing for E2206JS0E1, only the BW `K` and the BWRY `Q` variants).
- Public product specification for the BW sibling (28 pages, "tentative", 2023-09-01): https://www.mouser.com/datasheet/3/3772/1/1Pxxx_00_tentative_E2206KS0E1_20230901.pdf (fetching it timed out from here; contains the FPC pinout and driving sequence; read it in a browser).
- Retail context: E2206KS0E1 (BW) is about **$4.66 at DigiKey / $4.67 at Mouser**, in stock. Ready-made adapters: Good Display **DESPI-C02** (24-pin 0.5 mm FPC breakout, ~$6-9) and Waveshare **Universal e-Paper Raw Panel Driver Board** with ESP32 (~$15). A custom breakout is probably unnecessary.
- FCC filings for the 2.1" VUSION tags (grantee 2ACQM) have public internal photos; none found for model HRD3-0210-A.

### E-paper breakout idea (user, 2026-10-06)

User considered cloning the DESPI-C02 (~$8.50-10) from its Gerbers/photos. Recommendation recorded in `docs/epaper-breakout-plan.md`: design our own from the controller reference circuit + the panel datasheet (cross-check: Adafruit 2.13" eInk Bonnet, CC BY-SA, parts list extracted); KiCad (kicad-cli) is installed; needs the Pervasive 2.06" specification PDF (FPC pinout, circuit) downloaded in a browser.

### Pervasive 2.06" specification read (2026-10-06)

The user downloaded the product specification PDF; read pages 15-18. Full 24-pin FPC pinout and reference booster circuit (10 uH, MCH3478 MOSFET, 3x SS2040FL, 0.47 ohm, 4.7 uF + 1 uF/25 V caps) recorded in `docs/epaper-breakout-plan.md`. It confirms BUSY_N is active low, BS must be grounded for 4-wire SPI, and the supply should be switchable. Adafruit's CC BY-SA netlist matches the same topology.

### Flex photo and connector orientation (user, 2026-10-06)

Photo of the panel's flex: markings `1 A1360146-00 24 / 2403 / 94V-0 / 02 / 55` are on the flex; fingers numbered 1 (left) to 24 (right) with the fingers facing the viewer. On the original tag the fingers faced the board. The Hirose FH34SRJ-24S-0.5SH named in the panel datasheet is a top-and-bottom contact ZIF, so either orientation can work, but the pin order mirrors; see `docs/epaper-breakout-plan.md`.

### The booster's switching node on the tag board (user question, 2026-10-06)

`trace-front-127` (NET49: pad-front-68 and pad-front-264) ends with a sharp turn on the **upper pad of the large two-pad molded part = the boost inductor**, with its last segment heading to the **MOSFET (SOT-23, dark part to its left)**. Photo overlay: `docs/images/overlay_booster_switching_node.png`. NET49 therefore joins the inductor's upper terminal, the MOSFET drain, the first of the three Schottky diodes (pad 264 under it) and one end of the tan 1206-size capacitor (pads 68/67, probably the 4.7 uF/25 V flying capacitor): the switching node of the booster, same topology as Pervasive's reference circuit and Adafruit's bonnet. Inductor value not measured (reference: 10 uH); markings unreadable.
Also: pads 59-78 (pairs with one GND pad) along the left edge next to the connector are very probably the 1 uF output capacitors; tp-back-45/49/50 are probably booster/panel rail test points (possibly high voltage), tp-back-40 = PC06 (power-path control), tp-back-46 unknown.

### Panel power switch (user hypothesis, checked 2026-10-06)

- `trace-front-121` (NET14 = the main 3.3 V rail) runs along the bottom of the MCU side to **`pad-front-259`**, next to a **dark 3-lead SOT-23-type transistor** flanked by two 0201 resistor pairs (259/260 right, 261/262 left): photo overlay `docs/images/overlay_panel_power_switch.png`. Interpretation: the input side of the panel's **load switch**.
- `trace-back-41` (a trace, NET35) only joins via-1, via-7 and `tp-back-40`; via-7 is MCU pin 7 (PC06, pad-front-88). **Not yet traced onward to the transistor.** (Do not confuse trace-back-41 with `tp-back-41` = PA08 BUSY.)
- Consistent with experiments: PC06 high -> panel power-on hangs (supply cut); PC06 low or floating -> works. So the switch is **on by default / when PC06 is low or released, off when PC06 is high**; matches the panel datasheet's advice for a switchable supply.
- Correction to the earlier guess: **`tp-back-45` (NET40: pad 60 with GND pad 59, i.e. a capacitor, plus pad 262)** is more likely the **switched panel supply output** than a high-voltage rail; `tp-back-49`/`tp-back-50` may still be booster rails. Validation: with the chip in reset (PC06 floating) tp-back-45 should read about the rail; tying tp-back-40 to 3.3 V through 1 kOhm should drop tp-back-45 to ~0 V.

### Re-traced SVG (user, 2026-10-06 12:55; reviewed by comparing nets, not NETn labels)

Compared the new export with the committed one by connectivity: **no old net was split and no pad removed**; 64 pads added (293-356), many previously isolated pads joined to existing nets. SWD pads, nRESET, PB01's pad and the display pins (PC00-PC04, PA08) are unchanged apart from extra pads on each net. Component records now exist in the SVG (`comp-front-1..4`) and the SVG states its scale: **55.07 px/mm** (matches the 0.4 mm QFN pitch = 22 px).

- **The "5C" diode needs re-checking.** Pad 51 (anode, per the component tester) was alone with the unpopulated pads 238/240; it is now on **GND**, while pad 52 stays on the centre-contact net (pad 122, tp-back-12/35). If right, the diode is a clamp from GND to the 3.3 V contact, not a series diode, and then nothing traced links the contact net (NET12) to the chip VDD net (NET14); the "VDD is one diode drop below the contact" explanation is **unproven**. To verify: continuity from pad 51 to ground, and what bridges contact net to NET14.
- **Signal contact:** `pad-front-123` (NET1) now reaches pads 213, 215, 217, 294 and tp-back-1/13. PB01's net (pads 99, 184, tp-back-33) is still separate, so the one-way element between them is still not in the netlist.
- **comp-front-3 (pads 341-344)**: 4 pads in a 2x2 grid (0.74 x 0.52 mm centres, pads ~0.4 x 0.2 mm) on NET117, VDD (NET14), PC06 (NET35, tp-back-40) and NET40 (tp-back-45, the switched panel rail). That net pattern is a **4-pin load switch** (VDD in, panel rail out, PC06 control), refining the earlier "dark 3-lead SOT-23 transistor" reading above. Pads 259-262 sit on the same spot and share nets with it, so they are probably duplicates of the same footprint; NET117 is untraced.
- **comp-front-4 (pads 353-356)**: 4 pads (0.62 x 0.7 mm centres, ~0.22 x 0.42 mm): GND, NET24 (tp-back-26 only), NET106 (pad 208), and NET152 (untraced). Function unknown.
- **comp-front-2** (pads 315/316, user note "MOSFET?"): pads are 3.4 x 1.4 mm, 2.2 mm apart, so this is the boost inductor (nets NET48 = switching node, NET40 = switched rail), not a MOSFET.
- **NFC group:** pads 249-254 plus 277/278 on two nets, consistent with the earlier note (coil ends, three parallel tuning-cap pairs, 8-pad footprint).
- Photos (user): the booster/connector cluster matches the Pervasive reference (inductor, MOSFET + sense resistor, three "AK" Schottky diodes, caps); a small diode-style part marked "ZV" (user's reading) sits at the connector's lower end, not in the reference circuit: probably a Zener/clamp, unconfirmed. MCU marking in the photo reads ...2327 where our earlier note says 2344: maybe a different tag or a misread.
- The two 4-pad footprints and others were contributed to the user's circuit-tracer catalog: georgestephanis/circuit-tracer#3.

### Re-trace, 13:17 (user combined overlapping nets)

Only two merges, no pads added or moved: pad 218 joined PD01's net (NET3, tp-back-3), harmless; and **PA00's net (pad 118, 201, 203, 348, tp-back-22) merged into the chip VDD net (NET14)**. That puts PA00 directly on VDD. Unlikely to be real unless the pads join through copper only (a pull-up resistor would not merge nets), so treat it as a possible overlapping-trace artifact. Check: with the chip running, read PA00 (`scripts/pins.py`/`gpio_watch.py`) with its pull-down on, or measure tp-back-22 against tp-back-15; if it floats low, the merge is wrong.

## 2026-10-07

### Second tag: unlock, flash and first draw over SWD

- A second ContRD010A tag, wired to the Pico debugprobe as in the README (GP1 nRESET, GP2 SWCLK, GP3 SWDIO, 3V3 and GND). `pyocd list` showed the probe; `scripts/dci.py status` answered
  (DPIDR `0x6ba02477`, DCIID `0xdc11d`) and reported the **factory lock**: SESTATUS words `[0x20, 0x101020c, 0xffffffff, 0x27, 0xffffffff]` -> debug lock configured, device erase allowed, secure debug on, hw LOCKED.
- `dci.py erase` (the SE answers with length word `0x4`, then the link drops: normal). **A power cycle is required** (pulling the 3V3 wire and reconnecting it was enough; nRESET alone is not).
  After it the lock word was `0x2`: lock off, erase still allowed, hw unlocked.
- Flashed `firmware/eink_receiver/receiver.bin` with the README's `pyocd flash` command (official Silicon Labs pack via `--pack`). The first words read back matched the file (SP `0x20008000`, reset vector `0x45`), the core ran, and the tag showed its green boot blink.
  Only the first 16 bytes were compared, not the whole image.
- `scripts/eink_draw.py --demo --led` drew the demo through the MCU over SWD: **refresh 21.6 s**. The harmless "Error probing AP#3" line appears every time.

### The panel only shows 248 of the 250 lines (user observation)

The demo's one-pixel border was missing on the right edge. Cause: we send 250 lines (x = 0..249, connector on the right) but the 2.06" panel is 248 px wide, so lines 248 and 249 are not displayed and the border drawn at x = 249 fell off.
Fix: `VIS_W = 248` in `scripts/eink_draw.py`; the demo's border/header use it, and `fit()` fits real images to 248 columns and pads the last two lines with white. The user confirmed the border shows afterwards.

### LED brightness: 10 % by software PWM (user request)

The LED was "painfully bright" (full current, common anode). There is no dimming control other than the supply-enable pin, so dimming is **software PWM on PD00** (which gates all three colours), about 1.16 kHz (period 2^14 cycles at ~19 MHz).

- `firmware/led_brightness/led.c` (new): shows green at 100 / 60 / 40 / 25 / 10 % duty, 3 s each. The user picked **10 %** ("everything else is really bright").
- `firmware/eink_receiver/receiver.c`: `led()` now only selects the colour; `led_tick()` does the PWM and is called from `delay_cycles()`, `epd_wait_idle()` and the e-paper plane loop (so the LED is dimmed during boot, the refresh and the result blink). **The LED is off while receiving**: `led_tick()` inside `wait_until()`/`sample_byte()` would disturb the bit sampling, so the old "blue = receiving" state is gone. Not yet tested end to end with a real frame.
- The host-driven scripts (`eink_draw.py --led`, `eink_uc81.py --led`) cannot dim: the core is halted and the pin is held static. `--led` is opt-in; leave it off.
- Build gotcha: a chain of `?:` returning constants was turned into a switch **lookup table** (`.Lswitch.table.reset`), which `build_fw.py` rejects (relocations against `.text`). Use explicit calls or arithmetic, no constant tables.

### Direct drive: the Pico talks SPI to the panel through the display test points, MCU held in reset

Seven test points on the right side of the coil/test-pad side go straight to the panel's connector pins (they also reach the MCU pads, which are Hi-Z while the MCU is in reset). Wiring used (series resistor of ~330 ohm per Pico-driven line recommended: the tag's rail is ~2.9 V, the Pico drives 3.3 V):

| Tag test point | Signal | MCU pin | Pico GPIO (pin) |
|---|---|---|---|
| tp40 | panel power path (PC06, drive LOW = on) | PC06 | GP16 (21) |
| tp42 | CS | PC02 | GP17 (22) |
| tp48 | SCK | PC01 | GP18 (24) |
| tp43 | SDA (MOSI) | PC00 | GP19 (25) |
| tp47 | D/C | PC03 | GP20 (26) |
| tp44 | RES | PC04 | GP21 (27) |
| tp41 | BUSY (low = busy) | PA08 | GP22 (29) |
| tp23 | tag nRESET (hold LOW) | RESETn | GP1 (2) |

(Pico pins 23 and 28 are spare GNDs between the signals.) GP17-GP19 are the Pico's hardware SPI0 (CS, SCK, TX).

- The Pico's debugprobe firmware cannot drive arbitrary GPIOs, so the Pico was switched to **MicroPython v1.29.0** (`RPI_PICO-20260824-v1.29.0.uf2`) by hand: unplug, hold BOOTSEL, plug in, copy the UF2 to `RPI-RP2`. (A running debugprobe cannot reboot itself to BOOTSEL.) `mpremote` installed into the project venv.
- Pre-check with the MCU held in reset and PC06 low: BUSY read **0 with no pull, pull-up and pull-down alike**: the panel actively drives BUSY low until it has been reset and powered on. Normal for a UC81xx.
- `scripts/make_frame.py` builds an 8000-byte frame (4000 black/white plane + 4000 red plane, same layout as the SWD route); `scripts/pico_eink.py` is the MicroPython driver (same init as `eink_draw.py`: reset, 0x01, 0x06, 0x04 + wait, 0x00 0xCF, 0x61, 0x50 0x77, planes 0x10 and 0x13, 0x12 refresh, 0x02 power off).
  `mpremote cp frame.bin :frame.bin; mpremote run scripts/pico_eink.py`.
- **Result: it works.** Refresh 21.6 s, the panel drew the "Driven by a Pico" demo frame with no help from the tag's MCU. This confirms the seven test points, the CS/DC assignment and that the panel needs nothing from the MCU.
- To go back to SWD debugging, flash `debugprobe_on_pico-v2.3.1.uf2` (raspberrypi/debugprobe release debugprobe-v2.3.1) through BOOTSEL again.

### Timing, tone and half-tone experiments (2026-10-07, evening)

Pico direct drive (MicroPython, 2 MHz SPI, MCU held in reset). Full write-up with photos: [display.md](display.md#timing-where-a-refresh-spends-its-time).

- Phase timings: reset 120 ms, power on 50 ms, each plane upload ~20 ms, **refresh 21.81 s (later 22.99 s)**, power off 20 ms: the refresh is 99 % of the ~22 s total. So the interface (MCU, Pico or SWD host) does not matter for speed.
- Black/white mode (PSR `0xDF`): refresh **19.76 s**; partial window in that mode also 19.76 s (the window did not shorten the waveform; the visible region was not the one asked for).
- KW-mode data: new bit 1 -> burgundy, 0 -> white, **independent of the old state** (three old bands, identical results); polarity inverse to the three-colour black/white plane.
- (bw 0, red 0) = plain red: red wins; no fourth per-pixel colour.
- Dithering: Floyd-Steinberg gradients and 9-step Bayer swatches in black/white, red/white and red/black all work well; photos in `docs/images/tones-*.jpg`.
- Practical snags: a `pio device monitor` (PlatformIO serial monitor) left running in another terminal held the Pico's serial port and made `mpremote` fail with "failed to access ... in use by another program" (found with `lsof`, closed by the user).
- Added: `scripts/make_tone_tests.py`, `scripts/pico_uc81_probe.py`.
