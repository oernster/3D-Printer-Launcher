#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for building on Debian / Ubuntu / Linux Mint.
#
# Example system setup:
#   sudo apt update
#   sudo apt install -y python3 python3-venv python3-pip build-essential
#   python3 -m venv venv
#   source venv/bin/activate
#   pip install --upgrade pip
#   pip install -r requirements.txt
#   pip install nuitka ordered-set zstandard
#
# Then run (from the repo root):
#   ./build_nuitka_debian.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/build_nuitka_unix.sh" "$@"

