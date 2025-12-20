# main_window.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDesktopServices, QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QFrame,
    QSplitter,
)

from app_spec import AppSpec, BASE_DIR
from config import load_tools_config
from runner_widget import AppRunner
from manage_tools_dialog import ManageToolsDialog
from styles import build_styles


class MainWindow(QMainWindow):
    def __init__(self, specs: list[AppSpec]):
        super().__init__()
        self.setWindowTitle("3D Printer Launcher")
        # Increase default height further so the cards and log have extra space
        # on modern displays. This is roughly +6cm over the original height.
        self.setMinimumSize(QSize(980, 700))

        self.theme = "dark"
        self.setStyleSheet(build_styles(self.theme))

        # Log view
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        # Wrap log lines at the widget edge so long messages don't run off
        # the side of the screen.
        self.log_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log_view.setObjectName("LogView")

        # Root layout
        central = QWidget()
        central.setObjectName("Root")
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # -------- Left panel --------
        left = QWidget()
        left.setObjectName("LeftPanel")
        # Prevent the right log panel from visually "crushing" this section
        # when the window is resized or on unusual DPI setups.
        left.setMinimumWidth(360)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(12)

        # Topbar (two-row layout so button text is never crushed)
        topbar_col = QVBoxLayout()
        topbar_col.setSpacing(6)

        topbar_main = QHBoxLayout()
        topbar_main.setSpacing(10)

        topbar_secondary = QHBoxLayout()
        topbar_secondary.setSpacing(8)

        self.btn_start_all = QPushButton("Start all")
        self.btn_stop_all = QPushButton("Stop all")
        self.btn_open_logs = QPushButton("Open all logs")
        self.btn_clear = QPushButton("Clear log")
        self.btn_manage_printers = QPushButton("Manage printers")

        self.btn_start_all.setObjectName("PrimaryButton")
        self.btn_stop_all.setObjectName("PrimaryButton")
        self.btn_manage_printers.setObjectName("PrimaryButton")

        self.btn_light = QPushButton("☀")
        self.btn_dark = QPushButton("🌙")
        self.btn_light.setObjectName("IconButton")
        self.btn_dark.setObjectName("IconButton")
        self.btn_light.setFixedSize(40, 34)
        self.btn_dark.setFixedSize(40, 34)

        self.btn_start_all.clicked.connect(self.start_all)
        self.btn_stop_all.clicked.connect(self.stop_all)
        self.btn_open_logs.clicked.connect(self.open_all_logs)
        self.btn_clear.clicked.connect(self.log_view.clear)
        self.btn_manage_printers.clicked.connect(self.open_manage_tools)

        self.btn_light.clicked.connect(lambda: self.set_theme("light"))
        self.btn_dark.clicked.connect(lambda: self.set_theme("dark"))

        # First row: main actions (start/stop/manage)
        topbar_main.addWidget(self.btn_start_all)
        topbar_main.addWidget(self.btn_stop_all)
        topbar_main.addWidget(self.btn_manage_printers)
        topbar_main.addStretch(1)

        # Second row: logs + theme toggles
        topbar_secondary.addWidget(self.btn_open_logs)
        topbar_secondary.addWidget(self.btn_clear)
        topbar_secondary.addStretch(1)
        topbar_secondary.addWidget(self.btn_light)
        topbar_secondary.addWidget(self.btn_dark)

        topbar_col.addLayout(topbar_main)
        topbar_col.addLayout(topbar_secondary)

        left_layout.addLayout(topbar_col)

        # Cards container inside scroll
        cards_container = QWidget()
        cards_container.setObjectName("CardsContainer")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        self.cards_layout: QVBoxLayout = cards_layout
        self.runners: list[AppRunner] = []
        self._build_runners(specs)

        scroll = QScrollArea()
        scroll.setObjectName("CardsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(cards_container)

        left_layout.addWidget(scroll, 1)

        # -------- Right panel --------
        right = QWidget()
        right.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        log_title = QLabel("Live output")
        log_title.setObjectName("PanelTitle")

        right_layout.addWidget(log_title)
        right_layout.addWidget(self.log_view, 1)

        # Assemble via splitter so the user can resize panels and neither
        # can overrun the other.
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)  # left panel
        splitter.setStretchFactor(1, 2)  # right panel
        splitter.setHandleWidth(4)

        # Give an initial split with the divider pushed a bit further to the
        # right so the left tools column has more space by default.
        # (500px / 480px ≈ 51% / 49% of 980px total.)
        splitter.setSizes([500, 480])

        root.addWidget(splitter)
        self.setCentralWidget(central)

        # Menu
        menu = self.menuBar().addMenu("Tools")

        act_open_dev = QAction("Open Development folder", self)
        act_open_dev.triggered.connect(self.open_dev_folder)
        menu.addAction(act_open_dev)

        # Configuration / management
        act_manage = QAction("Manage printers / tools", self)
        act_manage.triggered.connect(self.open_manage_tools)
        menu.addAction(act_manage)

        # License link (opens the bundled LGPLv3 LICENSE file)
        act_license = QAction("View LGPL-3 License", self)
        act_license.triggered.connect(self.open_license)
        menu.addAction(act_license)

        menu.addSeparator()
        act_light = QAction("Light mode", self)
        act_dark = QAction("Dark mode", self)
        act_light.triggered.connect(lambda: self.set_theme("light"))
        act_dark.triggered.connect(lambda: self.set_theme("dark"))
        menu.addAction(act_light)
        menu.addAction(act_dark)

        # Apply initial theme once UI is wired up
        self.set_theme(self.theme)
        # Initialise top-level Start all / Stop all button states
        self._refresh_all_buttons()

    def set_theme(self, theme: str) -> None:
        """Switch between light and dark themes and update toggle state."""

        self.theme = theme
        self.setStyleSheet(build_styles(self.theme))

        # Highlight active icon button so you can see current theme
        if hasattr(self, "btn_light") and hasattr(self, "btn_dark"):
            self.btn_light.setProperty("active", theme == "light")
            self.btn_dark.setProperty("active", theme == "dark")
            for btn in (self.btn_light, self.btn_dark):
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def append_log(self, app_name: str, text: str) -> None:
        if text.strip() and "\n" not in text.strip("\n"):
            line = f"[{app_name}] {text}"
        else:
            line = f"[{app_name}]\n{text}"
        self.log_view.appendPlainText(line.rstrip("\n"))

    def start_all(self) -> None:
        for r in self.runners:
            r.start()
        self._refresh_all_buttons()

    def stop_all(self) -> None:
        for r in self.runners:
            r.stop()
        self._refresh_all_buttons()

    def open_all_logs(self) -> None:
        for r in self.runners:
            r.open_log()

    def open_dev_folder(self) -> None:
        """Open the root 3Dprinterlauncher project folder."""

        dev = BASE_DIR
        if dev.exists():
            QDesktopServices.openUrl(dev.as_uri())

    def open_license(self) -> None:
        """Open the LGPL-3 license file in the system viewer."""

        lic = BASE_DIR / "LICENSE"
        if lic.exists():
            QDesktopServices.openUrl(lic.as_uri())

    def open_manage_tools(self) -> None:
        """Open the Manage Tools dialog.
        """

        dlg = ManageToolsDialog(self, on_saved=self._reload_tools_from_config)
        dlg.exec()

    # ---- Dynamic tools management ----

    def _build_runners(self, specs: list[AppSpec]) -> None:
        """(Re)build the AppRunner cards list from the given specs."""

        # Clear existing widgets from the layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        self.runners = []
        for spec in specs:
            runner = AppRunner(spec, self.append_log)
            self.runners.append(runner)
            self.cards_layout.addWidget(runner)

        self.cards_layout.addStretch(1)
        self._refresh_all_buttons()

    def _reload_tools_from_config(self) -> None:
        """Reload enabled tools from tools_config.json and refresh the UI.

        This is used as a callback from the ManageToolsDialog so that changes
        take effect immediately without restarting the application.
        """

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
                    moonraker_url=getattr(t, "moonraker_url", None),
                    moonraker_port=getattr(t, "moonraker_port", None),
                )
            )

        self._build_runners(specs)

    def _refresh_all_buttons(self) -> None:
        """Update Start all / Stop all button enabled state.

        - Start all is enabled if at least one tool is not running.
        - Stop all is enabled if at least one tool is running.
        This gives users clear feedback which bulk action currently makes
        sense and avoids redundant clicks.
        """

        if not hasattr(self, "runners"):
            return

        any_running = any(r.is_running() for r in self.runners)
        any_stopped = any(not r.is_running() for r in self.runners)

        self.btn_start_all.setEnabled(any_stopped)
        self.btn_stop_all.setEnabled(any_running)
