"""Offscreen smoke tests for the Qt layer.

These do not assert on appearance, which would be fragile. They assert that
the widgets can be constructed and driven at all, which is the failure the
project has actually suffered: a rename that left a name undefined and a
dialog still written against an older configuration shape. Both raise on
construction and both are invisible to a linter run alone.

Anything that opens a modal dialog is deliberately not exercised here.
"""

from __future__ import annotations

import os

import pytest

# Must be set before QApplication is created, so no display is needed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from app_spec import KIND_NORMAL, KIND_ONESHOT, AppSpec
from config import ToolEntry, default_tools, save_tools_config


@pytest.fixture(scope="session")
def qt_app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def populated_config(config_dir):
    save_tools_config(default_tools())
    return config_dir


class TestAppRunnerCard:
    """The card that broke: a constant was referenced but never defined."""

    def _spec(self, tmp_path, kind):
        return AppSpec(
            name="Test printer", project_dir=tmp_path, script="app.py", kind=kind
        )

    def test_a_normal_card_builds(self, qt_app, tmp_path):
        from runner_widget import AppRunner

        card = AppRunner(self._spec(tmp_path, KIND_NORMAL), lambda name, text: None)
        assert card.btn_start.text() == "Start"
        assert not card.is_running()

    def test_a_oneshot_card_shows_a_single_run_action(self, qt_app, tmp_path):
        from runner_widget import AppRunner

        card = AppRunner(self._spec(tmp_path, KIND_ONESHOT), lambda name, text: None)
        assert card.btn_start.text() == "Run"
        assert card.btn_stop.isHidden()

    def test_validation_reports_a_missing_script(self, qt_app, tmp_path):
        from runner_widget import AppRunner

        card = AppRunner(self._spec(tmp_path, KIND_NORMAL), lambda name, text: None)
        ok, message = card.validate()
        assert not ok
        assert message


class TestMainWindow:
    def test_the_window_builds_and_titles_itself_with_the_version(
        self, qt_app, populated_config
    ):
        from main_window import MainWindow
        from version import __version__

        window = MainWindow()
        assert __version__ in window.windowTitle()

    def test_a_card_is_built_for_every_enabled_tool(self, qt_app, populated_config):
        from main_window import MainWindow

        window = MainWindow()
        assert len(window.runners) == len(default_tools())

    def test_stop_all_is_disabled_when_nothing_runs(self, qt_app, populated_config):
        from main_window import MainWindow

        window = MainWindow()
        assert not window.btn_stop_all.isEnabled()
        assert window.btn_start_all.isEnabled()


class TestToolForm:
    """The form that broke: it was still written against the old field names."""

    def test_an_entry_round_trips_through_the_form(self, qt_app):
        from tool_form import ToolForm

        original = ToolEntry(
            id="voron",
            label="Voron Trident",
            project_dir="VoronTemps",
            script="app.py",
            moonraker_host="printer.local",
            moonraker_api_port=7130,
            dashboard_port=5001,
        )

        form = ToolForm()
        form.load(original)
        updated, message = form.to_entry(original)

        assert message == ""
        assert updated == original

    def test_the_host_field_shows_the_host_not_the_whole_url(self, qt_app):
        from tool_form import ToolForm

        entry = ToolEntry(
            id="v",
            label="V",
            project_dir="d",
            script="s.py",
            moonraker_host="printer.local",
        )
        form = ToolForm()
        form.load(entry)
        assert form.edit_moonraker_host.text() == "printer.local"

    def test_a_missing_label_is_reported_rather_than_saved(self, qt_app):
        from tool_form import ToolForm

        entry = ToolEntry(id="v", label="V", project_dir="d", script="s.py")
        form = ToolForm()
        form.load(entry)
        form.edit_label.setText("   ")

        updated, message = form.to_entry(entry)
        assert updated is None
        assert message

    def test_a_blank_host_clears_the_url(self, qt_app):
        from tool_form import ToolForm

        entry = ToolEntry(
            id="v",
            label="V",
            project_dir="d",
            script="s.py",
            moonraker_host="printer.local",
        )
        form = ToolForm()
        form.load(entry)
        form.edit_moonraker_host.setText("")

        updated, _ = form.to_entry(entry)
        assert updated.moonraker_host is None
        assert updated.moonraker_url is None

    def test_a_nonsense_dashboard_port_becomes_none(self, qt_app):
        from tool_form import ToolForm

        entry = ToolEntry(id="v", label="V", project_dir="d", script="s.py")
        form = ToolForm()
        form.load(entry)
        form.edit_dashboard_port.setText("soon")

        updated, _ = form.to_entry(entry)
        assert updated.dashboard_port is None


class TestManageToolsDialog:
    def test_the_dialog_builds_and_lists_every_tool(self, qt_app, populated_config):
        from manage_tools_dialog import ManageToolsDialog

        dialog = ManageToolsDialog()
        assert dialog.list.count() == len(default_tools())

    def test_selecting_a_row_loads_it_into_the_form(self, qt_app, populated_config):
        from manage_tools_dialog import ManageToolsDialog

        dialog = ManageToolsDialog()
        dialog.list.setCurrentRow(0)
        assert dialog.form.edit_label.text() == default_tools()[0].label

    def test_add_appends_a_row(self, qt_app, populated_config):
        from manage_tools_dialog import ManageToolsDialog

        dialog = ManageToolsDialog()
        before = dialog.list.count()
        dialog._on_add()
        assert dialog.list.count() == before + 1
