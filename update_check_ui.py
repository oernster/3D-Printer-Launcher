"""The update check's Qt half: triggers, prompt and the menu entry.

Nothing here runs unless ``install_update_check`` is called, which only
the real entrypoint does: the UI smoke tests construct ``MainWindow``
directly and therefore never start a timer or touch the network.

The HTTP call runs on a worker thread and the result crosses back to the
UI thread through a Signal connected to a bound method of a UI-thread
QObject, so delivery is a queued connection and widgets are only touched
where Qt requires it.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QMessageBox

from update_check import (
    UpdateService,
    UpdateStatus,
    load_skipped_version,
    save_skipped_version,
)
from version import APP_NAME

LAUNCH_CHECK_DELAY_MS = 3000
HOURS_PER_DAY = 24
MINUTES_PER_HOUR = 60
SECONDS_PER_MINUTE = 60
MS_PER_SECOND = 1000
RECHECK_INTERVAL_MS = (
    HOURS_PER_DAY * MINUTES_PER_HOUR * SECONDS_PER_MINUTE * MS_PER_SECOND
)

MENU_ITEM_TEXT = "Check for updates"
PROMPT_TITLE = "Update available"
UP_TO_DATE_TEXT = "You are running the latest version."
CHECK_FAILED_TEXT = "The update check could not reach GitHub. Please try again later."
DOWNLOAD_TEXT = "Download"
SKIP_TEXT = "Skip this version"
LATER_TEXT = "Later"


class UpdateCheckController(QObject):
    """Runs the update check off the UI thread and presents the outcome."""

    _result_ready = Signal(object, bool)

    def __init__(self, window, service: UpdateService) -> None:
        super().__init__(window)
        self._window = window
        self._service = service
        self._result_ready.connect(self._present_result)
        QTimer.singleShot(LAUNCH_CHECK_DELAY_MS, self.check_automatically)
        self._recheck_timer = QTimer(self)
        self._recheck_timer.setInterval(RECHECK_INTERVAL_MS)
        self._recheck_timer.timeout.connect(self.check_automatically)
        self._recheck_timer.start()

    def check_automatically(self) -> None:
        """Run a check that honours the skip and stays silent on failure."""
        self._start_worker(manual=False)

    def check_manually(self) -> None:
        """Run a check that ignores the skip and reports every outcome."""
        self._start_worker(manual=True)

    def _start_worker(self, manual: bool) -> None:
        skipped = None if manual else load_skipped_version()

        def run() -> None:
            try:
                status = self._service.check(skipped)
            except Exception:  # noqa: BLE001 (any error reads as unreachable)
                status = None
            self._result_ready.emit(status, manual)

        threading.Thread(target=run, daemon=True).start()

    def _present_result(self, status: UpdateStatus | None, manual: bool) -> None:
        if status is None:
            if manual:
                QMessageBox.information(self._window, MENU_ITEM_TEXT, CHECK_FAILED_TEXT)
            return
        if status.update_available:
            self._prompt(status)
            return
        if manual:
            QMessageBox.information(self._window, MENU_ITEM_TEXT, UP_TO_DATE_TEXT)

    def _prompt(self, status: UpdateStatus) -> None:
        box = QMessageBox(self._window)
        box.setWindowTitle(PROMPT_TITLE)
        box.setText(
            f"{APP_NAME} {status.latest} is available. "
            f"You are running {status.current}."
        )
        download = box.addButton(DOWNLOAD_TEXT, QMessageBox.AcceptRole)
        skip = box.addButton(SKIP_TEXT, QMessageBox.DestructiveRole)
        box.addButton(LATER_TEXT, QMessageBox.RejectRole)
        box.setDefaultButton(download)
        box.exec()
        clicked = box.clickedButton()
        if clicked is download:
            url = status.download_url or status.page_url
            if url:
                QDesktopServices.openUrl(QUrl(url))
        elif clicked is skip and status.latest:
            save_skipped_version(status.latest)


def install_update_check(window, service: UpdateService) -> UpdateCheckController:
    """Attach the controller to ``window`` and add the Tools menu entry.

    Called by the entrypoint only, so a window built in a test carries no
    timers and makes no network calls.
    """
    controller = UpdateCheckController(window, service)
    window.update_controller = controller
    menu = getattr(window, "tools_menu", None)
    if menu is not None:
        action = QAction(MENU_ITEM_TEXT, window)
        action.triggered.connect(controller.check_manually)
        menu.addSeparator()
        menu.addAction(action)
    return controller
