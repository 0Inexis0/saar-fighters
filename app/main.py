#!/usr/bin/env python3
"""Saar-Fighters Home: a small native launcher, no browser runtime."""
import argparse
import os
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QDateTime, QProcess, QProcessEnvironment, Qt, QTimer, QSize, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QPen
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
SOCKET = f"saar-home-{os.getuid()}"

PATHS = {
    "music": '<path d="M9 18V5l12-3v13M9 8l12-3"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="18" cy="15" rx="3" ry="2"/>',
    "web": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
    "wifi": '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M8.5 16a5.5 5.5 0 0 1 7 0"/><circle cx="12" cy="20" r=".8"/>',
    "sound": '<path d="M3 9h4l5-4v14l-5-4H3zM16 8a6 6 0 0 1 0 8M19 4a11 11 0 0 1 0 16"/>',
    "bluetooth": '<path d="M6 6l12 12-6 4V2l6 4L6 18"/>',
    "update": '<path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5M4 16a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
    "folder": '<path d="M3 6h7l2 3h9v11H3zM3 6V4h7l2 2h9v3"/>',
    "power": '<path d="M12 2v10M6 5a9 9 0 1 0 12 0"/>',
    "restart": '<path d="M4 9a9 9 0 1 1 1 9M4 3v6h6"/>',
    "home": '<path d="M3 11l9-8 9 8M6 9v12h5v-7h3v7h4V9"/>',
}


def icon(name, color="#e6e9df", size=40):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
           f'<g fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" '
           f'stroke-linejoin="round">{PATHS[name]}</g></svg>')
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class Tile(QPushButton):
    def __init__(self, symbol, title, subtitle, action, accent=False):
        super().__init__()
        self.setObjectName("primaryTile" if accent else "tile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(170, 113)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 16)
        top = QHBoxLayout()
        image = QLabel()
        image.setPixmap(icon(symbol, "#152118" if accent else "#edaa66", 32).pixmap(QSize(32, 32)))
        top.addWidget(image)
        top.addStretch()
        arrow = QLabel("↗")
        arrow.setStyleSheet(f"font-size: 22px; color: {'#294a35' if accent else '#718078'}")
        top.addWidget(arrow)
        layout.addLayout(top)
        layout.addStretch()
        text = QLabel(title)
        text.setObjectName("tileTitle")
        text.setStyleSheet(f"color: {'#102318' if accent else '#f3f3eb'};")
        layout.addWidget(text)
        sub = QLabel(subtitle)
        sub.setObjectName("tileSubtitle")
        sub.setStyleSheet(f"color: {'#304b37' if accent else '#a8b5ae'};")
        layout.addWidget(sub)
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.clicked.connect(action)


class UpdateDialog(QDialog):
    def __init__(self, parent, preview=False):
        super().__init__(parent)
        self.setWindowTitle("System aktualisieren")
        self.resize(740, 490)
        layout = QVBoxLayout(self)
        title = QLabel("Updates für euren Rechner.")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        info = QLabel("Aktualisiert Arch und installierte Flatpak-Apps.\n"
                      "Du brauchst Internet und das Passwort des Wartungskontos.\n"
                      "Bitte Netzteil anschließen und währenddessen nicht ausschalten.")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Bereit. Erst „Update starten“ löst die Passwortabfrage aus.")
        layout.addWidget(self.output, 1)
        self.state = QLabel("Noch nicht gestartet")
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        buttons = QHBoxLayout()
        self.start = QPushButton("Update starten")
        self.start.setObjectName("confirm")
        self.close_button = QPushButton("Zurück")
        buttons.addWidget(self.start)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished_update)
        self.process.errorOccurred.connect(self.process_error)
        self.start.clicked.connect(lambda: self.begin(preview))
        self.close_button.clicked.connect(self.reject)

    def begin(self, preview):
        if preview:
            self.state.setText("Vorschau: Auf diesem Rechner wird kein Update ausgeführt.")
            return
        self.start.setEnabled(False)
        self.close_button.setEnabled(False)
        self.output.clear()
        self.state.setText("Warte auf Freigabe / Update läuft …")
        self.process.start("pkexec", ["/usr/local/libexec/saar-update"])

    def read_output(self):
        self.output.appendPlainText(bytes(self.process.readAllStandardOutput()).decode(errors="replace"))

    def finished_update(self, code, status):
        self.close_button.setEnabled(True)
        if status == QProcess.ExitStatus.NormalExit and code == 0:
            self.state.setText("Update erfolgreich. Du kannst den Rechner jetzt neu starten.")
        elif code in (126, 127):
            self.state.setText("Update nicht freigegeben oder abgebrochen. Es wurde nicht erfolgreich abgeschlossen.")
            self.start.setEnabled(True)
        else:
            self.state.setText("Update fehlgeschlagen. Bitte die Ausgabe dem Administrator zeigen.")
            self.start.setEnabled(True)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.state.setText("Die Update-Verwaltung konnte nicht gestartet werden.")
            self.close_button.setEnabled(True)
            self.start.setEnabled(True)

    def reject(self):
        if self.process.state() == QProcess.ProcessState.NotRunning:
            super().reject()

    def closeEvent(self, event):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            event.ignore()
        else:
            super().closeEvent(event)


class Home(QWidget):
    def __init__(self, preview=False):
        super().__init__()
        self.preview = preview
        self.setObjectName("home")
        self.setWindowTitle("Saar-Fighters · Startseite")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 540)
        self.background = QSvgRenderer(str(ASSETS / "terrain.svg"))
        self.processes = []
        self.last_action = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 24, 48, 22)
        layout.setSpacing(16)
        header = QHBoxLayout()
        brand = QLabel("SF  /  SAAR-FIGHTERS AV")
        brand.setStyleSheet("font-size: 15px; font-weight: 800; letter-spacing: 2px; color: #edaa66;")
        header.addWidget(brand)
        header.addStretch()
        self.network = QLabel("Verbindung wird geprüft")
        self.network.setStyleSheet("font-size: 13px; color: #bdc9bf;")
        header.addWidget(self.network)
        header.addSpacing(25)
        self.clock = QLabel()
        self.clock.setStyleSheet("font-size: 22px; font-weight: 600;")
        header.addWidget(self.clock)
        layout.addLayout(header)

        hero = QVBoxLayout()
        hero.setSpacing(4)
        eyebrow = QLabel("EUER VEREIN. EUER PLATZ.")
        eyebrow.setStyleSheet("color: #b1bfae; font-size: 11px; letter-spacing: 3px; font-weight: 600;")
        hero.addWidget(eyebrow)
        self.headline = QLabel("Ankommen. Musik an.")
        self.headline.setStyleSheet("font-size: 42px; font-weight: 800; letter-spacing: -1px;")
        hero.addWidget(self.headline)
        self.description = QLabel("Ein Klick genügt. Was möchtest du machen?")
        self.description.setStyleSheet("font-size: 15px; color: #b8c3b9;")
        hero.addWidget(self.description)
        layout.addLayout(hero)

        grid = QGridLayout()
        grid.setSpacing(14)
        specs = [
            ("music", "Spotify", "Der Sound für euren Tag", "spotify", True),
            ("web", "Internet", "Browser öffnen", "web", False),
            ("folder", "Dateien", "Musik, Bilder & USB-Sticks", "files", False),
            ("wifi", "WLAN", "Netzwerk verbinden", "wifi", False),
            ("sound", "Lautstärke", "Boxen & Audioausgang", "sound", False),
            ("bluetooth", "Bluetooth", "Geräte verbinden", "bluetooth", False),
        ]
        self.tiles = {}
        for i, (symbol, title, subtitle, action, accent) in enumerate(specs):
            tile = Tile(symbol, title, subtitle, lambda checked=False, a=action: self.launch(a), accent)
            self.tiles[action] = tile
            grid.addWidget(tile, i // 3, i % 3)
        layout.addLayout(grid, 1)
        self.feedback = QLabel("Zurück geht’s jederzeit über „Startseite“ in der oberen Leiste.")
        self.feedback.setStyleSheet("color: #a6b5a7; font-size: 12px;")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        footer = QHBoxLayout()
        self.update_button = QPushButton("  Updates")
        self.update_button.setIcon(icon("update", "#edaa66", 22))
        self.update_button.clicked.connect(self.show_updates)
        footer.addWidget(self.update_button)
        footer.addStretch()
        for symbol, text, action in (("restart", "Neustart", "reboot"), ("power", "Ausschalten", "poweroff")):
            button = QPushButton(f"  {text}")
            button.setIcon(icon(symbol, "#c6cfc7", 20))
            button.clicked.connect(lambda checked=False, a=action: self.power(a))
            footer.addWidget(button)
        layout.addLayout(footer)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.tick)
        self.clock_timer.start(1000)
        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.refresh_network)
        self.net_timer.start(15000)
        self.net_process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        self.net_process.setProcessEnvironment(environment)
        self.net_process.finished.connect(self.network_result)
        self.net_process.errorOccurred.connect(lambda _: self.network.setText("Netzwerkstatus nicht verfügbar"))
        self.tick()
        self.refresh_network()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.background.render(painter, QRectF(self.rect()))
        painter.end()

    def resizeEvent(self, event):
        compact = self.height() < 650
        self.headline.setStyleSheet(
            f"font-size: {30 if compact else 42}px; font-weight: 800; letter-spacing: -1px;")
        self.layout().setContentsMargins(28 if self.width() < 1000 else 48, 20, 28 if self.width() < 1000 else 48, 18)
        super().resizeEvent(event)

    def tick(self):
        self.clock.setText(QDateTime.currentDateTime().toString("HH:mm"))

    def refresh_network(self):
        if self.preview:
            self.network.setText("●  Design-Vorschau")
        elif self.net_process.state() == QProcess.ProcessState.NotRunning:
            self.net_process.start("nmcli", ["-t", "-f", "STATE", "general"])
            QTimer.singleShot(5000, self.network_timeout)

    def network_timeout(self):
        if self.net_process.state() != QProcess.ProcessState.NotRunning:
            self.net_process.kill()
            self.network.setText("Netzwerkstatus nicht verfügbar")

    def network_result(self, code, status):
        value = bytes(self.net_process.readAllStandardOutput()).decode().strip()
        if code:
            self.network.setText("Netzwerkstatus nicht verfügbar")
        elif value == "connected":
            self.network.setText("●  Netzwerk verbunden")
        elif value in ("connected (local only)", "connected (site only)"):
            self.network.setText("●  Verbindung eingeschränkt")
        else:
            self.network.setText("○  Offline · WLAN öffnen")

    def command_for(self, action):
        if action == "spotify":
            if Path("/var/lib/flatpak/app/com.spotify.Client/current/active").exists():
                return ["flatpak", "run", "com.spotify.Client"]
            return ["firefox", "--new-window", "https://open.spotify.com"]
        return {
            "web": ["firefox", "--new-window", "https://start.duckduckgo.com"],
            "files": ["dolphin", str(Path.home())],
            "wifi": ["kcmshell6", "kcm_networkmanagement"],
            "sound": ["kcmshell6", "kcm_pulseaudio"],
            "bluetooth": ["kcmshell6", "kcm_bluetooth"],
        }[action]

    def launch(self, action):
        self.last_action = action
        if self.preview:
            self.feedback.setText(f"Vorschau: „{self.tiles[action].accessibleName()}“ gewählt. Es wird keine App gestartet.")
            return
        command = self.command_for(action)
        if not shutil.which(command[0]):
            self.feedback.setText("Diese Anwendung fehlt. Bitte die Vereinsadministration kontaktieren.")
            return
        process = QProcess(self)
        # GUI applications must not inherit cloud-init's or a terminal's session env.
        self.processes.append(process)
        process.errorOccurred.connect(lambda _: self.feedback.setText("Die Anwendung konnte nicht gestartet werden."))
        process.finished.connect(lambda code, status, p=process: self.app_finished(p, code, status))
        process.start(command[0], command[1:])
        self.feedback.setText("App wird geöffnet. Über „Startseite“ kommst du wieder hierher.")

    def app_finished(self, process, code, status):
        if code != 0:
            self.feedback.setText("Die App wurde mit einem Fehler beendet. Bitte erneut versuchen.")
        if process in self.processes:
            self.processes.remove(process)
        process.deleteLater()

    def show_updates(self):
        dialog = UpdateDialog(self, self.preview)
        dialog.exec()

    def power(self, action):
        if action not in ("reboot", "poweroff"):
            raise ValueError("Unsupported power action")
        title = "Neu starten?" if action == "reboot" else "Ausschalten?"
        body = "Die Musik wird beendet. Bitte offene Dateien vorher speichern."
        dialog = QMessageBox(QMessageBox.Icon.Question, title, body, parent=self)
        confirm = dialog.addButton("Neu starten" if action == "reboot" else "Ausschalten",
                                   QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() != confirm:
            return
        self.last_action = action
        if self.preview:
            self.feedback.setText(f"Vorschau: {title} bestätigt. Dieser Rechner bleibt unverändert.")
            return
        process = QProcess(self)
        self.processes.append(process)
        process.finished.connect(lambda code, status: self.feedback.setText(
            "Aktion läuft …" if code == 0 else "Aktion nicht möglich. Bitte laufende Updates prüfen."))
        process.errorOccurred.connect(lambda _: self.feedback.setText("Aktion konnte nicht ausgeführt werden."))
        process.start("systemctl", [action])

    def reveal(self):
        self.showMaximized()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.preview:
            event.accept()
        else:
            # A closed application should not strand a nontechnical user.
            event.ignore()


STYLE = """
QWidget { font-family: "Noto Sans", "DejaVu Sans"; color: #eef0e8; font-size: 14px; }
QLabel { background: transparent; }
QPushButton { background: #22332c; border: 1px solid #405148; border-radius: 12px;
              padding: 11px 18px; font-weight: 600; min-height: 24px; }
QPushButton:hover { background: #31463a; border-color: #ddaa70; }
QPushButton:focus { border: 2px solid #ffc78c; }
QPushButton:pressed { background: #435541; }
QPushButton:disabled { color: #718078; background: #1b2621; }
QPushButton#tile { background: rgba(28, 45, 36, 235); border: 1px solid #435346; border-radius: 18px; padding: 0; }
QPushButton#tile:hover { background: #314a39; border-color: #e9ac70; }
QPushButton#tile:focus { border: 2px solid #ffc78c; }
QPushButton#primaryTile { background: #b8d79a; border: 1px solid #d7ecb6; border-radius: 18px; padding: 0; }
QPushButton#primaryTile:hover { background: #cce9af; }
QPushButton#primaryTile:focus { border: 2px solid #ffffff; }
QLabel#tileTitle { font-size: 24px; font-weight: 750; }
QLabel#tileSubtitle { font-size: 12px; font-weight: 400; }
QDialog, QMessageBox { background: #18271f; }
QPlainTextEdit { background: #101b15; color: #caddc3; border: 1px solid #465b49;
                 border-radius: 8px; font-family: monospace; font-size: 12px; padding: 8px; }
QPushButton#confirm { background: #b8d79a; color: #17261c; }
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Disable all system actions")
    parser.add_argument("--screenshot", type=Path, help="Save a preview render and exit")
    parser.add_argument("--size", default="1280x800")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("saar-home")
    app.setDesktopFileName("de.saarfighters.Home")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setWindowIcon(icon("home"))
    server = None
    if not (args.preview or args.screenshot):
        socket = QLocalSocket()
        socket.connectToServer(SOCKET)
        if socket.waitForConnected(600):
            socket.write(b"show")
            socket.waitForBytesWritten(600)
            return 0
        QLocalServer.removeServer(SOCKET)
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(SOCKET):
            raise SystemExit("Could not create user-local launcher socket")
    window = Home(args.preview or bool(args.screenshot))
    if server:
        def reveal():
            peer = server.nextPendingConnection()
            window.reveal()
            peer.disconnectFromServer()
            peer.deleteLater()
        server.newConnection.connect(reveal)
    if args.preview or args.screenshot:
        width, height = map(int, args.size.split("x"))
        window.resize(width, height)
        window.show()
    else:
        window.showMaximized()
    if args.screenshot:
        def capture():
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.screenshot)):
                raise RuntimeError("Could not save screenshot")
            app.quit()
        QTimer.singleShot(600, capture)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
