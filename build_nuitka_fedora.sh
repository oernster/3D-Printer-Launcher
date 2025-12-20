#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for building on Fedora.
#
# Example system setup:
#   sudo dnf install -y python3 python3-venv python3-pip gcc gcc-c++ make
#   python3 -m venv venv
#   source venv/bin/activate
#   pip install --upgrade pip
#   pip install -r requirements.txt
#   pip install nuitka ordered-set zstandard
#
# Then run:
#   ./build_nuitka_fedora.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/build_nuitka_unix.sh" "$@"

