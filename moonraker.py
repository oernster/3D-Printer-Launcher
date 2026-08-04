"""Shared Moonraker helpers used by the launcher and the bundled tools.

This module is deliberately dependency-free at import time (standard library
only) so the bundled dashboards can import it without pulling in PySide6 and
so the launcher does not pull in aiohttp. The async client that actually talks
to Moonraker lives in :mod:`moonraker_client`.

The bundled tools live in subdirectories and are launched as separate
processes, so their ``sys.path[0]`` is their own directory. Each one puts the
launcher root on ``sys.path`` before importing this module.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Moonraker's default HTTP API port, as shipped by Klipper installations.
DEFAULT_API_PORT = 7125

# The single Moonraker endpoint every tool in this project queries.
QUERY_PATH = "/printer/objects/query"

# Moonraker is served over plain HTTP unless a reverse proxy is in front of
# it. The launcher only ever builds http:// URLs; a user who needs https can
# still store one by hand and the client below honours it.
DEFAULT_SCHEME = "http"

# The launcher passes the resolved URL to each tool through this variable.
URL_ENV_VAR = "MOONRAKER_API_URL"

# Optional per-tool override file, read from the tool's own directory.
LOCAL_CONFIG_FILENAME = "config.json"

# Keys accepted in that file, in order of preference.
LOCAL_CONFIG_KEYS = ("moonraker_url", "url")


def build_query_url(
    host: str,
    api_port: int = DEFAULT_API_PORT,
    scheme: str = DEFAULT_SCHEME,
) -> str:
    """Build the full Moonraker query URL from a host and port.

    The host may be a bare hostname or IP address. Anything the user typed
    that already looks like a URL is reduced to its host and port first, so
    pasting a full URL into the host field still does the right thing.
    """

    parsed_host, parsed_port = split_query_url(host)
    if parsed_host:
        host = parsed_host
        if parsed_port is not None:
            api_port = parsed_port

    return f"{scheme}://{host}:{api_port}{QUERY_PATH}"


def split_query_url(url: str | None) -> tuple[str | None, int | None]:
    """Split a stored Moonraker URL back into its host and port.

    Returns ``(None, None)`` for anything that cannot be understood. A bare
    host with no scheme is returned as the host with no port.
    """

    if not url or not url.strip():
        return None, None

    text = url.strip()
    if "//" not in text:
        # A bare "host" or "host:port"; urlparse needs a scheme to find them.
        text = f"{DEFAULT_SCHEME}://{text}"

    try:
        parsed = urlparse(text)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None, None

    if not host:
        return None, None
    return host, port


def display_host(url: str | None) -> str:
    """Return a short "host" or "host:port" label for a Moonraker URL."""

    host, port = split_query_url(url)
    if host is None:
        return url or "unknown"
    if port is None:
        return host
    return f"{host}:{port}"


def swap_scheme(url: str | None) -> str | None:
    """Return the same URL with http and https exchanged, else ``None``.

    Moonraker is usually plain HTTP, so a user who typed https:// gets one
    silent retry rather than a dashboard that never shows a reading.
    """

    if not url:
        return None

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    if parsed.scheme == "https":
        return parsed._replace(scheme=DEFAULT_SCHEME).geturl()
    if parsed.scheme == DEFAULT_SCHEME:
        return parsed._replace(scheme="https").geturl()
    return None


def read_local_config_url(tool_dir: Path) -> str | None:
    """Read a Moonraker URL from a tool's own ``config.json``, if present."""

    path = tool_dir / LOCAL_CONFIG_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        # Falls back to the next source in resolve_query_url. A broken local
        # override must not stop the dashboard starting.
        logger.warning("Could not read %s", path, exc_info=True)
        return None

    if not isinstance(data, dict):
        return None

    for key in LOCAL_CONFIG_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_query_url(cli_arg: str | None, tool_dir: Path) -> str | None:
    """Decide which Moonraker URL a bundled tool should use.

    First non-empty wins: the ``--moonraker-url`` argument, then the
    environment variable the launcher sets, then the tool's own
    ``config.json``. There is deliberately no built-in address: a tool with
    nothing configured says so rather than querying a stranger's device.
    """

    if cli_arg and cli_arg.strip():
        return cli_arg.strip()

    env_value = os.environ.get(URL_ENV_VAR)
    if env_value and env_value.strip():
        return env_value.strip()

    return read_local_config_url(tool_dir)
