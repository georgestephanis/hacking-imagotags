#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Rename the auto-numbered pad / net / component IDs of the ContRD010A circuit-tracer export to names that say what they are.

usage: rename_netlist.py IN.svg OUT.svg [OUT-netlist.json] [id-map.json]

Every ID token is replaced consistently everywhere it appears (id=, data-connects, data-pads, data-vias, the embedded JSON). Unknown pads keep
their original IDs. Net labels (NETn) are renumbered by the tracer on every save, so nets are named from the pads we know sit on them.
"""
import json, re, sys

# --- known pads -------------------------------------------------------------------------------------------------------------
TP = {  # test points on the coil / test-pad side
    "tp-back-18": ("tp-swclk-pa01", "DBG_SWCLK"), "tp-back-19": ("tp-swdio-pa02", "DBG_SWDIO"),
    "tp-back-17": ("tp-swo-pa03", "DBG_SWO"), "tp-back-23": ("tp-nreset", "DBG_NRESET"),
    "tp-back-15": ("tp-vdd-1", "VDD"), "tp-back-31": ("tp-vdd-2", None),
    "tp-back-16": ("tp-gnd-1", None), "tp-back-39": ("tp-gnd-2", None),
    "tp-back-12": ("tp-vin-3v3-1", "VIN_3V3"), "tp-back-35": ("tp-vin-3v3-2", None),
    "tp-back-1": ("tp-sig-spring-1", "SPRING_SIG"), "tp-back-13": ("tp-sig-spring-2", None),
    "tp-back-43": ("tp-disp-sda-pc00", "DISP_SDA"), "tp-back-48": ("tp-disp-sck-pc01", "DISP_SCK"),
    "tp-back-42": ("tp-disp-cs-pc02", "DISP_CS"), "tp-back-47": ("tp-disp-dc-pc03", "DISP_DC"),
    "tp-back-44": ("tp-disp-res-pc04", "DISP_RES"), "tp-back-41": ("tp-disp-busy-pa08", "DISP_BUSY"),
    "tp-back-40": ("tp-disp-pwr-en-pc06", "DISP_PWR_EN"), "tp-back-45": ("tp-disp-vcc-switched", "DISP_VCC_SWITCHED"),
    "tp-back-49": ("tp-boost-rail-a", "BOOST_RAIL_A"), "tp-back-50": ("tp-boost-rail-b", "BOOST_RAIL_B"),
    "tp-back-24": ("tp-btn-pb03", "BTN"), "tp-back-33": ("tp-sig-pb01", "SIG_PB01"),
    "tp-back-36": ("tp-led-en-pd00", "LED_EN"), "tp-back-10": ("tp-led-g-gate-pb00", "LED_G_GATE"),
    "tp-back-4": ("tp-led-red-cathode", "LED_R_CATHODE"), "tp-back-6": ("tp-led-green-cathode", "LED_G_CATHODE"),
    "tp-back-7": ("tp-led-blue-cathode", "LED_B_CATHODE"),
    "tp-back-22": ("tp-pa00", None), "tp-back-21": ("tp-pa04", "GPIO_PA04"), "tp-back-27": ("tp-pa05", "GPIO_PA05"),
    "tp-back-20": ("tp-pa06", "GPIO_PA06"), "tp-back-38": ("tp-pc05", "GPIO_PC05"), "tp-back-25": ("tp-pc07", "GPIO_PC07"),
    "tp-back-3": ("tp-pd01", "GPIO_PD01"), "tp-back-28": ("tp-pd02", "GPIO_PD02"), "tp-back-29": ("tp-pd03", "GPIO_PD03"),
}
SPRINGS = {"pad-front-121": "spring-gnd", "pad-front-122": "spring-vin-3v3", "pad-front-123": "spring-sig"}
# QFN40 pin -> (pad id, name); numbering counter-clockwise from the pin-1 dot (top of the left side in photos/mcu-side.jpg)
MCU = [79, 83, 84, 85, 86, 87, 88, 89, 90, 91, 82, 92, 93, 94, 95, 96, 97, 98, 99, 100,
       118, 117, 116, 115, 114, 113, 112, 111, 110, 81, 109, 108, 107, 106, 105, 104, 103, 102, 101, 80]
PINS = ["PC00", "PC01", "PC02", "PC03", "PC04", "PC05", "PC06", "PC07", "HFXTAL_I", "HFXTAL_O", "RESETn", "RFVDD", "RFVSS", "RF2G4_IO",
        "PAVDD", "PB04", "PB03", "PB02", "PB01", "PB00", "PA00", "PA01", "PA02", "PA03", "PA04", "PA05", "PA06", "PA07", "PA08",
        "DECOUPLE", "VREGSW", "VREGVDD", "VREGVSS", "DVDD", "AVDD", "IOVDD", "PD03", "PD02", "PD01", "PD00"]
COMPS = {"comp-front-1": "fp-nfc-ic", "comp-front-2": "l-boost", "comp-front-3": "u-panel-load-switch", "comp-front-4": "fp-unknown-4pad"}


def main():
    src = open(sys.argv[1]).read()
    m = re.search(r'(id="circuit-tracer-data">\s*<!\[CDATA\[)(.*?)(\]\]>)', src, re.S)
    data = json.loads(m.group(2))
    net_of = {}
    for n in data["nets"]:
        for p in n["padIds"]: net_of[p] = n["label"]
    ids, nets = {}, {}
    for old, (new, net) in TP.items():
        ids[old] = new
        if net and old in net_of: nets[net_of[old]] = net
    ids.update(SPRINGS)
    for pin, (pad, name) in enumerate(zip(MCU, PINS), 1):
        old = f"pad-front-{pad}"
        ids[old] = f"mcu-{pin:02d}-{name.lower()}"
        lab = net_of.get(old)
        if lab and lab not in nets and lab != "GND": nets[lab] = f"PIN{pin:02d}_{name.upper()}"
    for n, new in ((285, "led-pad-1"), (286, "led-pad-2"), (287, "led-pad-3"), (288, "led-pad-4"), (289, "led-pad-5"), (290, "led-pad-6")):
        ids[f"pad-back-{n}"] = new
    ids.update(COMPS)
    if "NET14" in net_of.values() and any(v == "VDD" for v in nets.values()) is False: pass
    mapping = dict(ids); mapping.update(nets)
    pat = re.compile(r"(?<![A-Za-z0-9_-])(" + "|".join(sorted(map(re.escape, mapping), key=len, reverse=True)) + r")(?![A-Za-z0-9_-])")
    out = pat.sub(lambda mo: mapping[mo.group(1)], src)
    open(sys.argv[2], "w").write(out)
    m2 = re.search(r'(id="circuit-tracer-data">\s*<!\[CDATA\[)(.*?)(\]\]>)', out, re.S)
    d2 = json.loads(m2.group(2))
    if len(sys.argv) > 3: json.dump(d2, open(sys.argv[3], "w"), indent=1)
    if len(sys.argv) > 4: json.dump({"ids": ids, "nets": nets}, open(sys.argv[4], "w"), indent=1, sort_keys=True)
    print(f"renamed {len(ids)} ids and {len(nets)} nets; {len(d2['nets'])} nets, {len(d2['components'])} components in the JSON")


main()
