#!/usr/bin/env bash
set -euo pipefail

# Nuitka build script for macOS and Linux, for every distribution.
#
# This mirrors the options in build_nuitka.py and build_nuitka.cmd, minus the
# Windows-only flags. The version stamped into the binary is read from the
# VERSION file, the same file the running application reads.
#
# Usage (from the repo root):
#   ./build_nuitka_unix.sh
#
# Set PYTHON_BIN to choose the interpreter, for example:
#   PYTHON_BIN=./venv/bin/python ./build_nuitka_unix.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

# Print the prerequisites for whichever package manager this machine has, so
# one script covers Debian, Fedora, RHEL, Arch, Void and macOS.
print_prerequisites() {
  local packages
  if command -v apt >/dev/null 2>&1; then
    packages="sudo apt update && sudo apt install -y python3 python3-venv python3-pip build-essential patchelf"
  elif command -v dnf >/dev/null 2>&1; then
    packages="sudo dnf install -y python3 python3-devel python3-pip gcc gcc-c++ make patchelf"
  elif command -v pacman >/dev/null 2>&1; then
    packages="sudo pacman -S --needed python python-pip base-devel patchelf"
  elif command -v xbps-install >/dev/null 2>&1; then
    packages="sudo xbps-install -S python3 python3-pip base-devel patchelf"
  elif command -v zypper >/dev/null 2>&1; then
    packages="sudo zypper install -y python3 python3-devel python3-pip gcc gcc-c++ make patchelf"
  elif command -v brew >/dev/null 2>&1; then
    packages="brew install python"
  else
    packages="(no known package manager found: install Python 3, pip and a C toolchain)"
  fi

  echo "System prerequisites for this machine:" 1>&2
  echo "  ${packages}" 1>&2
  echo "Then, in an activated venv:" 1>&2
  echo "  pip install -r requirements.txt" 1>&2
  echo "  pip install nuitka ordered-set zstandard" 1>&2
  echo 1>&2
}

VERSION_FILE="${REPO_ROOT}/VERSION"
if [ -r "${VERSION_FILE}" ]; then
  APP_VERSION="$(tr -d '[:space:]' < "${VERSION_FILE}")"
else
  # Matches the fallback in version.py so the two never disagree.
  APP_VERSION="0.0.0-dev"
fi

# Nuitka wants a plain numeric product version, so drop any suffix.
PRODUCT_VERSION="${APP_VERSION%%-*}"

DIST_DIR="${REPO_ROOT}/dist"
if [ -d "${DIST_DIR}" ]; then
  echo "Removing existing dist directory..." 1>&2
  rm -rf "${DIST_DIR}"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

print_prerequisites

echo "Using Python interpreter: ${PYTHON_BIN}" 1>&2
echo "Building 3D Printer Launcher ${APP_VERSION} with Nuitka..." 1>&2

"${PYTHON_BIN}" -m nuitka \
  --onefile \
  --enable-plugin=pyside6 \
  --product-name="3D Printer Launcher" \
  --product-version="${PRODUCT_VERSION}" \
  --file-version="${PRODUCT_VERSION}" \
  --file-description="Launcher for Klipper printer dashboards and helper tools" \
  --follow-imports \
  --output-dir=dist \
  main.py

echo 1>&2
echo "If the build succeeded, your single-file executable is in dist/main" 1>&2
