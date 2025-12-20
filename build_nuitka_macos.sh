#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for building on macOS.
#
# Prerequisites (example, adjust to your setup):
#   brew install python@3
#   # Optionally create a virtualenv in this repo:
#   python3 -m venv venv
#   source venv/bin/activate
#   pip install --upgrade pip
#   pip install -r requirements.txt
#   pip install nuitka ordered-set zstandard
#
# Then run:
#   ./build_nuitka_macos.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/build_nuitka_unix.sh" "$@"

