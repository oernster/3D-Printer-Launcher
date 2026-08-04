# main.py
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from config import ensure_config_exists
from main_window import MainWindow
from version import APP_NAME, __version__


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info("%s %s starting", APP_NAME, __version__)

    ensure_config_exists()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
