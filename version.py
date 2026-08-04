"""Single source of truth for the application version.

The version lives in the ``VERSION`` file at the repository root so the
build scripts and the running application cannot drift apart. When that
file is missing (for example in a packaged build that did not ship it),
:data:`FALLBACK_VERSION` is used instead.
"""

from __future__ import annotations

from pathlib import Path

APP_NAME = "3D Printer Launcher"

VERSION_FILENAME = "VERSION"

FALLBACK_VERSION = "0.0.0-dev"


def _candidate_paths() -> list[Path]:
    """Places the VERSION file may live, most specific first."""

    here = Path(__file__).resolve().parent

    # Imported lazily so a packaged build that cannot resolve its own root
    # still falls back cleanly rather than failing at import time.
    from app_spec import BASE_DIR

    candidates = [here / VERSION_FILENAME, BASE_DIR / VERSION_FILENAME]

    seen: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.append(path)
    return seen


def read_version() -> str:
    """Return the version string or FALLBACK_VERSION if none is readable."""

    for path in _candidate_paths():
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return FALLBACK_VERSION


__version__ = read_version()
