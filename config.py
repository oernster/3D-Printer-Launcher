from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from app_spec import BASE_DIR, AppSpec
from moonraker import DEFAULT_API_PORT, build_query_url, split_query_url

logger = logging.getLogger(__name__)

# Directory name used under the per-user configuration root.
APP_DIR_NAME = "3D-Printer-Launcher"

# The live configuration, written to a per-user location.
CONFIG_FILENAME = "tools_config.json"

# The tracked template shipped with the repository. It holds placeholder
# addresses only and is never written to.
EXAMPLE_CONFIG_FILENAME = "tools_config.example.json"

# Escape hatch for tests and for anyone who wants the config beside the app.
CONFIG_DIR_ENV_VAR = "PRINTER_LAUNCHER_CONFIG_DIR"

DEFAULT_KIND = "normal"

# Dashboard ports assigned to the bundled tools on a fresh install. They only
# have to differ from each other so two dashboards can run at once.
DEFAULT_QIDI_DASHBOARD_PORT = 5000
DEFAULT_VORON_DASHBOARD_PORT = 5001


@dataclass
class ToolEntry:
    """Persistent configuration for one launcher tool/printer.

    This is intentionally a superset of what AppSpec needs so that the
    launcher can drive special UI behaviour (e.g. one-shot tools) without
    hard-coding names.

    The Moonraker address is stored once, as a host plus an API port. The
    full query URL is derived from those two fields, so there is no way for
    a stored URL and a stored port to disagree.
    """

    id: str
    label: str
    project_dir: str
    script: str
    # Behaviour hint for the UI/runner; e.g. "normal" vs "oneshot".
    kind: str = DEFAULT_KIND
    enabled: bool = True
    # Moonraker host or IP address for Klipper-based tools. When set, the
    # launcher exposes the derived URL to the child process via
    # MOONRAKER_API_URL so one script can target different printers.
    moonraker_host: str | None = None
    # TCP port Moonraker itself listens on.
    moonraker_api_port: int = DEFAULT_API_PORT
    # Local dashboard port for Flask-based tools such as the Voron/Klipper
    # dashboard. When provided, the launcher adds a "--port" argument so
    # multiple dashboards can be run concurrently.
    dashboard_port: int | None = None

    @property
    def moonraker_url(self) -> str | None:
        """The full Moonraker query URL, derived from host and API port."""

        if not self.moonraker_host:
            return None
        return build_query_url(self.moonraker_host, self.moonraker_api_port)


def user_config_dir() -> Path:
    """Return the per-user directory holding the live configuration.

    Windows uses %APPDATA%; everything else follows the XDG base directory
    specification and falls back to ~/.config.
    """

    override = os.environ.get(CONFIG_DIR_ENV_VAR)
    if override and override.strip():
        return Path(override.strip())

    if sys.platform.startswith("win"):
        roaming = os.environ.get("APPDATA")
        root = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        root = Path(xdg) if xdg else Path.home() / ".config"

    return root / APP_DIR_NAME


def config_path() -> Path:
    """Path of the live, per-user configuration file."""

    return user_config_dir() / CONFIG_FILENAME


def example_config_path() -> Path:
    """Path of the tracked template shipped alongside the application."""

    return BASE_DIR / EXAMPLE_CONFIG_FILENAME


def legacy_config_path() -> Path:
    """Path of the pre-split configuration that lived beside the app."""

    return BASE_DIR / CONFIG_FILENAME


def default_tools() -> list[ToolEntry]:
    """Built-in defaults used when no template and no config are present."""

    return [
        ToolEntry(
            id="qidi-temps",
            label="Qidi Temps",
            project_dir="qidi-temps",
            script="app.py",
            kind="normal",
            enabled=True,
            dashboard_port=DEFAULT_QIDI_DASHBOARD_PORT,
        ),
        ToolEntry(
            id="qidi-webcamd-restart",
            label="Qidi Webcamd restart",
            project_dir="qidiwebcamdrestart",
            script="webcamdrestart.py",
            kind="oneshot",
            enabled=True,
        ),
        ToolEntry(
            id="voron-temps",
            label="Voron Temps",
            project_dir="VoronTemps",
            script="app.py",
            kind="normal",
            enabled=True,
            dashboard_port=DEFAULT_VORON_DASHBOARD_PORT,
        ),
    ]


def _coerce_port(value: object) -> int | None:
    """Read a port from JSON, accepting both numbers and numeric strings."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _read_host_and_port(obj: dict) -> tuple[str | None, int]:
    """Resolve the Moonraker host and API port for one raw entry.

    ``moonraker_host`` wins when present. A configuration written before the
    host/port split only has ``moonraker_url``, so the host and port are
    recovered from it.
    """

    api_port = _coerce_port(obj.get("moonraker_api_port"))

    host_val = obj.get("moonraker_host")
    if isinstance(host_val, str) and host_val.strip():
        return host_val.strip(), api_port or DEFAULT_API_PORT

    url_val = obj.get("moonraker_url")
    if isinstance(url_val, str):
        host, port = split_query_url(url_val)
        if host:
            return host, port or api_port or DEFAULT_API_PORT

    return None, api_port or DEFAULT_API_PORT


def entry_from_mapping(obj: object) -> ToolEntry | None:
    """Build a ToolEntry from one raw JSON object or None if unusable."""

    if not isinstance(obj, dict):
        return None

    tid = str(obj.get("id") or "").strip()
    label = str(obj.get("label") or "").strip()
    project_dir = str(obj.get("project_dir") or "").strip()
    script = str(obj.get("script") or "").strip()
    if not tid or not label or not project_dir or not script:
        return None

    host, api_port = _read_host_and_port(obj)

    # "moonraker_port" is the pre-split name for the local dashboard port.
    dashboard_port = _coerce_port(obj.get("dashboard_port"))
    if dashboard_port is None:
        dashboard_port = _coerce_port(obj.get("moonraker_port"))

    return ToolEntry(
        id=tid,
        label=label,
        project_dir=project_dir,
        script=script,
        kind=str(obj.get("kind") or DEFAULT_KIND).strip() or DEFAULT_KIND,
        enabled=bool(obj.get("enabled", True)),
        moonraker_host=host,
        moonraker_api_port=api_port,
        dashboard_port=dashboard_port,
    )


def parse_tools(raw: object) -> list[ToolEntry]:
    """Turn decoded JSON into tool entries, skipping anything unusable."""

    items = raw.get("tools") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []

    tools: list[ToolEntry] = []
    for obj in items:
        entry = entry_from_mapping(obj)
        if entry is None:
            logger.warning("Skipping unusable tool entry: %r", obj)
            continue
        tools.append(entry)
    return tools


def load_tools_config() -> list[ToolEntry]:
    """Load tool configuration from JSON, falling back to defaults.

    Any invalid entries are skipped. Unknown keys are ignored. A corrupt file
    is reported and left untouched rather than overwritten.
    """

    path = config_path()
    if not path.exists():
        return default_tools()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception(
            "Could not read %s; starting from built-in defaults and leaving "
            "the file untouched.",
            path,
        )
        return default_tools()

    return parse_tools(raw) or default_tools()


def save_tools_config(tools: list[ToolEntry]) -> None:
    """Persist the given tools list to the per-user config file."""

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tools": [asdict(t) for t in tools]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def ensure_config_exists() -> Path:
    """Create the per-user config on first run and return its path.

    The order of preference is: a configuration the user already had beside
    the application (migrated once), then the tracked example template, then
    the built-in defaults.
    """

    path = config_path()
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)

    for source, reason in (
        (legacy_config_path(), "migrated from"),
        (example_config_path(), "created from"),
    ):
        if not source.exists():
            continue
        try:
            shutil.copyfile(source, path)
        except OSError:
            logger.exception("Could not copy %s to %s", source, path)
            break
        logger.info("Configuration %s %s", reason, source)
        return path

    save_tools_config(default_tools())
    logger.info("Configuration created from built-in defaults at %s", path)
    return path


def enabled_specs() -> list[AppSpec]:
    """Return an AppSpec for every enabled tool in the live configuration."""

    return [
        AppSpec(
            name=t.label,
            project_dir=BASE_DIR / t.project_dir,
            script=t.script,
            kind=t.kind,
            moonraker_url=t.moonraker_url,
            dashboard_port=t.dashboard_port,
        )
        for t in load_tools_config()
        if t.enabled
    ]
