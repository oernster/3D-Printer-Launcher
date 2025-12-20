# runner_widget.py
from __future__ import annotations

import time
import re
from typing import Callable

from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
)

from app_spec import AppSpec


# Strip ANSI colour / control codes (e.g. from Flask, paramiko, remote shells)
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class AppRunner(QWidget):
    """Card UI + process controller for one app (venv python + live logging)."""

    def __init__(self, spec: AppSpec, log_sink: Callable[[str, str], None], parent=None):
        super().__init__(parent)
        self.spec = spec
        self.log_sink = log_sink

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._on_ready_read)
        self.proc.started.connect(self._on_started)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)

        self._build_ui()
        self._set_status("Stopped", kind="stopped")
        self._refresh_buttons()

    def _build_ui(self) -> None:
        self.setObjectName("AppCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel(self.spec.name)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)

        self.status = QLabel("")
        self.status.setObjectName("StatusBadge")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setFixedHeight(24)
        self.status.setMinimumWidth(90)

        header.addWidget(title, 1)
        header.addWidget(self.status, 0)

        btns = QHBoxLayout()
        btns.setSpacing(8)

        self.btn_start = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")
        self.btn_open_log = QPushButton("Open log")
        self.btn_open_folder = QPushButton("Open folder")

        self.btn_start.setObjectName("StartButton")
        self.btn_stop.setObjectName("StopButton")

        # Special-case UI for one-shot tools (e.g. webcam restart): show a
        # single primary action button and hide Stop. This is driven by the
        # spec.kind field so users can rename tools without breaking behaviour.
        if getattr(self.spec, "kind", "normal") == "oneshot":
            self.btn_start.setText("Run")
            self.btn_stop.hide()

        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_open_log.clicked.connect(self.open_log)
        self.btn_open_folder.clicked.connect(self.open_folder)

        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)
        btns.addStretch(1)
        btns.addWidget(self.btn_open_log)
        btns.addWidget(self.btn_open_folder)

        outer.addLayout(header)
        # The internal script and temp paths are not relevant for end users
        # when this launcher is packaged as a single-file EXE, so we omit the
        # extra meta label here to keep the UI clean.
        outer.addLayout(btns)

    def validate(self) -> tuple[bool, str]:
        if not self.spec.project_dir.exists():
            return False, f"Project dir not found:\n{self.spec.project_dir}"
        if not self.spec.venv_python.exists():
            return False, f"Venv python not found:\n{self.spec.venv_python}"
        if not self.spec.script_path.exists():
            return False, f"Script not found:\n{self.spec.script_path}"
        return True, ""

    def is_running(self) -> bool:
        return self.proc.state() != QProcess.NotRunning

    def start(self) -> None:
        if self.is_running():
            return

        ok, msg = self.validate()
        if not ok:
            self._set_status("Error", kind="error")
            self._log(f"[launcher] {msg}\n")
            QMessageBox.warning(self, f"{self.spec.name} – cannot start", msg)
            self._refresh_buttons()
            return

        self.proc.setWorkingDirectory(str(self.spec.project_dir))
        self.proc.setProgram(str(self.spec.venv_python))

        args = [str(self.spec.script_path)]
        # Optional per-printer Moonraker port (for Klipper dashboards). When
        # specified, append a --port argument so multiple dashboards can run
        # concurrently on different ports.
        if getattr(self.spec, "moonraker_port", None):
            args.extend(["--port", str(self.spec.moonraker_port)])
        self.proc.setArguments(args)

        # ✅ Force UTF-8 for child process stdout/stderr on Windows and inject
        # optional Moonraker URL for Klipper printers. Also pass the launcher
        # label so dashboards can show which printer they belong to.
        env = self.proc.processEnvironment()
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        # Used by dashboard apps (e.g. VoronTemps, Qidi temps) to display a
        # human‑friendly printer name in the HTML.
        env.insert("LAUNCHER_TOOL_LABEL", self.spec.name)
        url = getattr(self.spec, "moonraker_url", None)
        if url:
            env.insert("MOONRAKER_API_URL", url)
        self.proc.setProcessEnvironment(env)

        self._log(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} START ====\n")
        self._log(f"[launcher] Using: {self.spec.venv_python}\n")
        self._log(f"[launcher] Working dir: {self.spec.project_dir}\n")
        self._log(f"[launcher] Script: {self.spec.script_path}\n")
        if getattr(self.spec, "moonraker_url", None):
            self._log(f"[launcher] Moonraker URL: {self.spec.moonraker_url}\n")
        if getattr(self.spec, "moonraker_port", None):
            self._log(f"[launcher] Dashboard port: {self.spec.moonraker_port}\n")

        self._set_status("Starting…", kind="warn")
        self.proc.start()
        self._refresh_buttons()

    def stop(self) -> None:
        if not self.is_running():
            return

        self._log(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} STOP requested ====\n")
        self._set_status("Stopping…", kind="warn")

        # On Windows especially, a Python process running a webserver may not
        # respond promptly to a gentle terminate. To avoid leaving the port
        # bound (which makes the dashboard appear to still be running), we
        # escalate to a hard kill quickly.
        self.proc.terminate()

        kind = getattr(self.spec, "kind", "normal")
        kill_delay_ms = 500 if kind != "oneshot" else 2000
        QTimer.singleShot(kill_delay_ms, self._kill_if_needed)
        self._refresh_buttons()

    def _kill_if_needed(self) -> None:
        if self.is_running():
            self._log("[launcher] Force-killing process.\n")
            self.proc.kill()

    def _log(self, text: str) -> None:
        # Normalise text by removing terminal colour codes so logs stay readable
        # in the GUI and on disk.
        if text:
            text = ANSI_ESCAPE_RE.sub("", text)

        try:
            self.spec.project_dir.mkdir(parents=True, exist_ok=True)
            with open(self.spec.log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(text)
        except Exception:
            pass
        self.log_sink(self.spec.name, text)

    def _on_ready_read(self) -> None:
        data = bytes(self.proc.readAllStandardOutput())
        if data:
            self._log(data.decode("utf-8", errors="replace"))

    def _on_started(self) -> None:
        self._set_status("Running", kind="ok")
        try:
            pid = int(self.proc.processId())
        except Exception:
            pid = 0
        if pid:
            self._log(f"[launcher] PID: {pid}\n")
        self._refresh_buttons()

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self._log(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} EXIT code={exit_code} ====\n")
        self._set_status("Stopped", kind="stopped")
        self._refresh_buttons()

    def _on_error(self, err) -> None:
        self._log(f"\n[launcher] QProcess error: {err}\n")
        self._set_status("Error", kind="error")
        self._refresh_buttons()

    def _set_status(self, text: str, kind: str) -> None:
        self.status.setText(text)
        self.status.setProperty("kind", kind)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _refresh_buttons(self) -> None:
        running = self.is_running()
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def open_log(self) -> None:
        try:
            self.spec.log_path.touch(exist_ok=True)
        except Exception:
            pass
        QDesktopServices.openUrl(self.spec.log_path.as_uri())

    def open_folder(self) -> None:
        QDesktopServices.openUrl(self.spec.project_dir.as_uri())
