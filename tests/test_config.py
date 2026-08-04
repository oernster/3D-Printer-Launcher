"""Tests for loading, saving and migrating the tools configuration."""

from __future__ import annotations

import json

import config
from app_spec import KIND_NORMAL, KIND_ONESHOT
from config import (
    DEFAULT_API_PORT,
    ToolEntry,
    config_path,
    default_tools,
    ensure_config_exists,
    entry_from_mapping,
    load_tools_config,
    parse_tools,
    save_tools_config,
    user_config_dir,
)


def _valid_mapping(**overrides) -> dict:
    base = {
        "id": "voron",
        "label": "Voron Trident",
        "project_dir": "VoronTemps",
        "script": "app.py",
    }
    base.update(overrides)
    return base


class TestUserConfigDir:
    def test_the_environment_override_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv(config.CONFIG_DIR_ENV_VAR, str(tmp_path))
        assert user_config_dir() == tmp_path

    def test_the_directory_is_named_after_the_application(self, monkeypatch):
        monkeypatch.delenv(config.CONFIG_DIR_ENV_VAR, raising=False)
        assert user_config_dir().name == config.APP_DIR_NAME


class TestToolEntry:
    def test_the_query_url_is_derived_from_host_and_port(self):
        entry = ToolEntry(
            id="v",
            label="V",
            project_dir="VoronTemps",
            script="app.py",
            moonraker_host="printer.local",
            moonraker_api_port=7130,
        )
        assert entry.moonraker_url == "http://printer.local:7130/printer/objects/query"

    def test_no_host_means_no_url(self):
        entry = ToolEntry(id="v", label="V", project_dir="d", script="s.py")
        assert entry.moonraker_url is None


class TestEntryFromMapping:
    def test_a_minimal_entry_takes_the_defaults(self):
        entry = entry_from_mapping(_valid_mapping())
        assert entry is not None
        assert entry.kind == KIND_NORMAL
        assert entry.enabled is True
        assert entry.moonraker_api_port == DEFAULT_API_PORT
        assert entry.dashboard_port is None

    def test_a_non_mapping_is_rejected(self):
        assert entry_from_mapping(["not", "a", "dict"]) is None

    def test_every_required_field_is_required(self):
        for missing in ("id", "label", "project_dir", "script"):
            mapping = _valid_mapping()
            mapping[missing] = ""
            assert entry_from_mapping(mapping) is None

    def test_the_host_field_is_preferred(self):
        entry = entry_from_mapping(
            _valid_mapping(
                moonraker_host="printer.local",
                moonraker_url="http://ignored:7125/printer/objects/query",
            )
        )
        assert entry.moonraker_host == "printer.local"

    def test_a_legacy_url_is_split_back_into_host_and_port(self):
        """Configurations written before the split must still load."""

        entry = entry_from_mapping(
            _valid_mapping(moonraker_url="http://10.0.0.9:7130/printer/objects/query")
        )
        assert entry.moonraker_host == "10.0.0.9"
        assert entry.moonraker_api_port == 7130

    def test_the_legacy_dashboard_port_name_is_honoured(self):
        entry = entry_from_mapping(_valid_mapping(moonraker_port=5001))
        assert entry.dashboard_port == 5001

    def test_the_current_dashboard_port_name_wins(self):
        entry = entry_from_mapping(
            _valid_mapping(dashboard_port=5005, moonraker_port=5001)
        )
        assert entry.dashboard_port == 5005

    def test_a_numeric_string_port_is_accepted(self):
        entry = entry_from_mapping(_valid_mapping(dashboard_port="5002"))
        assert entry.dashboard_port == 5002

    def test_a_boolean_is_not_a_port(self):
        entry = entry_from_mapping(_valid_mapping(dashboard_port=True))
        assert entry.dashboard_port is None

    def test_a_nonsense_port_is_dropped(self):
        entry = entry_from_mapping(_valid_mapping(dashboard_port="soon"))
        assert entry.dashboard_port is None

    def test_unknown_keys_are_ignored(self):
        assert entry_from_mapping(_valid_mapping(colour="red")) is not None


class TestParseTools:
    def test_reads_the_tools_key(self):
        assert len(parse_tools({"tools": [_valid_mapping()]})) == 1

    def test_accepts_a_bare_list(self):
        assert len(parse_tools([_valid_mapping()])) == 1

    def test_an_unusable_entry_is_skipped_not_fatal(self):
        tools = parse_tools({"tools": [_valid_mapping(), {"id": "broken"}]})
        assert len(tools) == 1

    def test_an_unexpected_shape_yields_nothing(self):
        assert parse_tools("not a config") == []


class TestLoadAndSave:
    def test_a_missing_file_gives_the_built_in_defaults(self, config_dir):
        assert load_tools_config() == default_tools()

    def test_a_saved_configuration_round_trips(self, config_dir):
        original = [
            ToolEntry(
                id="v",
                label="Voron",
                project_dir="VoronTemps",
                script="app.py",
                moonraker_host="printer.local",
                dashboard_port=5001,
            )
        ]
        save_tools_config(original)
        assert load_tools_config() == original

    def test_saving_creates_the_directory(self, config_dir):
        save_tools_config(default_tools())
        assert config_path().exists()

    def test_a_corrupt_file_falls_back_without_overwriting_it(self, config_dir):
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path().write_text("{ not json", encoding="utf-8")

        assert load_tools_config() == default_tools()
        # The user's file is left alone so it can still be recovered by hand.
        assert config_path().read_text(encoding="utf-8") == "{ not json"

    def test_a_file_with_no_usable_entries_falls_back(self, config_dir):
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path().write_text(json.dumps({"tools": []}), encoding="utf-8")
        assert load_tools_config() == default_tools()


class TestEnsureConfigExists:
    def test_an_existing_file_is_left_alone(self, config_dir):
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path().write_text(json.dumps({"tools": []}), encoding="utf-8")

        ensure_config_exists()

        assert config_path().read_text(encoding="utf-8") == json.dumps({"tools": []})

    def test_the_shipped_template_is_used_on_a_first_run(self, config_dir):
        ensure_config_exists()
        assert config_path().exists()

    def test_the_template_carries_no_real_printer_address(self, repo_root):
        """The tracked template must never name anybody's actual printer."""

        raw = (repo_root / "tools_config.example.json").read_text(encoding="utf-8")
        for entry in json.loads(raw)["tools"]:
            assert entry["moonraker_host"] == ""

    def test_a_legacy_file_beside_the_app_is_migrated(
        self, config_dir, tmp_path, monkeypatch
    ):
        legacy = tmp_path / "tools_config.json"
        payload = {"tools": [_valid_mapping(moonraker_host="old.local")]}
        legacy.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(config, "legacy_config_path", lambda: legacy)

        ensure_config_exists()

        tools = load_tools_config()
        assert tools[0].moonraker_host == "old.local"


class TestDefaults:
    def test_no_default_names_a_printer(self):
        """A fresh install must not point at anybody's device."""

        assert all(tool.moonraker_host is None for tool in default_tools())

    def test_the_webcam_helper_is_a_one_shot(self):
        entry = next(t for t in default_tools() if t.kind == KIND_ONESHOT)
        assert entry.project_dir == "qidiwebcamdrestart"

    def test_the_dashboards_get_different_ports(self):
        ports = [t.dashboard_port for t in default_tools() if t.dashboard_port]
        assert len(ports) == len(set(ports))
