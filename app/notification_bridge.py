"""Supervise the session notification listener without blocking the Qt UI."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QProcess, QTimer
from PySide6.QtWidgets import QApplication


class NotificationBridge(QObject):
    def __init__(self, center, home, preview=False):
        super().__init__(home)
        self.center = center
        self.enabled = not preview and sys.platform == "linux"
        self.stopping = False
        self.buffer = b""
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.process.readAllStandardError)
        self.process.finished.connect(self.lost)
        self.process.errorOccurred.connect(self.lost)
        self.retry = QTimer(self)
        self.retry.setSingleShot(True)
        self.retry.setInterval(15000)
        self.retry.timeout.connect(self.start)
        QApplication.instance().aboutToQuit.connect(self.stop)
        home.destroyed.connect(self.stop)
        if self.enabled:
            self.start()

    def start(self):
        if self.enabled and not self.stopping and self.process.state() == QProcess.ProcessState.NotRunning:
            self.buffer = b""
            self.process.start(sys.executable, ["-u", str(Path(__file__).with_name("notification_watch.py"))])

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if len(line) > 65536:
                continue
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(event, dict):
                self.center.desktop_event(event)
        if len(self.buffer) > 65536:
            self.buffer = b""

    def lost(self, *_):
        if self.enabled and not self.stopping:
            self.center.desktop_event({"event": "unavailable"})
            self.retry.start()

    def stop(self, *_):
        if self.stopping:
            return
        self.stopping = True
        self.retry.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(1000):
                self.process.kill()
                self.process.waitForFinished(1000)
