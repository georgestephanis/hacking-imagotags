#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Create a local venv with everything the scripts need: pyOCD (debug/flash), Pillow (image conversion), pyserial (send_image.py).
# Run from anywhere: scripts/setup.sh.  Firmware builds additionally need Homebrew LLVM: brew install llvm
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q pyocd pillow pyserial
./.venv/bin/pyocd --version
./.venv/bin/python -c "import PIL, serial; print('Pillow', PIL.__version__, '| pyserial', serial.__version__)"
./.venv/bin/pyocd list
