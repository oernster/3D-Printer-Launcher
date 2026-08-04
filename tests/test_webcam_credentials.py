"""Tests for the webcam helper's credentials file handling."""

from __future__ import annotations

import json

from webcam_credentials import (
    CREDENTIALS_FILENAME,
    PASSWORD_ENV_VAR,
    PASSWORD_KEY,
    credentials_path,
    is_webcam_tool,
    load_password,
    resolve_password,
    save_password,
)


class TestIsWebcamTool:
    def test_recognises_the_bundled_helper(self):
        assert is_webcam_tool("qidiwebcamdrestart", "webcamdrestart.py")

    def test_rejects_a_dashboard(self):
        assert not is_webcam_tool("VoronTemps", "app.py")

    def test_both_parts_must_match(self):
        assert not is_webcam_tool("qidiwebcamdrestart", "app.py")


class TestCredentialsPath:
    def test_sits_under_the_helper_directory(self, tmp_path):
        path = credentials_path(tmp_path)
        assert path.parent.name == "qidiwebcamdrestart"
        assert path.name == CREDENTIALS_FILENAME


class TestLoadPassword:
    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert load_password(tmp_path / CREDENTIALS_FILENAME) == ""

    def test_reads_a_stored_password(self, tmp_path):
        path = tmp_path / CREDENTIALS_FILENAME
        path.write_text(json.dumps({PASSWORD_KEY: "hunter2"}), encoding="utf-8")
        assert load_password(path) == "hunter2"

    def test_a_corrupt_file_yields_nothing(self, tmp_path):
        path = tmp_path / CREDENTIALS_FILENAME
        path.write_text("{ not json", encoding="utf-8")
        assert load_password(path) == ""

    def test_a_non_mapping_yields_nothing(self, tmp_path):
        path = tmp_path / CREDENTIALS_FILENAME
        path.write_text("[]", encoding="utf-8")
        assert load_password(path) == ""

    def test_a_non_string_password_yields_nothing(self, tmp_path):
        path = tmp_path / CREDENTIALS_FILENAME
        path.write_text(json.dumps({PASSWORD_KEY: 1234}), encoding="utf-8")
        assert load_password(path) == ""


class TestSavePassword:
    def test_a_saved_password_round_trips(self, tmp_path):
        path = tmp_path / "nested" / CREDENTIALS_FILENAME
        save_password(path, "hunter2")
        assert load_password(path) == "hunter2"

    def test_saving_creates_the_directory(self, tmp_path):
        path = tmp_path / "nested" / CREDENTIALS_FILENAME
        save_password(path, "hunter2")
        assert path.exists()

    def test_a_blank_password_removes_the_file(self, tmp_path):
        path = tmp_path / CREDENTIALS_FILENAME
        save_password(path, "hunter2")
        save_password(path, "   ")
        assert not path.exists()

    def test_clearing_an_absent_file_is_harmless(self, tmp_path):
        save_password(tmp_path / CREDENTIALS_FILENAME, "")


class TestResolvePassword:
    def test_the_environment_wins(self, tmp_path, monkeypatch):
        path = tmp_path / CREDENTIALS_FILENAME
        save_password(path, "from-file")
        monkeypatch.setenv(PASSWORD_ENV_VAR, "from-env")
        assert resolve_password(path) == "from-env"

    def test_the_file_is_used_when_the_variable_is_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
        path = tmp_path / CREDENTIALS_FILENAME
        save_password(path, "from-file")
        assert resolve_password(path) == "from-file"

    def test_nothing_anywhere_yields_nothing(self, tmp_path, monkeypatch):
        monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
        assert resolve_password(tmp_path / CREDENTIALS_FILENAME) == ""
