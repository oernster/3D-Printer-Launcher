"""Tests that VERSION really is the single source of truth."""

from __future__ import annotations

import re

import version
from build_nuitka import pe_version
from version import FALLBACK_VERSION, VERSION_FILENAME, read_version

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Files that must not carry a version string of their own.
FILES_THAT_MUST_NOT_HARDCODE = (
    "pyproject.toml",
    "main.py",
    "main_window.py",
    "config.py",
    "app_spec.py",
)


class TestVersionFile:
    def test_the_version_file_exists(self, repo_root):
        assert (repo_root / VERSION_FILENAME).is_file()

    def test_it_holds_a_single_semantic_version(self, repo_root):
        raw = (repo_root / VERSION_FILENAME).read_text(encoding="utf-8")
        assert len(raw.strip().splitlines()) == 1
        assert SEMVER_RE.match(raw.strip())

    def test_the_module_reports_what_the_file_says(self, repo_root):
        raw = (repo_root / VERSION_FILENAME).read_text(encoding="utf-8").strip()
        assert version.__version__ == raw

    def test_it_is_not_the_fallback(self):
        """A real build must never ship the development sentinel."""

        assert version.__version__ != FALLBACK_VERSION


class TestFallback:
    def test_an_unreadable_file_yields_the_sentinel(self, monkeypatch, tmp_path):
        monkeypatch.setattr(version, "_candidate_paths", lambda: [tmp_path / "nope"])
        assert read_version() == FALLBACK_VERSION

    def test_an_empty_file_yields_the_sentinel(self, monkeypatch, tmp_path):
        empty = tmp_path / VERSION_FILENAME
        empty.write_text("   \n", encoding="utf-8")
        monkeypatch.setattr(version, "_candidate_paths", lambda: [empty])
        assert read_version() == FALLBACK_VERSION

    def test_the_sentinel_cannot_be_mistaken_for_a_release(self):
        """It must look like a placeholder, not an older real version."""

        assert FALLBACK_VERSION == "0.0.0-dev"


class TestNoOtherFileHardcodesAVersion:
    def test_no_module_repeats_the_version(self, repo_root):
        """Only VERSION may contain the version. Everything else derives it."""

        current = (repo_root / VERSION_FILENAME).read_text(encoding="utf-8").strip()
        for name in FILES_THAT_MUST_NOT_HARDCODE:
            text = (repo_root / name).read_text(encoding="utf-8")
            assert current not in text, f"{name} hardcodes the version {current}"

    def test_pyproject_declares_the_version_dynamically(self, repo_root):
        text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
        assert 'dynamic = ["version"]' in text
        assert 'file = "VERSION"' in text


class TestPeVersion:
    def test_a_three_part_version_is_padded_to_four(self):
        assert pe_version("2.0.3") == "2.0.3.0"

    def test_a_pre_release_suffix_is_dropped(self):
        assert pe_version("0.0.0-dev") == "0.0.0.0"

    def test_an_over_long_version_is_truncated(self):
        assert pe_version("1.2.3.4.5") == "1.2.3.4"

    def test_something_unparseable_still_yields_four_numbers(self):
        assert pe_version("not-a-version") == "0.0.0.0"
