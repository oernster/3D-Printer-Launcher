# main.py
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app_spec import AppSpec, BASE_DIR
from config import ensure_config_exists, load_tools_config
from main_window import MainWindow


def build_specs() -> list[AppSpec]:
    """Build AppSpec list from the persisted tools configuration.

    This replaces the previously hard-coded Qidi/Voron tools and allows
    users to enable/disable Qidi tools and add arbitrary Klipper printers
    (or other tools) with custom labels.
    """

    ensure_config_exists()
    tools = load_tools_config()

    specs: list[AppSpec] = []
    for t in tools:
        if not t.enabled:
            continue
        specs.append(
            AppSpec(
                name=t.label,
                project_dir=BASE_DIR / t.project_dir,
                script=t.script,
                kind=t.kind,
                moonraker_url=t.moonraker_url,
                moonraker_port=t.moonraker_port,
            )
        )

    return specs


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow(build_specs())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
