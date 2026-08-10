"""Tests for the update check's Qt-free half."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

from update_check import (
    ACCEPT_HEADER,
    PLATFORM_KEY_LINUX,
    PLATFORM_KEY_MACOS,
    PLATFORM_KEY_WINDOWS,
    RELEASES_LATEST_URL,
    REQUEST_TIMEOUT_SECONDS,
    SETTINGS_FILENAME,
    GitHubReleaseSource,
    ReleaseAsset,
    ReleaseInfo,
    UpdateService,
    is_newer,
    load_skipped_version,
    platform_key_for,
    save_skipped_version,
    select_asset_url,
)

CURRENT = "2.1.0"


class FakeReleaseSource:
    def __init__(self, release: ReleaseInfo | None) -> None:
        self._release = release

    def latest_release(self) -> ReleaseInfo | None:
        return self._release


def release(
    version: str = "9.9.9", assets: tuple[ReleaseAsset, ...] | None = None
) -> ReleaseInfo:
    if assets is None:
        assets = (ReleaseAsset("3D-Printer-Launcher.exe", "https://example.test/win"),)
    return ReleaseInfo(
        version=version, page_url="https://example.test/rel", assets=assets
    )


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeOpener:
    def __init__(self, body: bytes | None = None, error: Exception | None = None):
        self._body = body
        self._error = error
        self.request: urllib.request.Request | None = None
        self.timeout: float | None = None

    def __call__(self, request: urllib.request.Request, timeout: float) -> Any:
        self.request = request
        self.timeout = timeout
        if self._error is not None:
            raise self._error
        return FakeResponse(self._body or b"")


def payload(**overrides: Any) -> bytes:
    data: dict[str, Any] = {
        "tag_name": "v2.2.0",
        "html_url": "https://example.test/rel",
        "assets": [
            {
                "name": "3D-Printer-Launcher.exe",
                "browser_download_url": "https://example.test/win",
            }
        ],
    }
    data.update(overrides)
    return json.dumps(data).encode("utf-8")


def test_is_newer_ordering_and_tolerance() -> None:
    assert is_newer("2.2.0", CURRENT) is True
    assert is_newer(CURRENT, CURRENT) is False
    assert is_newer("2.0.9", CURRENT) is False
    assert is_newer("v2.2.0", CURRENT) is True
    assert is_newer("V2.2.0", CURRENT) is True
    assert is_newer("  2.2.0  ", CURRENT) is True
    assert is_newer("2.1.0.1", CURRENT) is True
    assert is_newer("2.2", CURRENT) is True


def test_is_newer_malformed_and_prerelease_never_prompt() -> None:
    assert is_newer("not-a-version", CURRENT) is False
    assert is_newer("2.2.0", "garbage") is False
    assert is_newer("", CURRENT) is False
    assert is_newer("2.2.0-rc1", CURRENT) is False


@pytest.mark.parametrize(
    ("sys_platform", "expected"),
    [
        ("win32", PLATFORM_KEY_WINDOWS),
        ("darwin", PLATFORM_KEY_MACOS),
        ("linux", PLATFORM_KEY_LINUX),
        ("freebsd14", PLATFORM_KEY_LINUX),
    ],
)
def test_platform_key_mapping(sys_platform: str, expected: str) -> None:
    assert platform_key_for(sys_platform) == expected


def test_select_asset_url_by_suffix() -> None:
    assets = (
        ReleaseAsset("Setup.EXE", "https://example.test/w"),
        ReleaseAsset("app.dmg", "https://example.test/m"),
    )
    assert select_asset_url(assets, PLATFORM_KEY_WINDOWS) == "https://example.test/w"
    assert select_asset_url(assets, PLATFORM_KEY_MACOS) == "https://example.test/m"
    assert select_asset_url(assets, PLATFORM_KEY_LINUX) is None
    assert select_asset_url((), PLATFORM_KEY_WINDOWS) is None
    assert select_asset_url(assets, "beos") is None


def test_service_unreachable_source_returns_none() -> None:
    service = UpdateService(FakeReleaseSource(None), CURRENT, PLATFORM_KEY_WINDOWS)
    assert service.check() is None


def test_service_reports_newer_release() -> None:
    service = UpdateService(FakeReleaseSource(release()), CURRENT, PLATFORM_KEY_WINDOWS)
    status = service.check()
    assert status is not None
    assert status.update_available is True
    assert status.latest == "9.9.9"
    assert status.current == CURRENT
    assert status.download_url == "https://example.test/win"
    assert status.page_url == "https://example.test/rel"


def test_service_same_version_not_available() -> None:
    service = UpdateService(
        FakeReleaseSource(release(CURRENT)), CURRENT, PLATFORM_KEY_WINDOWS
    )
    status = service.check()
    assert status is not None
    assert status.update_available is False


def test_service_skip_rules() -> None:
    service = UpdateService(FakeReleaseSource(release()), CURRENT, PLATFORM_KEY_WINDOWS)
    skipped = service.check(skipped_version="9.9.9")
    assert skipped is not None
    assert skipped.update_available is False
    different = service.check(skipped_version="2.2.0")
    assert different is not None
    assert different.update_available is True


def test_service_empty_assets_offer_no_download_url() -> None:
    service = UpdateService(
        FakeReleaseSource(release(assets=())), CURRENT, PLATFORM_KEY_WINDOWS
    )
    status = service.check()
    assert status is not None
    assert status.download_url is None
    assert status.page_url == "https://example.test/rel"


def test_adapter_happy_path_strips_v_and_targets_endpoint() -> None:
    opener = FakeOpener(payload())
    result = GitHubReleaseSource(opener=opener).latest_release()
    assert result is not None
    assert result.version == "2.2.0"
    assert result.page_url == "https://example.test/rel"
    assert result.assets[0].name == "3D-Printer-Launcher.exe"
    assert opener.request is not None
    assert opener.request.full_url == RELEASES_LATEST_URL
    assert opener.request.get_header("Accept") == ACCEPT_HEADER
    assert opener.timeout == REQUEST_TIMEOUT_SECONDS


def test_adapter_failures_read_as_no_release() -> None:
    assert GitHubReleaseSource(FakeOpener(error=OSError())).latest_release() is None
    assert GitHubReleaseSource(FakeOpener(b"not json")).latest_release() is None
    assert GitHubReleaseSource(FakeOpener(b"[1]")).latest_release() is None
    for override in (
        {"tag_name": None},
        {"tag_name": ""},
        {"tag_name": 7},
        {"html_url": None},
        {"html_url": ""},
        {"html_url": 7},
    ):
        source = GitHubReleaseSource(FakeOpener(payload(**override)))
        assert source.latest_release() is None, override


def test_adapter_filters_malformed_assets() -> None:
    body = payload(
        assets=[
            "not a dict",
            {"name": "", "browser_download_url": "https://example.test/x"},
            {"name": "no-url.exe"},
            {"name": "good.exe", "browser_download_url": "https://example.test/g"},
        ]
    )
    result = GitHubReleaseSource(FakeOpener(body)).latest_release()
    assert result is not None
    assert [asset.name for asset in result.assets] == ["good.exe"]
    for override in ({"assets": None}, {"assets": "nope"}):
        result = GitHubReleaseSource(FakeOpener(payload(**override))).latest_release()
        assert result is not None
        assert result.assets == ()


def test_skip_persistence_roundtrip(tmp_path) -> None:
    assert load_skipped_version(tmp_path) is None
    save_skipped_version("2.2.0", tmp_path)
    assert load_skipped_version(tmp_path) == "2.2.0"
    written = json.loads((tmp_path / SETTINGS_FILENAME).read_text(encoding="utf-8"))
    assert written == {"skipped_update_version": "2.2.0"}


def test_skip_persistence_preserves_other_keys(tmp_path) -> None:
    path = tmp_path / SETTINGS_FILENAME
    path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    save_skipped_version("2.2.0", tmp_path)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written == {"skipped_update_version": "2.2.0", "theme": "dark"}


def test_skip_persistence_tolerates_damage(tmp_path) -> None:
    path = tmp_path / SETTINGS_FILENAME
    path.write_text("{ not json", encoding="utf-8")
    assert load_skipped_version(tmp_path) is None
    save_skipped_version("2.2.0", tmp_path)
    assert load_skipped_version(tmp_path) == "2.2.0"
    path.write_text(json.dumps({"skipped_update_version": 7}), encoding="utf-8")
    assert load_skipped_version(tmp_path) is None
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert load_skipped_version(tmp_path) is None
