"""Dialog for adding, removing and editing the launcher's tools/printers.

The dialog owns the list and the buttons; :class:`tool_form.ToolForm` owns the
per-entry fields and :mod:`webcam_credentials` owns the helper's password
file. Changes are written to the per-user configuration and callers may pass
an ``on_saved`` callback so the main window can live-refresh its cards.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app_spec import BASE_DIR, KIND_NORMAL
from config import ToolEntry, load_tools_config, save_tools_config
from tool_form import ToolForm
from webcam_credentials import (
    credentials_path,
    is_webcam_tool,
    load_password,
    save_password,
)

logger = logging.getLogger(__name__)

DIALOG_WIDTH = 720
DIALOG_HEIGHT = 420

# Relative widths of the list column and the editor column.
LIST_STRETCH = 2
FORM_STRETCH = 3

# Defaults applied to an entry created with Add. The user is expected to
# rename it and point it at their own printer straight away.
NEW_TOOL_LABEL = "New printer"
NEW_TOOL_PROJECT_DIR = "VoronTemps"
NEW_TOOL_SCRIPT = "app.py"
NEW_TOOL_ID_PREFIX = "printer-"


class ManageToolsDialog(QDialog):
    """Editor for the persisted list of launcher tools."""

    def __init__(self, parent=None, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage printers / tools")
        self.resize(DIALOG_WIDTH, DIALOG_HEIGHT)

        self._tools: list[ToolEntry] = load_tools_config()
        # Whether the editor holds in-memory changes. This does not mean they
        # have reached disk; only Save does that.
        self._dirty: bool = False
        self._current_row: int = -1
        self._on_saved_cb = on_saved

        root = QHBoxLayout(self)

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_selection_changed)
        root.addWidget(self.list, LIST_STRETCH)

        form_col = QVBoxLayout()
        self.form = ToolForm()
        form_col.addWidget(self.form)
        form_col.addStretch(1)
        form_col.addLayout(self._build_buttons())
        root.addLayout(form_col, FORM_STRETCH)

        for field in self.form.editable_fields():
            field.textEdited.connect(self._mark_dirty)
        self.form.combo_kind.currentIndexChanged.connect(self._mark_dirty)
        self.form.chk_enabled.toggled.connect(self._mark_dirty)

        self._refresh_list()

    def _build_buttons(self) -> QHBoxLayout:
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
        return btns

    # ---- List handling ----

    def _refresh_list(self) -> None:
        self.list.clear()
        for tool in self._tools:
            item = QListWidgetItem(tool.label)
            item.setData(Qt.UserRole, tool.id)
            self.list.addItem(item)

        if self._tools:
            self.list.setCurrentRow(0)
            self._current_row = 0
        else:
            self._current_row = -1

    def _current_index(self) -> int:
        row = self.list.currentRow()
        return row if 0 <= row < len(self._tools) else -1

    def _restore_selection(self) -> None:
        self.list.blockSignals(True)
        self.list.setCurrentRow(self._current_row)
        self.list.blockSignals(False)

    def _keep_pending_edits(self) -> bool:
        """Offer to keep unsaved edits. False means stay on the current row."""

        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved changes to this printer. Do you want to keep "
            "them before switching?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Yes:
            updated = self._entry_from_form(self._current_row)
            if updated is None:
                return False
            self._tools[self._current_row] = updated

        self._dirty = False
        return True

    def _on_selection_changed(self, row: int) -> None:
        has_pending = self._dirty and 0 <= self._current_row < len(self._tools)
        if has_pending and not self._keep_pending_edits():
            self._restore_selection()
            return

        self._current_row = row

        if not 0 <= row < len(self._tools):
            self.form.clear()
            return

        tool = self._tools[row]
        self.form.load(tool)

        if is_webcam_tool(tool.project_dir, tool.script):
            self.form.set_password(load_password(credentials_path(BASE_DIR)))
        else:
            self.form.set_password("")

        self._dirty = False

    # ---- Editing ----

    def _entry_from_form(self, index: int) -> ToolEntry | None:
        """Read the form back onto entry ``index``, warning on bad input."""

        updated, message = self.form.to_entry(self._tools[index])
        if updated is None:
            QMessageBox.warning(self, "Missing data", message)
        return updated

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _on_add(self) -> None:
        self._tools.append(
            ToolEntry(
                id=f"{NEW_TOOL_ID_PREFIX}{len(self._tools) + 1}",
                label=NEW_TOOL_LABEL,
                project_dir=NEW_TOOL_PROJECT_DIR,
                script=NEW_TOOL_SCRIPT,
                kind=KIND_NORMAL,
                enabled=True,
            )
        )
        self._refresh_list()
        self.list.setCurrentRow(len(self._tools) - 1)
        self._dirty = True

    def _on_remove(self) -> None:
        index = self._current_index()
        if index < 0:
            return
        del self._tools[index]
        self._refresh_list()
        self._dirty = True

    # ---- Saving ----

    def _save_webcam_password(self) -> None:
        """Persist the password field when the webcam helper is selected."""

        index = self._current_index()
        if index < 0:
            return
        tool = self._tools[index]
        if not is_webcam_tool(tool.project_dir, tool.script):
            return
        save_password(credentials_path(BASE_DIR), self.form.password())

    def _on_save(self) -> None:
        index = self._current_index()
        if index >= 0:
            updated = self._entry_from_form(index)
            if updated is None:
                return
            self._tools[index] = updated

        cleaned = [t for t in self._tools if t.label and t.project_dir and t.script]
        if not cleaned:
            QMessageBox.warning(
                self,
                "Invalid configuration",
                "At least one valid printer/tool must be defined.",
            )
            return

        self._save_webcam_password()

        save_tools_config(cleaned)
        self._tools = cleaned
        self._refresh_list()
        self._dirty = False

        if self._on_saved_cb is not None:
            try:
                self._on_saved_cb()
            except Exception:
                # Falls back to leaving the dialog open and usable. A failure
                # to refresh the caller's view must not lose the saved config,
                # which is already on disk by this point.
                logger.exception("The on_saved callback failed")

        QMessageBox.information(
            self,
            "Configuration saved",
            "Tools configuration has been saved.",
        )

    def _on_close(self) -> None:
        """Close, offering to save first when there are unsaved changes."""

        if self._dirty:
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                "You have unsaved changes. Do you want to save them before " "closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )

            if choice == QMessageBox.Cancel:
                return
            if choice == QMessageBox.Yes:
                self._on_save()
                # _on_save clears the flag only when it succeeded.
                if self._dirty:
                    return

        self.accept()
