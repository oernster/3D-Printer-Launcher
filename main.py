# main.py
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app_spec import AppSpec, BASE_DIR
from main_window import MainWindow


def build_specs() -> list[AppSpec]:
    return [
        AppSpec(
            name="Qidi Temps",
            project_dir=BASE_DIR / "qidi-temps",
            script="app.py",
        ),
        AppSpec(
            name="Qidi Webcamd restart",
            project_dir=BASE_DIR / "qidiwebcamdrestart",
            script="webcamdrestart.py",
        ),
        AppSpec(
            name="Voron Temps",
            project_dir=BASE_DIR / "VoronTemps",
            script="app.py",
        ),
    ]


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow(build_specs())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
