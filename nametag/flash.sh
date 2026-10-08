#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Flash the name-badge firmware (at 0x0) and the page images (at 0x2000) to an unlocked ContRD010A tag over SWD.
#   usage: nametag/flash.sh PATH/TO/SiliconLabs.GeckoPlatform_EFR32FG22_DFP.<version>.pack [pages.bin]
# pages.bin defaults to ./nametag-out/pages.bin (make it with nametag/make_pages.py). Set PYOCD to the pyocd executable if it is not on PATH.
# The tag must be wired as in docs/flashing.md and already unlocked; this erases only the flash pages it writes.
set -euo pipefail
PACK="${1:?usage: flash.sh PACK.pack [pages.bin]}"
PAGES="${2:-nametag-out/pages.bin}"
PYOCD="${PYOCD:-pyocd}"
HERE="$(cd "$(dirname "$0")" && pwd)"
COMMON=(--pack "$PACK" -t efr32fg22c121f512gm40 -f 1000000 -O adi.v5.max_invalid_ap_count=0)
"$PYOCD" flash "${COMMON[@]}" --base-address 0x0 "$HERE/nametag.bin"
"$PYOCD" flash "${COMMON[@]}" --base-address 0x2000 "$PAGES"
"$PYOCD" commander "${COMMON[@]}" -c "read32 0x2000 2" -c "reset" -c "status"     # header: 0x31534750 (PGS1) and the page count
