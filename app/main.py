#!/usr/bin/env python3
"""Saar-Fighters Home: a small native launcher, no browser runtime."""
import argparse
import os
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QProcess, QTranslator, Qt, QTimer, QSize, QRectF
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)
from devices import AudioSheet, BluetoothSheet, DeviceClient, WifiSheet, label
from hardware import status_labels

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
SOCKET = f"saar-home-{os.getuid()}"
CLUB_WEBSITE = "https://www.saarfighters-as.de/"

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
    "battery": '<rect x="2" y="6" width="18" height="12" rx="2"/><path d="M23 10v4M6 9v6M10 9v6M14 9v6"/>',
    "charger": '<path d="M8 2v5m8-5v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5"/>',
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
        self.setMinimumSize(170, 104)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
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
        sub.setWordWrap(True)
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
        layout.setSpacing(10)
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(ASSETS / "club-logo.gif")).scaled(
            56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAccessibleName("Original-Logo der Saar-Fighters AS")
        header.addWidget(logo)
        brand = QLabel("SAAR-FIGHTERS\nAS e.V.")
        brand.setStyleSheet("font-size: 14px; font-weight: 800; letter-spacing: 2px; color: #edaa66;")
        header.addWidget(brand)
        header.addStretch()
        self.website_button = QPushButton("Vereinswebseite  ↗")
        self.website_button.setAccessibleName("Vereinswebseite öffnen")
        self.website_button.clicked.connect(lambda: self.launch("club"))
        header.addWidget(self.website_button)
        layout.addLayout(header)

        self.device_client = DeviceClient(self, preview)
        self.status_values = []
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        for title, symbol in (("Netzwerk", "wifi"), ("Bluetooth", "bluetooth"),
                              ("Netzteil", "charger"), ("Akku", "battery")):
            frame = QFrame()
            frame.setObjectName("statusChip")
            box = QVBoxLayout(frame)
            box.setContentsMargins(12, 7, 12, 7)
            box.setSpacing(2)
            box.addWidget(label(title, "font-size: 10px; color: #a6b5a7;"))
            value = label("Wird geprüft …", "font-size: 12px; font-weight: 600;")
            value.setMinimumWidth(0)
            box.addWidget(value)
            status_row.addWidget(frame, 1)
            self.status_values.append(value)
        layout.addLayout(status_row)
        self.network = self.status_values[0]
        self.device_client.status_changed.connect(self.update_status)
        QTimer.singleShot(800, self.device_client.refresh_status)

        if preview:
            layout.addWidget(label("Vorschau · Statusanzeigen mit Beispieldaten",
                                   "font-size: 15px; color: #b8c3b9;"))

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
        self.feedback = QLabel()
        self.feedback.hide()
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

    def paintEvent(self, event):
        painter = QPainter(self)
        self.background.render(painter, QRectF(self.rect()))
        painter.end()

    def resizeEvent(self, event):
        self.layout().setContentsMargins(24 if self.width() < 1000 else 40, 12, 24 if self.width() < 1000 else 40, 14)
        super().resizeEvent(event)

    def update_status(self, status):
        values = status_labels(status)
        for widget, text, prefix in zip(self.status_values, values, ("", "Bluetooth", "Netzteil", "Akku")):
            widget.setText(text.removeprefix(prefix).lstrip(": ") if prefix else text)
        network = status.get("network", {})
        connectivity = {0: "Internetstatus nicht geprüft", 1: "Kein Internet",
                        2: "Anmeldung im Browser erforderlich", 3: "Internet eingeschränkt",
                        4: "Internet erreichbar"}.get(network.get("connectivity", 0), "")
        self.network.setToolTip(network.get("name", "") + "\n" + connectivity)
        names = [d["name"] for d in status.get("bluetooth", {}).get("devices", []) if d.get("connected")]
        self.status_values[1].setToolTip("\n".join(names))

    def command_for(self, action):
        if action == "spotify":
            if Path("/var/lib/flatpak/app/com.spotify.Client/current/active").exists():
                return ["flatpak", "run", "com.spotify.Client"]
            return ["firefox", "--new-window", "https://open.spotify.com"]
        return {
            "web": ["firefox", "--new-window", "https://start.duckduckgo.com"],
            "files": ["dolphin", str(Path.home())],
            "club": ["firefox", "--new-window", CLUB_WEBSITE],
        }[action]

    def launch(self, action):
        self.last_action = action
        if action in ("wifi", "bluetooth", "sound"):
            self.open_device(action)
            return
        if self.preview:
            title = "Vereinswebseite" if action == "club" else self.tiles[action].accessibleName()
            self.set_feedback(f"Vorschau: „{title}“ gewählt. Es wird keine App gestartet.")
            return
        command = self.command_for(action)
        if not shutil.which(command[0]):
            self.set_feedback("Diese Anwendung fehlt. Bitte die Vereinsadministration kontaktieren.")
            return
        process = QProcess(self)
        # GUI applications must not inherit cloud-init's or a terminal's session env.
        self.processes.append(process)
        process.errorOccurred.connect(lambda _: self.set_feedback("Die Anwendung konnte nicht gestartet werden."))
        process.finished.connect(lambda code, status, p=process: self.app_finished(p, code, status))
        process.start(command[0], command[1:])
        self.set_feedback("")

    def set_feedback(self, text):
        self.feedback.setText(text)
        self.feedback.setVisible(bool(text))

    def open_device(self, action):
        sheet = {"wifi": WifiSheet, "bluetooth": BluetoothSheet, "sound": AudioSheet}[action](
            self, self.device_client)
        sheet.exec()
        sheet.deleteLater()

    def app_finished(self, process, code, status):
        if code != 0:
            self.set_feedback("Die App wurde mit einem Fehler beendet. Bitte erneut versuchen.")
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
            self.set_feedback(f"Vorschau: {title} bestätigt. Dieser Rechner bleibt unverändert.")
            return
        process = QProcess(self)
        self.processes.append(process)
        process.finished.connect(lambda code, status: self.set_feedback(
            "Aktion läuft …" if code == 0 else "Aktion nicht möglich. Bitte laufende Updates prüfen."))
        process.errorOccurred.connect(lambda _: self.set_feedback("Aktion konnte nicht ausgeführt werden."))
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
QDialog#deviceSheet { background: #18271f; border: 1px solid #64745b; border-radius: 18px; }
QFrame#statusChip { background: rgba(28, 45, 36, 220); border: 1px solid #435346; border-radius: 10px; }
QListWidget { background: #111f18; border: 1px solid #435346; border-radius: 12px; padding: 6px; outline: none; }
QListWidget::item { padding: 8px 14px; border-radius: 9px; color: #e3e9dc; }
QListWidget::item:selected { background: #354d38; color: #f1f5e9; border: 1px solid #b8d79a; }
QLineEdit { background: #101d16; border: 1px solid #63765c; border-radius: 9px; padding: 12px; }
QLineEdit:focus { border-color: #edaa66; }
QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: #35483a; }
QSlider::sub-page:horizontal { background: #b8d79a; border-radius: 4px; }
QSlider::handle:horizontal { width: 26px; margin: -10px 0; border-radius: 12px; background: #edaa66; }
QPlainTextEdit { background: #101b15; color: #caddc3; border: 1px solid #465b49;
                 border-radius: 8px; font-family: monospace; font-size: 12px; padding: 8px; }
QPushButton#confirm { background: #b8d79a; color: #17261c; }
QPushButton#confirm:disabled { background: #28372d; color: #7e8c81; border-color: #3c4d40; }
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Disable all system actions")
    parser.add_argument("--screenshot", type=Path, help="Save a preview render and exit")
    parser.add_argument("--size", default="1280x800")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    QLocale.setDefault(QLocale("de_DE"))
    translator = QTranslator()
    if translator.load("qtbase_de", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
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
    app.aboutToQuit.connect(window.device_client.stop)
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
        QTimer.singleShot(1100, capture)
    result = app.exec()
    window.device_client.stop()
    # Dispose the widget tree while QApplication and Python callbacks are alive.
    import shiboken6
    shiboken6.delete(window)
    app.removeTranslator(translator)
    return result


if __name__ == "__main__":
    sys.exit(main())
