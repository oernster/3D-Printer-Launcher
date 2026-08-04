"""Tests for the shared Moonraker URL helpers."""

from __future__ import annotations

import json

import pytest

from moonraker import (
    DEFAULT_API_PORT,
    QUERY_PATH,
    URL_ENV_VAR,
    build_query_url,
    display_host,
    read_local_config_url,
    resolve_query_url,
    split_query_url,
    swap_scheme,
)


class TestBuildQueryUrl:
    def test_builds_from_bare_host(self):
        url = build_query_url("printer.local")
        assert url == f"http://printer.local:{DEFAULT_API_PORT}{QUERY_PATH}"

    def test_honours_an_explicit_api_port(self):
        assert build_query_url("printer.local", 7130).startswith(
            "http://printer.local:7130"
        )

    def test_a_pasted_full_url_is_reduced_to_host_and_port(self):
        url = build_query_url("http://10.0.0.5:7130/printer/objects/query")
        assert url == f"http://10.0.0.5:7130{QUERY_PATH}"

    def test_a_pasted_host_and_port_wins_over_the_argument(self):
        expected = f"http://10.0.0.5:7130{QUERY_PATH}"
        assert build_query_url("10.0.0.5:7130", 7125) == expected


class TestSplitQueryUrl:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_empty_input_yields_nothing(self, value):
        assert split_query_url(value) == (None, None)

    def test_full_url(self):
        assert split_query_url(f"http://1.2.3.4:7125{QUERY_PATH}") == ("1.2.3.4", 7125)

    def test_bare_host_has_no_port(self):
        assert split_query_url("printer.local") == ("printer.local", None)

    def test_host_and_port_without_a_scheme(self):
        assert split_query_url("printer.local:7130") == ("printer.local", 7130)

    def test_unparseable_input_yields_nothing(self):
        assert split_query_url("http://[oops") == (None, None)


class TestDisplayHost:
    def test_includes_the_port_when_there_is_one(self):
        assert display_host(f"http://1.2.3.4:7125{QUERY_PATH}") == "1.2.3.4:7125"

    def test_omits_a_missing_port(self):
        assert display_host("printer.local") == "printer.local"

    def test_unrecognised_input_is_returned_as_given(self):
        assert display_host("http://[oops") == "http://[oops"

    def test_nothing_reads_as_unknown(self):
        assert display_host(None) == "unknown"


class TestSwapScheme:
    def test_https_becomes_http(self):
        assert swap_scheme("https://p:7125/x") == "http://p:7125/x"

    def test_http_becomes_https(self):
        assert swap_scheme("http://p:7125/x") == "https://p:7125/x"

    @pytest.mark.parametrize("value", [None, "", "ftp://p/x"])
    def test_anything_else_has_no_alternative(self, value):
        assert swap_scheme(value) is None


class TestReadLocalConfigUrl:
    def test_missing_file_is_not_an_error(self, tmp_path):
        assert read_local_config_url(tmp_path) is None

    def test_reads_the_moonraker_url_key(self, tmp_path):
        (tmp_path / "config.json").write_text(
            json.dumps({"moonraker_url": "http://p:7125/q"}), encoding="utf-8"
        )
        assert read_local_config_url(tmp_path) == "http://p:7125/q"

    def test_falls_back_to_the_url_key(self, tmp_path):
        (tmp_path / "config.json").write_text(
            json.dumps({"url": "http://p:7125/q"}), encoding="utf-8"
        )
        assert read_local_config_url(tmp_path) == "http://p:7125/q"

    def test_corrupt_file_yields_nothing_rather_than_raising(self, tmp_path):
        (tmp_path / "config.json").write_text("{not json", encoding="utf-8")
        assert read_local_config_url(tmp_path) is None

    def test_a_json_list_is_not_a_config(self, tmp_path):
        (tmp_path / "config.json").write_text("[]", encoding="utf-8")
        assert read_local_config_url(tmp_path) is None

    def test_a_blank_value_is_ignored(self, tmp_path):
        (tmp_path / "config.json").write_text(
            json.dumps({"moonraker_url": "  "}), encoding="utf-8"
        )
        assert read_local_config_url(tmp_path) is None


class TestResolveQueryUrl:
    def test_the_argument_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv(URL_ENV_VAR, "http://from-env/q")
        assert resolve_query_url("http://from-arg/q", tmp_path) == "http://from-arg/q"

    def test_the_environment_comes_next(self, tmp_path, monkeypatch):
        monkeypatch.setenv(URL_ENV_VAR, "http://from-env/q")
        assert resolve_query_url(None, tmp_path) == "http://from-env/q"

    def test_then_the_local_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv(URL_ENV_VAR, raising=False)
        (tmp_path / "config.json").write_text(
            json.dumps({"moonraker_url": "http://from-file/q"}), encoding="utf-8"
        )
        assert resolve_query_url(None, tmp_path) == "http://from-file/q"

    def test_nothing_configured_yields_nothing(self, tmp_path, monkeypatch):
        """There must be no built-in address pointing at somebody's printer."""

        monkeypatch.delenv(URL_ENV_VAR, raising=False)
        assert resolve_query_url(None, tmp_path) is None

    def test_a_blank_argument_does_not_count(self, tmp_path, monkeypatch):
        monkeypatch.setenv(URL_ENV_VAR, "http://from-env/q")
        assert resolve_query_url("   ", tmp_path) == "http://from-env/q"
