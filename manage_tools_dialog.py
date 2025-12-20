from __future__ import annotations

from dataclasses import replace
from typing import List, Callable, Optional
from pathlib import Path
from urllib.parse import urlparse
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QMessageBox,
)

from config import load_tools_config, save_tools_config, ToolEntry
from app_spec import BASE_DIR


class ManageToolsDialog(QDialog):
    """Dialog for adding/removing/editing launcher tools/printers.

    Changes are written to tools_config.json. Callers may pass an ``on_saved``
    callback that will be invoked after a successful save, which the main
    window can use to live-refresh its visible tools.
    """

    def __init__(self, parent=None, on_saved: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage printers / tools")
        self.resize(720, 420)

        self._tools: List[ToolEntry] = load_tools_config()
        # Tracks whether there are unsaved in-memory changes in the editor
        # (either to the selected entry or the list structure itself). This
        # does *not* mean they are persisted to disk yet.
        self._dirty: bool = False
        self._current_row: int = -1
        self._on_saved_cb: Optional[Callable[[], None]] = on_saved

        root = QHBoxLayout(self)

        # Left: list of tools
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_selection_changed)
        root.addWidget(self.list, 2)

        # Right: editor form
        form_col = QVBoxLayout()

        def row(label_text: str, widget):
            row_l = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(90)
            row_l.addWidget(lbl)
            row_l.addWidget(widget, 1)
            form_col.addLayout(row_l)

        self.edit_label = QLineEdit()
        self.edit_project_dir = QLineEdit()
        self.edit_script = QLineEdit()
        # Moonraker IP/host (we build the full URL internally so users don't
        # have to remember the full /printer/objects/query path).
        self.edit_moonraker_url = QLineEdit()
        # Moonraker API TCP port (where Moonraker listens, usually 7125).
        self.edit_moonraker_api_port = QLineEdit()
        self.edit_moonraker_api_port.setPlaceholderText("7125 (default)")
        # Local dashboard (Flask) port for the UI itself.
        self.edit_moonraker_port = QLineEdit()
        self.combo_kind = QComboBox()
        self.combo_kind.addItems(["normal", "oneshot"])
        self.combo_kind.setToolTip(
            "normal: regular tool with Start/Stop buttons.\n"
            "oneshot: single Run action (no Stop), suitable for tasks like "
            "Qidi Webcam restart."
        )
        self.chk_enabled = QCheckBox("Enabled")

        # Optional password field, only meaningful for the Qidi webcam restart
        # helper. It writes to qidiwebcamdrestart/credentials.json which is
        # ignored by git.
        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.Password)
        self.edit_password.setPlaceholderText(
            "Only used for the Qidi Webcam restart tool"
        )

        row("Label", self.edit_label)
        row("Project dir", self.edit_project_dir)
        row("Script", self.edit_script)
        row("Moonraker IP/host", self.edit_moonraker_url)
        hint_url = QLabel(
            "Example: 192.168.1.226  (Moonraker typically listens on port 7125)"
        )
        hint_url.setWordWrap(True)
        hint_url.setStyleSheet("color: gray; font-size: 11px;")
        form_col.addWidget(hint_url)

        row("Moonraker API port", self.edit_moonraker_api_port)
        hint_api_port = QLabel("TCP port where Moonraker listens (default 7125).")
        hint_api_port.setWordWrap(True)
        hint_api_port.setStyleSheet("color: gray; font-size: 11px;")
        form_col.addWidget(hint_api_port)

        row("Dashboard port", self.edit_moonraker_port)
        hint_port = QLabel(
            "Example: 5000. Use a different port per printer if you want to "
            "view multiple dashboards at the same time."
        )
        hint_port.setWordWrap(True)
        hint_port.setStyleSheet("color: gray; font-size: 11px;")
        form_col.addWidget(hint_port)
        row("Kind", self.combo_kind)
        row("Webcam password", self.edit_password)
        form_col.addWidget(self.chk_enabled)

        form_col.addStretch(1)

        # Buttons
        btns = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_remove = QPushButton("Remove")
        self.btn_save = QPushButton("Save changes")
        self.btn_close = QPushButton("Close")

        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_close.clicked.connect(self._on_close)

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_remove)
        btns.addStretch(1)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_close)

        form_col.addLayout(btns)

        root.addLayout(form_col, 3)

        # Mark the form dirty whenever the user edits any visible field
        for w in (
            self.edit_label,
            self.edit_project_dir,
            self.edit_script,
            self.edit_moonraker_url,
            self.edit_moonraker_api_port,
            self.edit_moonraker_port,
            self.edit_password,
        ):
            w.textEdited.connect(self._mark_dirty)
        self.combo_kind.currentIndexChanged.connect(self._mark_dirty)
        self.chk_enabled.toggled.connect(self._mark_dirty)

        self._refresh_list()

    # ---- Internal helpers ----

    def _refresh_list(self) -> None:
        self.list.clear()
        for t in self._tools:
            item = QListWidgetItem(t.label)
            item.setData(Qt.UserRole, t.id)
            self.list.addItem(item)

        if self._tools:
            self.list.setCurrentRow(0)
            self._current_row = 0
        else:
            self._current_row = -1

    def _current_index(self) -> int:
        row = self.list.currentRow()
        return row if 0 <= row < len(self._tools) else -1

    def _on_selection_changed(self, row: int) -> None:
        # If there are unsaved edits for the previously selected entry, offer
        # to keep or discard them before switching.
        if self._dirty and self._current_row != -1 and 0 <= self._current_row < len(self._tools):
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                "You have unsaved changes to this printer. Do you want to keep them before switching?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )

            if choice == QMessageBox.Cancel:
                # Revert the selection change
                self.list.blockSignals(True)
                self.list.setCurrentRow(self._current_row)
                self.list.blockSignals(False)
                return

            if choice == QMessageBox.Yes:
                updated = self._validate_from_form(self._tools[self._current_row])
                if updated is None:
                    # Validation failed; stay on current row
                    self.list.blockSignals(True)
                    self.list.setCurrentRow(self._current_row)
                    self.list.blockSignals(False)
                    return
                self._tools[self._current_row] = updated

            # Either kept or discarded; form is now considered clean
            self._dirty = False

        self._current_row = row

        if row < 0 or row >= len(self._tools):
            self._clear_form()
            return
        t = self._tools[row]
        self.edit_label.setText(t.label)
        self.edit_project_dir.setText(t.project_dir)
        self.edit_script.setText(t.script)

        # Extract just the host part from any stored Moonraker URL so the user
        # only has to think about IP/hostname; the fixed path and scheme are
        # handled behind the scenes.
        host_text = ""
        if t.moonraker_url:
            try:
                parsed = urlparse(t.moonraker_url)
                host_text = parsed.hostname or t.moonraker_url
            except Exception:
                host_text = t.moonraker_url
        self.edit_moonraker_url.setText(host_text)

        # API port: use stored value or default to 7125 if not set.
        api_port_val = getattr(t, "moonraker_api_port", None) or 7125
        self.edit_moonraker_api_port.setText(str(api_port_val))

        # Dashboard (Flask) port is optional.
        self.edit_moonraker_port.setText(
            str(t.moonraker_port) if t.moonraker_port is not None else ""
        )
        idx = self.combo_kind.findText(t.kind)
        self.combo_kind.setCurrentIndex(idx if idx >= 0 else 0)
        self.chk_enabled.setChecked(t.enabled)

        if self._is_qidi_webcam_tool(t):
            self._load_webcam_password()
        else:
            self.edit_password.clear()
        self._dirty = False

    def _clear_form(self) -> None:
        self.edit_label.clear()
        self.edit_project_dir.clear()
        self.edit_script.clear()
        self.edit_moonraker_url.clear()
        self.edit_moonraker_api_port.setText("7125")
        self.edit_moonraker_port.clear()
        self.edit_password.clear()
        self.combo_kind.setCurrentIndex(0)
        self.chk_enabled.setChecked(True)

    def _on_add(self) -> None:
        new = ToolEntry(
            id=f"printer-{len(self._tools)+1}",
            label="New printer",
            project_dir="VoronTemps",
            script="app.py",
            kind="normal",
            enabled=True,
        )
        self._tools.append(new)
        self._refresh_list()
        self.list.setCurrentRow(len(self._tools) - 1)
        self._dirty = True

    def _on_remove(self) -> None:
        idx = self._current_index()
        if idx < 0:
            return
        del self._tools[idx]
        self._refresh_list()
        self._dirty = True

    def _on_save(self) -> None:
        idx = self._current_index()
        if idx >= 0:
            # Update the currently selected entry from the form before saving
            updated = self._validate_from_form(self._tools[idx])
            if updated is None:
                return
            self._tools[idx] = updated

        # Also validate all entries to avoid saving obviously broken config
        cleaned: List[ToolEntry] = []
        for t in self._tools:
            if not t.label or not t.project_dir or not t.script:
                continue
            cleaned.append(t)

        if not cleaned:
            QMessageBox.warning(self, "Invalid configuration", "At least one valid printer/tool must be defined.")
            return

        # Persist any Qidi webcam password for the currently selected tool
        # before we overwrite the in-memory list.
        self._maybe_save_webcam_password()

        save_tools_config(cleaned)
        self._tools = cleaned
        self._refresh_list()
        self._dirty = False

        # Notify caller (e.g. MainWindow) so it can live-refresh its tool list.
        if self._on_saved_cb is not None:
            try:
                self._on_saved_cb()
            except Exception:
                # Do not let callback failures break the dialog UX.
                pass

        QMessageBox.information(
            self,
            "Configuration saved",
            "Tools configuration has been saved.",
        )

    def _validate_from_form(self, original: ToolEntry) -> ToolEntry | None:
        label = self.edit_label.text().strip()
        project_dir = self.edit_project_dir.text().strip()
        script = self.edit_script.text().strip()
        host = self.edit_moonraker_url.text().strip()

        api_port_text = self.edit_moonraker_api_port.text().strip()
        if api_port_text.isdigit():
            moonraker_api_port = int(api_port_text)
        else:
            moonraker_api_port = 7125

        port_text = self.edit_moonraker_port.text().strip()
        moonraker_port: int | None
        if port_text.isdigit():
            moonraker_port = int(port_text)
        else:
            moonraker_port = None
        kind = self.combo_kind.currentText().strip() or "normal"
        enabled = self.chk_enabled.isChecked()

        if not label or not project_dir or not script:
            QMessageBox.warning(
                self,
                "Missing data",
                "Label, project directory and script are all required.",
            )
            return None

        # Build the full Moonraker API URL from the IP/host. We assume the
        # Moonraker API port (default 7125) and fixed /printer/objects/query
        # path so the user doesn't have to type it.
        moonraker_url: str | None
        if host:
            api_port = moonraker_api_port or 7125
            moonraker_url = f"http://{host}:{api_port}/printer/objects/query"
        else:
            moonraker_url = None

        return replace(
            original,
            label=label,
            project_dir=project_dir,
            script=script,
            moonraker_api_port=moonraker_api_port,
            moonraker_url=moonraker_url,
            moonraker_port=moonraker_port,
            kind=kind,
            enabled=enabled,
        )

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _on_close(self) -> None:
        """Handle Close button with optional unsaved-changes warning."""

        if self._dirty:
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                "You have unsaved changes. Do you want to save them before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )

            if choice == QMessageBox.Cancel:
                return
            if choice == QMessageBox.Yes:
                self._on_save()
                # _on_save will reset _dirty on success
                if self._dirty:
                    # Save failed or was cancelled by validation
                    return

        self.accept()

    # ---- Qidi webcam password helpers ----

    def _credentials_path(self) -> Path:
        return BASE_DIR / "qidiwebcamdrestart" / "credentials.json"

    def _is_qidi_webcam_tool(self, t: ToolEntry) -> bool:
        return t.project_dir == "qidiwebcamdrestart" and t.script == "webcamdrestart.py"

    def _load_webcam_password(self) -> None:
        path = self._credentials_path()
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            pw = data.get("password")
            if isinstance(pw, str):
                self.edit_password.setText(pw)
            else:
                self.edit_password.clear()
        except FileNotFoundError:
            self.edit_password.clear()
        except Exception:
            # On parse errors, just clear the field rather than raising.
            self.edit_password.clear()

    def _maybe_save_webcam_password(self) -> None:
        idx = self._current_index()
        if idx < 0:
            return
        t = self._tools[idx]
        if not self._is_qidi_webcam_tool(t):
            return

        pw = self.edit_password.text()
        path = self._credentials_path()

        # If the password is blank, remove any existing credentials file so
        # the helper will error out clearly rather than using stale data.
        if not pw.strip():
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"password": pw}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


