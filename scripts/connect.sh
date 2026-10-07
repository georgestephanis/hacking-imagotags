#!/usr/bin/env bash
# Open a pyOCD commander session on the (unlocked) tag. 20 kHz is the only reliably stable clock so far.
# Retries because the first SWD handshake is flaky. Extra args are passed through, e.g.
#   scripts/connect.sh -c "read32 0x00000000 32"
cd "$(dirname "$0")/.."
for i in 1 2 3 4 5; do
  ./.venv/bin/pyocd commander -t cortex_m -f 20000 -O connect_mode=attach "$@" && exit 0
done
exit 1
