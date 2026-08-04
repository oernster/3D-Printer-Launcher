"""The editor form for a single tool entry, used by the Manage dialog.

Kept apart from the dialog so the dialog stays a list plus buttons and so
the field-to-``ToolEntry`` mapping has one home. The form reports validation
failures as a message string; deciding how to show it is the dialog's job.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app_spec import KIND_NORMAL, TOOL_KINDS
from config import DEFAULT_API_PORT, ToolEntry

# Width of the form's label column, so the fields line up.
LABEL_COLUMN_WIDTH = 90

HINT_STYLE = "color: gray; font-size: 11px;"


class ToolForm(QWidget):
    """Editable view of one :class:`ToolEntry`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.edit_label = QLineEdit()
        self.edit_project_dir = QLineEdit()
        self.edit_script = QLineEdit()

        # The user supplies a host or IP only. The full query URL is derived
        # from the host and the API port, so the two cannot disagree.
        self.edit_moonraker_host = QLineEdit()
        self.edit_moonraker_api_port = QLineEdit()
        self.edit_moonraker_api_port.setPlaceholderText(f"{DEFAULT_API_PORT} (default)")
        self.edit_dashboard_port = QLineEdit()

        self.combo_kind = QComboBox()
        self.combo_kind.addItems(TOOL_KINDS)
        self.combo_kind.setToolTip(
            "normal: regular tool with Start/Stop buttons.\n"
            "oneshot: single Run action (no Stop), suitable for tasks like "
            "Qidi Webcam restart."
        )

        self.chk_enabled = QCheckBox("Enabled")

        # Only meaningful for the bundled Qidi webcam restart helper. It is
        # written to an untracked credentials file, never to the tool config.
        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.Password)
        self.edit_password.setPlaceholderText(
            "Only used for the Qidi Webcam restart tool"
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._build_rows()

    # ---- Construction ----

    def _add_row(self, label_text: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(LABEL_COLUMN_WIDTH)
        row.addWidget(label)
        row.addWidget(widget, 1)
        self._layout.addLayout(row)

    def _add_hint(self, text: str) -> None:
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        self._layout.addWidget(hint)

    def _build_rows(self) -> None:
        self._add_row("Label", self.edit_label)
        self._add_row("Project dir", self.edit_project_dir)
        self._add_row("Script", self.edit_script)

        self._add_row("Moonraker IP/host", self.edit_moonraker_host)
        self._add_hint(
            "The printer's hostname or IP address only. The launcher builds "
            "the full Moonraker query URL from this and the API port below."
        )

        self._add_row("Moonraker API port", self.edit_moonraker_api_port)
        self._add_hint(
            f"TCP port where Moonraker listens (default {DEFAULT_API_PORT})."
        )

        self._add_row("Dashboard port", self.edit_dashboard_port)
        self._add_hint(
            "The local port this tool's own web dashboard listens on. Use a "
            "different port per printer to view several at the same time."
        )

        self._add_row("Kind", self.combo_kind)
        self._add_row("Webcam password", self.edit_password)
        self._layout.addWidget(self.chk_enabled)

    # ---- Change tracking ----

    def editable_fields(self) -> tuple[QLineEdit, ...]:
        """Every free-text field, for wiring up change notifications."""

        return (
            self.edit_label,
            self.edit_project_dir,
            self.edit_script,
            self.edit_moonraker_host,
            self.edit_moonraker_api_port,
            self.edit_dashboard_port,
            self.edit_password,
        )

    # ---- Loading and clearing ----

    def load(self, entry: ToolEntry) -> None:
        """Fill every field from the given entry."""

        self.edit_label.setText(entry.label)
        self.edit_project_dir.setText(entry.project_dir)
        self.edit_script.setText(entry.script)
        self.edit_moonraker_host.setText(entry.moonraker_host or "")
        self.edit_moonraker_api_port.setText(str(entry.moonraker_api_port))
        self.edit_dashboard_port.setText(
            str(entry.dashboard_port) if entry.dashboard_port is not None else ""
        )
        self.combo_kind.setCurrentIndex(max(self.combo_kind.findText(entry.kind), 0))
        self.chk_enabled.setChecked(entry.enabled)

    def clear(self) -> None:
        """Reset every field to the state used for a fresh entry."""

        self.edit_label.clear()
        self.edit_project_dir.clear()
        self.edit_script.clear()
        self.edit_moonraker_host.clear()
        self.edit_moonraker_api_port.setText(str(DEFAULT_API_PORT))
        self.edit_dashboard_port.clear()
        self.edit_password.clear()
        self.combo_kind.setCurrentIndex(0)
        self.chk_enabled.setChecked(True)

    def password(self) -> str:
        return self.edit_password.text()

    def set_password(self, password: str) -> None:
        self.edit_password.setText(password)

    # ---- Reading back ----

    def to_entry(self, original: ToolEntry) -> tuple[ToolEntry | None, str]:
        """Apply the form to ``original``.

        Returns the updated entry and an empty string or ``None`` and a
        message explaining what the user still has to fill in.
        """

        label = self.edit_label.text().strip()
        project_dir = self.edit_project_dir.text().strip()
        script = self.edit_script.text().strip()

        if not label or not project_dir or not script:
            return None, "Label, project directory and script are all required."

        host = self.edit_moonraker_host.text().strip()

        api_port_text = self.edit_moonraker_api_port.text().strip()
        api_port = int(api_port_text) if api_port_text.isdigit() else DEFAULT_API_PORT

        dashboard_text = self.edit_dashboard_port.text().strip()
        dashboard_port = int(dashboard_text) if dashboard_text.isdigit() else None

        updated = replace(
            original,
            label=label,
            project_dir=project_dir,
            script=script,
            moonraker_host=host or None,
            moonraker_api_port=api_port,
            dashboard_port=dashboard_port,
            kind=self.combo_kind.currentText().strip() or KIND_NORMAL,
            enabled=self.chk_enabled.isChecked(),
        )
        return updated, ""
