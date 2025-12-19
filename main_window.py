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
from runner_widget import AppRunner
from styles import build_styles


class MainWindow(QMainWindow):
    def __init__(self, specs: list[AppSpec]):
        super().__init__()
        self.setWindowTitle("Oliver’s App Launcher")
        # Slightly more compact default height (roughly 2/3 of the previous
        # size) so the launcher doesn't feel too tall on screen.
        self.setMinimumSize(QSize(980, 460))

        self.theme = "dark"
        self.setStyleSheet(build_styles(self.theme))

        # Log view
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
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

        # Topbar
        topbar = QHBoxLayout()
        topbar.setSpacing(10)

        self.btn_start_all = QPushButton("Start all")
        self.btn_stop_all = QPushButton("Stop all")
        self.btn_open_logs = QPushButton("Open all logs")
        self.btn_clear = QPushButton("Clear log")

        self.btn_start_all.setObjectName("PrimaryButton")
        self.btn_stop_all.setObjectName("PrimaryButton")

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

        self.btn_light.clicked.connect(lambda: self.set_theme("light"))
        self.btn_dark.clicked.connect(lambda: self.set_theme("dark"))

        topbar.addWidget(self.btn_start_all)
        topbar.addWidget(self.btn_stop_all)
        topbar.addStretch(1)
        topbar.addWidget(self.btn_open_logs)
        topbar.addWidget(self.btn_clear)
        topbar.addSpacing(8)
        topbar.addWidget(self.btn_light)
        topbar.addWidget(self.btn_dark)

        left_layout.addLayout(topbar)

        # Cards container inside scroll
        cards_container = QWidget()
        cards_container.setObjectName("CardsContainer")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        self.runners: list[AppRunner] = []
        for spec in specs:
            runner = AppRunner(spec, self.append_log)
            self.runners.append(runner)
            cards_layout.addWidget(runner)

        cards_layout.addStretch(1)

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

    def stop_all(self) -> None:
        for r in self.runners:
            r.stop()

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
