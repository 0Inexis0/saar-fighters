"""Offline slideshow triggered by system-wide Wayland idle events."""
import json
import os
from pathlib import Path
import random
import sys

from PySide6.QtCore import QObject, QProcess, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget
from rocket import game_active


class Slideshow(QWidget):
    def __init__(self, folder):
        super().__init__()
        self.setWindowTitle("Saar-Fighters · Diashow")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.folder = Path(folder)
        self.slides = json.loads((self.folder / "credits.json").read_text(encoding="utf-8"))
        self.order = []
        self.current = None
        self.picture = QPixmap()
        self.timer = QTimer(self)
        self.timer.setInterval(12_000)
        self.timer.timeout.connect(self.next_slide)

    def next_slide(self):
        if not self.order:
            self.order = list(range(len(self.slides)))
            random.shuffle(self.order)
            if len(self.order) > 1 and self.order[-1] == self.current:
                self.order[0], self.order[-1] = self.order[-1], self.order[0]
        while self.order:
            self.current = self.order.pop()
            self.picture = QPixmap(str(self.folder / self.slides[self.current]["file"]))
            if not self.picture.isNull():
                self.update()
                return True
        self.hide()
        return False

    def start(self):
        if self.isVisible():
            return
        if self.next_slide():
            self.showFullScreen()
            self.raise_()
            self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#13170f"))
        if not self.picture.isNull():
            image = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width() - image.width()) // 2, (self.height() - image.height()) // 2, image)
        painter.fillRect(0, self.height() - 64, self.width(), 64, QColor(0, 0, 0, 170))
        painter.setPen(QColor("#eeece1"))
        if self.current is not None:
            slide = self.slides[self.current]
            painter.drawText(24, self.height() - 38, slide["credit"])
        painter.drawText(24, self.height() - 16, "Maus bewegen oder eine Taste drücken, um zurückzukehren")
        painter.end()

    def mouseMoveEvent(self, event):
        self.hide()

    def mousePressEvent(self, event):
        self.hide()

    def keyPressEvent(self, event):
        self.hide()

    def wheelEvent(self, event):
        self.hide()


class IdleSlideshow(QObject):
    def __init__(self, home, folder, preview=False):
        super().__init__(home)
        self.home = home
        self.view = Slideshow(folder)
        self.stopping = False
        self.buffer = b""
        self.process = QProcess(self)
        self.process.setStandardErrorFile(QProcess.nullDevice())
        self.process.readyReadStandardOutput.connect(self.read_events)
        self.process.finished.connect(self.lost)
        self.process.errorOccurred.connect(lambda _: self.lost())
        self.retry = QTimer(self)
        self.retry.setSingleShot(True)
        self.retry.setInterval(15_000)
        self.retry.timeout.connect(self.start)
        QApplication.instance().aboutToQuit.connect(self.stop)
        home.destroyed.connect(self.stop)
        if not preview and os.environ.get("WAYLAND_DISPLAY"):
            self.start()

    def start(self):
        if not self.stopping and self.process.state() == QProcess.ProcessState.NotRunning:
            self.buffer = b""
            self.process.start(sys.executable, ["-u", str(Path(__file__).with_name("idle_watch.py"))])

    def read_events(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.buffer:
            event, self.buffer = self.buffer.split(b"\n", 1)
            self.handle_event(event.decode().strip())

    def handle_event(self, event):
        if event == "idled" and not QApplication.activeModalWidget() and not game_active():
            self.view.start()
        elif event == "resumed":
            self.view.hide()

    def lost(self, *args):
        self.view.hide()
        if not self.stopping:
            self.retry.start()

    def stop(self, *args):
        if self.stopping:
            return
        self.stopping = True
        self.retry.stop()
        self.view.hide()
        self.view.deleteLater()
        self.process.terminate()
        if not self.process.waitForFinished(1000):
            self.process.kill()
            self.process.waitForFinished(1000)
