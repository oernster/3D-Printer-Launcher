# main.py
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from config import ensure_config_exists
from main_window import MainWindow
from update_check import GitHubReleaseSource, UpdateService, platform_key_for
from update_check_ui import install_update_check
from version import APP_NAME, __version__


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info("%s %s starting", APP_NAME, __version__)

    ensure_config_exists()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)

    win = MainWindow()
    install_update_check(
        win,
        UpdateService(
            GitHubReleaseSource(), __version__, platform_key_for(sys.platform)
        ),
    )
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
