"""The update check's Qt-free half: version logic, GitHub adapter and skip.

Queries the ``releases/latest`` endpoint, which by contract returns only a
published, non-draft, non-prerelease release, so a tag pushed
mid-development can never prompt. The request is anonymous, times out
after five seconds and any failure reads as "no release visible".

The skipped-version choice persists in ``launcher_settings.json`` beside
the tools configuration, so the per-user configuration folder stays the
one place launcher state lives.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import user_config_dir

RELEASES_LATEST_URL = (
    "https://api.github.com/repos/oernster/3D-Printer-Launcher/releases/latest"
)
ACCEPT_HEADER = "application/vnd.github+json"
REQUEST_TIMEOUT_SECONDS = 5.0

SETTINGS_FILENAME = "launcher_settings.json"
SKIPPED_KEY = "skipped_update_version"

PLATFORM_KEY_WINDOWS = "windows"
PLATFORM_KEY_MACOS = "macos"
PLATFORM_KEY_LINUX = "linux"

_SYS_PLATFORM_KEYS = {
    "win32": PLATFORM_KEY_WINDOWS,
    "darwin": PLATFORM_KEY_MACOS,
}

_ASSET_SUFFIXES = {
    PLATFORM_KEY_WINDOWS: ".exe",
    PLATFORM_KEY_MACOS: ".dmg",
    PLATFORM_KEY_LINUX: ".flatpak",
}


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """One downloadable file attached to a published release."""

    name: str
    download_url: str


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """A published release as the update check needs to see it."""

    version: str
    page_url: str
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    """What one check concluded, ready for the UI to present."""

    current: str
    latest: str | None
    update_available: bool
    download_url: str | None
    page_url: str | None


def _version_tuple(text: str) -> tuple[int, ...] | None:
    """Parse ``text`` as a dotted integer tuple, else ``None``."""
    cleaned = text.strip()
    if cleaned[:1] in ("v", "V"):
        cleaned = cleaned[1:]
    try:
        return tuple(int(part) for part in cleaned.split("."))
    except ValueError:
        return None


def is_newer(candidate: str, current: str) -> bool:
    """Return whether ``candidate`` names a strictly newer version.

    Anything unparseable compares as not newer, so a malformed tag can
    never raise a spurious prompt.
    """
    candidate_tuple = _version_tuple(candidate)
    current_tuple = _version_tuple(current)
    if candidate_tuple is None or current_tuple is None:
        return False
    return candidate_tuple > current_tuple


def platform_key_for(sys_platform: str) -> str:
    """Map a ``sys.platform`` value onto an asset platform key."""
    return _SYS_PLATFORM_KEYS.get(sys_platform, PLATFORM_KEY_LINUX)


def select_asset_url(assets: tuple[ReleaseAsset, ...], platform_key: str) -> str | None:
    """Return the download URL of the asset matching ``platform_key``."""
    suffix = _ASSET_SUFFIXES.get(platform_key)
    if suffix is None:
        return None
    for asset in assets:
        if asset.name.lower().endswith(suffix):
            return asset.download_url
    return None


def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
    # The URL is a module constant naming the https endpoint, not user input.
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


def _parse_assets(raw: Any) -> tuple[ReleaseAsset, ...]:
    """Return the well-formed assets, silently dropping malformed entries."""
    if not isinstance(raw, list):
        return ()
    assets = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        url = entry.get("browser_download_url")
        if isinstance(name, str) and name and isinstance(url, str) and url:
            assets.append(ReleaseAsset(name=name, download_url=url))
    return tuple(assets)


class GitHubReleaseSource:
    """Fetches the newest published release over stdlib urllib.

    The opener is injected so tests never touch the network.
    """

    def __init__(
        self,
        opener: Callable[[urllib.request.Request, float], Any] = _default_opener,
    ) -> None:
        self._opener = opener

    def latest_release(self) -> ReleaseInfo | None:
        """Return the latest published release, else ``None`` on any failure."""
        request = urllib.request.Request(
            RELEASES_LATEST_URL, headers={"Accept": ACCEPT_HEADER}
        )
        try:
            with self._opener(request, REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError):
            # Offline, refused, rate-limited or unparseable: every one of
            # these means the same thing to the caller, no release visible.
            return None
        if not isinstance(payload, dict):
            return None
        tag = payload.get("tag_name")
        page_url = payload.get("html_url")
        if not isinstance(tag, str) or not tag:
            return None
        if not isinstance(page_url, str) or not page_url:
            return None
        version = tag[1:] if tag[:1] in ("v", "V") else tag
        return ReleaseInfo(
            version=version,
            page_url=page_url,
            assets=_parse_assets(payload.get("assets")),
        )


class UpdateService:
    """Asks the release source whether a newer version is published."""

    def __init__(
        self, source: GitHubReleaseSource, current_version: str, platform_key: str
    ) -> None:
        self._source = source
        self._current = current_version
        self._platform_key = platform_key

    def check(self, skipped_version: str | None = None) -> UpdateStatus | None:
        """Return the check's conclusion, or ``None`` when unreachable.

        A release equal to ``skipped_version`` is reported as seen but not
        available, which is what keeps a skipped version from prompting
        again on the automatic paths.
        """
        release = self._source.latest_release()
        if release is None:
            return None
        newer = is_newer(release.version, self._current)
        skipped = skipped_version is not None and release.version == skipped_version
        return UpdateStatus(
            current=self._current,
            latest=release.version,
            update_available=newer and not skipped,
            download_url=select_asset_url(release.assets, self._platform_key),
            page_url=release.page_url,
        )


def _settings_path(config_dir: Path | None = None) -> Path:
    base = config_dir if config_dir is not None else user_config_dir()
    return base / SETTINGS_FILENAME


def load_skipped_version(config_dir: Path | None = None) -> str | None:
    """Return the release version the user chose to skip, or ``None``."""
    path = _settings_path(config_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get(SKIPPED_KEY)
    return value if isinstance(value, str) and value else None


def save_skipped_version(version: str, config_dir: Path | None = None) -> None:
    """Persist the skipped version, preserving unrelated settings keys.

    Best effort: a settings file that cannot be written must never stop
    the launcher, so failures are swallowed and the skip simply does not
    stick past this session.
    """
    path = _settings_path(config_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        data = {}
    data[SKIPPED_KEY] = version
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
