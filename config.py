from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json

from app_spec import BASE_DIR


CONFIG_FILENAME = "tools_config.json"


@dataclass
class ToolEntry:
    """Persistent configuration for one launcher tool/printer.

    This is intentionally a superset of what AppSpec needs so that the
    launcher can drive special UI behaviour (e.g. one-shot tools) without
    hard-coding names.
    """

    id: str
    label: str
    project_dir: str
    script: str
    # Behaviour hint for the UI/runner; e.g. "normal" vs "oneshot".
    kind: str = "normal"
    enabled: bool = True
    # Optional Moonraker API URL for Klipper-based tools. When set, the
    # launcher will expose it to the child process via MOONRAKER_API_URL so
    # that a single script can target different printers.
    moonraker_url: str | None = None
    # Optional Moonraker API TCP port (default 7125). This is stored
    # separately so the UI can show a simple "IP/host + port" model.
    moonraker_api_port: int | None = None
    # Optional local dashboard port for Flask-based tools such as the
    # Voron/Klipper dashboard. When provided, the launcher will add a
    # "--port" argument so multiple dashboards can be run concurrently.
    moonraker_port: int | None = None


def config_path() -> Path:
    return BASE_DIR / CONFIG_FILENAME


def _default_tools() -> list[ToolEntry]:
    """Built-in defaults matching the previous hard-coded tools.

    Users can later modify these via the Manage Tools UI.
    """

    return [
        ToolEntry(
            id="qidi-temps",
            label="Qidi Temps",
            project_dir="qidi-temps",
            script="app.py",
            kind="normal",
            enabled=True,
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
        ),
    ]


def load_tools_config() -> list[ToolEntry]:
    """Load tool configuration from JSON, falling back to defaults.

    Any invalid entries are skipped. Unknown keys are ignored.
    """

    path = config_path()
    if not path.exists():
        return _default_tools()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Corrupt or unreadable file – treat as if missing, but *do not*
        # overwrite the broken file automatically.
        return _default_tools()

    items = raw.get("tools") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return _default_tools()

    tools: list[ToolEntry] = []
    for obj in items:
        if not isinstance(obj, dict):
            continue
        try:
            tid = str(obj.get("id") or "").strip()
            label = str(obj.get("label") or "").strip()
            project_dir = str(obj.get("project_dir") or "").strip()
            script = str(obj.get("script") or "").strip()
            kind = str(obj.get("kind") or "normal").strip() or "normal"
            enabled = bool(obj.get("enabled", True))

            moonraker_url_val = obj.get("moonraker_url")
            if isinstance(moonraker_url_val, str):
                moonraker_url = moonraker_url_val.strip() or None
            else:
                moonraker_url = None

            api_port_raw = obj.get("moonraker_api_port")
            moonraker_api_port: int | None
            if isinstance(api_port_raw, int):
                moonraker_api_port = api_port_raw
            elif isinstance(api_port_raw, str) and api_port_raw.strip().isdigit():
                moonraker_api_port = int(api_port_raw.strip())
            else:
                moonraker_api_port = None

            port_raw = obj.get("moonraker_port")
            moonraker_port: int | None
            if isinstance(port_raw, int):
                moonraker_port = port_raw
            elif isinstance(port_raw, str) and port_raw.strip().isdigit():
                moonraker_port = int(port_raw.strip())
            else:
                moonraker_port = None

            if not tid or not label or not project_dir or not script:
                continue

            tools.append(
                ToolEntry(
                    id=tid,
                    label=label,
                    project_dir=project_dir,
                    script=script,
                    kind=kind,
                    enabled=enabled,
                    moonraker_api_port=moonraker_api_port,
                    moonraker_url=moonraker_url,
                    moonraker_port=moonraker_port,
                )
            )
        except Exception:
            # Skip any entry that cannot be parsed cleanly
            continue

    return tools or _default_tools()


def save_tools_config(tools: list[ToolEntry]) -> None:
    """Persist the given tools list to JSON on disk."""

    path = config_path()
    payload = {
        "tools": [asdict(t) for t in tools],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def ensure_config_exists() -> None:
    """Create a default config file if none exists yet."""

    path = config_path()
    if path.exists():
        return
    save_tools_config(_default_tools())

