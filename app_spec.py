# app_spec.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


def _compute_base_dir() -> Path:
    """Return the real project root on disk.

    When running from source, this is the directory containing this file.
    When running as a compiled onefile Nuitka executable, module
    ``__file__`` points into the temporary extraction directory, but we
    want the directory that contains the *outer* executable so that
    ``qidi-temps/``, ``qidiwebcamdrestart/``, etc. are found correctly.
    """

    # Nuitka sets ``__compiled__ = True`` for compiled code; many
    # packagers also set ``sys.frozen``. We treat either as "frozen" and
    # derive the base directory starting from the executable path
    # (sys.argv[0]).
    is_compiled = "__compiled__" in globals() or getattr(sys, "frozen", False)
    if is_compiled:
        exe_dir = Path(sys.argv[0]).resolve().parent

        # When built with Nuitka onefile, you currently get:
        #   dist/main.exe
        #   qidi-temps/
        #   qidiwebcamdrestart/
        #   VoronTemps/
        # i.e. the project folders live *next to* ``dist``, not inside it.
        # When you later ship the app, you might instead place
        # ``main.exe`` directly alongside those folders.
        #
        # To support both layouts, we probe `exe_dir` first, then its
        # parent, and pick the first one that actually contains the
        # tool subdirectories.
        candidates = [exe_dir, exe_dir.parent]
        needed = {"qidi-temps", "qidiwebcamdrestart", "VoronTemps"}

        for base in candidates:
            if all((base / name).exists() for name in needed):
                return base

        # Fallback: at least return the EXE directory so paths are
        # predictable even if the folder layout changes.
        return exe_dir

    # Normal "run from source" mode during development: BASE_DIR is the
    # repository root containing this file.
    return Path(__file__).resolve().parent


# Base directory of the 3Dprinterlauncher project
BASE_DIR = _compute_base_dir()


@dataclass(frozen=True)
class AppSpec:
    name: str
    project_dir: Path
    script: str
    # Optional behavioural hint used by the UI/runner; for example
    # "oneshot" hides the Stop button and uses a different label.
    kind: str = "normal"
    # Optional per-tool Moonraker settings for Klipper dashboards.
    # When provided, the launcher will inject MOONRAKER_API_URL into the
    # child process environment and pass "--port" on the command line.
    moonraker_url: str | None = None
    moonraker_port: int | None = None

    @property
    def venv_python(self) -> Path:
        """Single shared virtualenv in the project root.

        This project launches the bundled tools (Flask dashboards, helpers)
        using a Python interpreter from a *shared* venv at `<repo>/venv`.

        Platform paths:
        - Windows: `<repo>/venv/Scripts/python.exe`
        - Linux/macOS: `<repo>/venv/bin/python` (or `python3`)

        We probe common locations and return the first one that exists so the
        launcher works across OSes and with different venv layouts.
        """

        candidates: list[Path] = [
            # POSIX venv layout
            BASE_DIR / "venv" / "bin" / "python3",
            BASE_DIR / "venv" / "bin" / "python",
            # Windows venv layout
            BASE_DIR / "venv" / "Scripts" / "python.exe",
        ]

        for p in candidates:
            if p.exists():
                return p

        # Return the most likely path for the current platform to produce a
        # helpful error message when validation fails.
        if sys.platform.startswith("win"):
            return BASE_DIR / "venv" / "Scripts" / "python.exe"
        return BASE_DIR / "venv" / "bin" / "python"

    @property
    def script_path(self) -> Path:
        return self.project_dir / self.script

    @property
    def log_path(self) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.name.lower())
        return self.project_dir / f"launcher_{safe}.log"
