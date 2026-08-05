"""Build the launcher into a single-file Windows executable with Nuitka.

Run from the repository root:

    python build_nuitka.py

The version stamped into the executable's metadata is read from the VERSION
file, the same file the running application reads, so a build cannot claim a
version the application does not report.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from version import APP_NAME, __version__

REPO_ROOT = Path(__file__).resolve().parent
DIST_DIR = REPO_ROOT / "dist"

ICON_FILENAME = "filament.ico"

ENTRY_SCRIPT = "main.py"

# Windows PE metadata wants four numeric components; VERSION carries three.
PE_VERSION_COMPONENTS = 4

DESCRIPTION = "Launcher for Klipper printer dashboards and helper tools"


def pe_version(version: str) -> str:
    """Pad a semantic version out to the four components Windows expects.

    A pre-release suffix such as the 0.0.0-dev fallback has no place in PE
    metadata, so only the leading numeric components are kept.
    """

    numeric = version.split("-", 1)[0]
    parts = [p for p in numeric.split(".") if p.isdigit()][:PE_VERSION_COMPONENTS]
    parts += ["0"] * (PE_VERSION_COMPONENTS - len(parts))
    return ".".join(parts)


def build_command() -> list[str]:
    """The full Nuitka invocation, including the version metadata flags."""

    stamped = pe_version(__version__)
    return [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={ICON_FILENAME}",
        f"--product-name={APP_NAME}",
        f"--product-version={stamped}",
        f"--file-version={stamped}",
        f"--file-description={DESCRIPTION}",
        "--follow-imports",
        "--output-dir=dist",
        ENTRY_SCRIPT,
    ]


def require_nuitka() -> None:
    """Stop with something actionable when the packaging tool is absent.

    Nuitka is build tooling rather than a runtime dependency, so it is declared
    in requirements-dev.txt and a virtual environment built from
    requirements.txt alone will not have it. Left to itself the build reports
    only "No module named nuitka" wrapped in a CalledProcessError traceback,
    which says nothing about where to get it.
    """

    if importlib.util.find_spec("nuitka") is not None:
        return

    print(
        "Nuitka is not installed in this interpreter:\n"
        f"  {sys.executable}\n\n"
        "It is build tooling rather than a runtime dependency, so it is\n"
        "declared in requirements-dev.txt. Install it with:\n\n"
        "  python -m pip install -r requirements-dev.txt\n",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main() -> None:
    # Checked before the output directory is touched: a missing build tool must
    # not cost the previous build.
    require_nuitka()

    if DIST_DIR.is_dir():
        print("Removing existing dist directory...")
        shutil.rmtree(DIST_DIR)

    cmd = build_command()
    print(f"Building {APP_NAME} {__version__}")
    print("Running:", " ".join(cmd))
    # Every element of cmd is built from constants in this file and the
    # VERSION file, so there is no untrusted input and no shell involved.
    subprocess.check_call(cmd, cwd=REPO_ROOT)  # noqa: S603


if __name__ == "__main__":  # pragma: no cover
    main()
