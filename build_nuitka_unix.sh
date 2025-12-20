#!/usr/bin/env bash
set -euo pipefail

# Generic Nuitka build script for macOS and Linux.
#
# This mirrors the options used in [`build_nuitka.py`](build_nuitka.py:1) and
# [`build_nuitka.cmd`](build_nuitka.cmd:1), but omits the Windows-only
# `--windows-console-mode=disable` flag.
#
# Usage (from the repo root):
#   ./build_nuitka_unix.sh
#
# You may optionally set PYTHON_BIN to control which Python is used, e.g.:
#   PYTHON_BIN=./venv/bin/python ./build_nuitka_unix.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

DIST_DIR="${REPO_ROOT}/dist"
if [ -d "${DIST_DIR}" ]; then
  echo "Removing existing dist directory..."
  rm -rf "${DIST_DIR}"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Using Python interpreter: ${PYTHON_BIN}" 1>&2
echo "Building with Nuitka (onefile, PySide6 plugin enabled)..." 1>&2

"${PYTHON_BIN}" -m nuitka \
  --onefile \
  --enable-plugin=pyside6 \
  --follow-imports \
  --output-dir=dist \
  main.py

echo
echo "If the build succeeded, your single-file executable is in dist/main" 1>&2

