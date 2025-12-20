#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for building on Arch Linux / Manjaro.
#
# Example system setup:
#   sudo pacman -Syu --needed python python-virtualenv python-pip base-devel
#   python -m venv venv
#   source venv/bin/activate
#   pip install --upgrade pip
#   pip install -r requirements.txt
#   pip install nuitka ordered-set zstandard
#
# Then run:
#   ./build_nuitka_arch.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/build_nuitka_unix.sh" "$@"

