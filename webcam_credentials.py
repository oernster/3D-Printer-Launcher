"""Reading and writing the Qidi webcam helper's SSH password.

The password lives in ``qidiwebcamdrestart/credentials.json``, which is
deliberately untracked. This module is the one place that knows the file's
name and shape, so the helper script and the Manage dialog cannot drift.

It is standard library only, so both the launcher and the helper can use it.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Lets a packaged build supply the password without writing it to disk. This
# is the variable's name, not a password.
PASSWORD_ENV_VAR = "QIDI_WEBCAMD_PASSWORD"  # noqa: S105

# Directory of the bundled helper, relative to the application root.
WEBCAM_TOOL_DIR = "qidiwebcamdrestart"

WEBCAM_TOOL_SCRIPT = "webcamdrestart.py"

CREDENTIALS_FILENAME = "credentials.json"

# The JSON key the password is stored under, not a password.
PASSWORD_KEY = "password"  # noqa: S105


def credentials_path(base_dir: Path) -> Path:
    """Path of the untracked credentials file for the webcam helper."""

    return base_dir / WEBCAM_TOOL_DIR / CREDENTIALS_FILENAME


def is_webcam_tool(project_dir: str, script: str) -> bool:
    """Whether a tool entry is the bundled Qidi webcam restart helper."""

    return project_dir == WEBCAM_TOOL_DIR and script == WEBCAM_TOOL_SCRIPT


def load_password(path: Path) -> str:
    """Return the stored password or an empty string if there is none.

    A missing or unreadable file is not an error: it simply means no password
    has been saved yet and the caller shows an empty field.
    """

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""
    except (OSError, ValueError):
        # Falls back to an empty field so the user can retype the password
        # rather than being shown a traceback over a corrupt local file.
        logger.warning("Could not read %s", path, exc_info=True)
        return ""

    if not isinstance(data, dict):
        return ""

    password = data.get(PASSWORD_KEY)
    return password if isinstance(password, str) else ""


def resolve_password(path: Path) -> str:
    """Return the password to use, preferring the environment variable.

    The variable exists so a packaged build can run without a credentials
    file on disk; the file is the normal case.
    """

    from_env = os.environ.get(PASSWORD_ENV_VAR)
    if from_env and from_env.strip():
        return from_env.strip()

    return load_password(path)


def save_password(path: Path, password: str) -> None:
    """Write the password or remove the file when the password is blank.

    Removing it rather than storing an empty string means the helper fails
    with its own clear "missing credentials" message instead of attempting an
    SSH connection with no password.
    """

    if not password.strip():
        path.unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({PASSWORD_KEY: password}, indent=2), encoding="utf-8")
