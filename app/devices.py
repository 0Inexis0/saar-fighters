"""Shared native device screens; all visible copy is German."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QProcess, Qt, QTimer, Signal, QSize, QRectF
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                              QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget, QPlainTextEdit, QFileDialog, QCheckBox, QButtonGroup, QRadioButton)

from PySide6.QtGui import QColor, QPainter, QPen
from hardware import wifi_password_valid
from music_player import PlayerSlider

EXAMPLE_STATUS = {
    "network": {"state": 70, "name": "Vereinsheim", "type": "802-11-wireless"},
    "bluetooth": {"available": True, "powered": True,
                  "devices": [{"name": "Vereinsboxen", "connected": True}]},
    "power": {"percentage": 78, "state": 1, "plugged": True},
}


def label(text="", style=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if style:
        widget.setStyleSheet(style)
    return widget


class NoticeLabel(QLabel):
    """Reserve space only while an actionable message is present."""
    def __init__(self, text=""):
        super().__init__()
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(text)

    def setText(self, text):
        super().setText(text)
        self.setVisible(bool(text))

    def clear(self):
        self.setText("")


class SettingsOption(QRadioButton):
    """A whole-row native radio control with a trailing selection mark."""
    def __init__(self, title, description):
        super().__init__(title)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        content = QVBoxLayout(self)
        content.setContentsMargins(16, 14, 42, 14)
        content.setSpacing(5)
        heading = label(title, "font-size: 14px; font-weight: 600;")
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        content.addWidget(heading)
        if description:
            detail = label(description, "font-size: 12px; color: #b5bcac;")
            detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            content.addWidget(detail)
        self.setMinimumHeight(48 if not description else 76)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.35)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#353e2d" if self.isChecked() else "#2c3127"))
        painter.drawRoundedRect(QRectF(self.rect()), 8, 8)
        if self.isChecked():
            painter.setPen(QPen(QColor("#c1d69e"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            x, y = self.width() - 26, self.height() // 2
            painter.drawLine(x - 5, y, x - 1, y + 4)
            painter.drawLine(x - 1, y + 4, x + 7, y - 5)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#c1d69e"), 1))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)


class SettingsChoice(QWidget):
    """Visible, keyboard-accessible exclusive choices for short settings lists."""
    currentIndexChanged = Signal(int)

    def __init__(self, choices, *, compact=False):
        super().__init__()
        self.choices = choices
        self.group = QButtonGroup(self)
        layout = QHBoxLayout(self) if compact else QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if compact else 1)
        for index, (title, key, description) in enumerate(choices):
            button = SettingsOption(title, description)
            self.group.addButton(button, index)
            layout.addWidget(button)
        self.group.button(0).setChecked(True)
        self.group.idToggled.connect(lambda index, checked: self.currentIndexChanged.emit(index) if checked else None)

    def currentIndex(self):
        return self.group.checkedId()

    def setCurrentIndex(self, index):
        button = self.group.button(index)
        if button:
            button.setChecked(True)

    def findData(self, key):
        return next((i for i, choice in enumerate(self.choices) if choice[1] == key), -1)

    def currentData(self):
        return self.choices[self.currentIndex()][1] if self.currentIndex() >= 0 else None

    def currentText(self):
        return self.choices[self.currentIndex()][0] if self.currentIndex() >= 0 else ""


class RemoteToggle(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setFixedSize(52, 32)
        self.setAccessibleName("Fernwartung im lokalen Netz")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b7bd87" if self.isChecked() else "#55594a"))
        painter.drawRoundedRect(QRectF(2, 4, 48, 24), 12, 12)
        painter.setBrush(QColor("#25281f" if self.isChecked() else "#eeece1"))
        painter.drawEllipse(QRectF(28 if self.isChecked() else 6, 8, 16, 16))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#eeece1"), 1))
            painter.drawRoundedRect(QRectF(0.5, 2, 51, 28), 14, 14)


class DeviceClient(QObject):
    status_changed = Signal(dict)
    pairing = Signal(dict)

    def __init__(self, parent=None, preview=False):
        super().__init__(parent)
        self.preview = preview
        self.preview_brightness = 70
        self.preview_audio_ids = ["1"]
        self.preview_audio_volume = 55
        self.preview_audio_muted = False
        self.preview_output_volumes = {}
        self.preview_auto_audio = True
        self.sequence = 0
        self.pending = {}
        self.buffer = b""
        self.stopping = False
        self.status_pending = False
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.errorOccurred.connect(lambda _: self.lost())
        self.process.finished.connect(lambda *_: self.lost())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(8000)
        if not preview:
            self.start()

    def start(self):
        if not self.stopping and self.process.state() == QProcess.ProcessState.NotRunning:
            self.buffer = b""
            self.process.start(sys.executable, ["-u", str(Path(__file__).with_name("backend.py"))])

    def request(self, operation, args=None, callback=None):
        if self.preview:
            QTimer.singleShot(0, self, lambda: self.preview_reply(operation, callback, args))
            return
        if self.process.state() != QProcess.ProcessState.Running:
            if callback:
                QTimer.singleShot(0, lambda: callback(None, "Geräteverbindung wird gestartet. Bitte gleich erneut versuchen."))
            return
        self.sequence += 1
        self.pending[self.sequence] = callback
        self.process.write((json.dumps({"id": self.sequence, "op": operation, "args": args or {}}) + "\n").encode())

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                result = json.loads(line)
            except ValueError:
                continue
            if "event" in result:
                self.pairing.emit(result)
            else:
                callback = self.pending.pop(result.get("id"), None)
                if callback:
                    callback(result.get("result"), result.get("error"))

    def refresh_status(self):
        if self.status_pending:
            return
        self.status_pending = True
        self.request("status", callback=self.got_status)

    def got_status(self, data, error):
        self.status_pending = False
        self.status_changed.emit(data if not error else {
            "network": {"error": True}, "bluetooth": {"error": True}, "power": {"error": True}})

    def lost(self):
        pending, self.pending = self.pending, {}
        for callback in pending.values():
            if callback:
                callback(None, "Geräteverbindung unterbrochen. Bitte erneut versuchen.")
        self.status_pending = False
        self.status_changed.emit({key: {"error": True} for key in ("network", "bluetooth", "power")})
        self.pairing.emit({"event": "pairing_closed"})
        if not self.stopping:
            QTimer.singleShot(5000, self.start)

    def stop(self):
        self.stopping = True
        self.timer.stop()
        if not self.preview:
            self.process.closeWriteChannel()
            if not self.process.waitForFinished(1000):
                self.process.kill()
                self.process.waitForFinished(1000)

    def preview_reply(self, operation, callback, args=None):
        if self.stopping:
            return
        args = args or {}
        if operation.startswith("audio"):
            if operation == "audio_autoswitch":
                self.preview_auto_audio = args["enabled"]
            elif operation == "audio_output_volume":
                self.preview_output_volumes[args["name"]] = args["value"]
            elif operation == "audio_outputs":
                self.preview_audio_ids = args["ids"]
            elif operation == "audio_output":
                self.preview_audio_ids = [args["id"]]
            elif operation == "audio_volume":
                self.preview_audio_volume = args["value"]
            elif operation == "audio_mute":
                self.preview_audio_muted = args["muted"]
            elif operation == "audio_toggle":
                self.preview_audio_muted = not self.preview_audio_muted
            outputs = [{"id": key, "name": "example" + key, "description": name,
                        "selected": key in self.preview_audio_ids,
                        "default": self.preview_audio_ids == [key],
                        "mute": self.preview_audio_muted, "volume": self.preview_output_volumes.get("example" + key, self.preview_audio_volume)}
                       for key, name in (("1", "Vereinsboxen"), ("2", "HDMI / Bildschirm"),
                                         ("3", "USB-Lautsprecher"))]
            control = {"volume": self.preview_audio_volume, "mute": self.preview_audio_muted}
            if callback:
                callback({"outputs": outputs, "control": control, "auto_bluetooth": self.preview_auto_audio,
                          "message": "Vorschau: Auswahl übernommen."}, None)
            return
        if operation == "brightness_set":
            self.preview_brightness = args["value"]
        if operation in ("brightness", "brightness_set"):
            if callback:
                callback({"displays": [{"id": "preview", "name": "Laptop-Bildschirm",
                                       "value": self.preview_brightness, "internal": True}]}, None)
            return
        data = {
            "media_status": {"available": True, "playing": True,
                             "player": "org.mpris.MediaPlayer2.spotify", "player_name": "Spotify",
                             "playback_status": "Playing", "title": "Euer nächster Lieblingssong",
                             "artist": "Beispielinterpret", "can_previous": True, "can_next": True},
            "status": EXAMPLE_STATUS,
            "wifi": {"available": True, "enabled": True, "hardware_enabled": True, "networks": [
                {"path": "/example/1", "name": "Vereinsheim", "strength": 91, "mode": "wpa-psk", "connected": True, "saved": "yes"},
                {"path": "/example/2", "name": "Gastnetz", "strength": 63, "mode": "wpa-psk", "connected": False, "saved": ""},
            ]},
            "bluetooth": {"available": True, "powered": True, "devices": [
                {"path": "/example/box", "name": "Vereinsboxen", "connected": True, "paired": True},
                {"path": "/example/new", "name": "Neuer Lautsprecher", "connected": False, "paired": False},
            ]},
        }.get(operation, {"message": "Vorschau: Es wurde keine Einstellung verändert."})
        if callback:
            callback(data, None)


class Sheet(QDialog):
    def __init__(self, parent, client, title, description):
        super().__init__(parent)
        self.client = client
        self.busy = False
        self.closed = False
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(min(parent.width() - 32, 820), min(parent.height() - 24, 610))
        self.setObjectName("deviceSheet")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(28, 22, 28, 22)
        self.body.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(label(title, "font-size: 28px; font-weight: 750;"), 1)
        self.back = QPushButton("Zurück")
        self.back.clicked.connect(self.reject)
        header.addWidget(self.back)
        self.body.addLayout(header)
        if description:
            self.body.addWidget(label(description, "color: #b9b8a7;"))
        self.message = NoticeLabel()
        self.body.addWidget(self.message)
        self.controls = []
        self.finished.connect(lambda _: setattr(self, "closed", True))

    def working(self, busy, message=""):
        self.busy = busy
        self.back.setEnabled(not busy)
        for control in self.controls:
            control.setEnabled(not busy)
        if message or not busy:
            self.message.setText(message)

    def request(self, operation, args=None, callback=None):
        def reply(data, error):
            if not self.closed and callback:
                callback(data, error)
        self.client.request(operation, args, reply if callback else None)

    def action(self, operation, args=None, finished=None):
        self.working(True, "Einen Moment …")
        def done(data, error):
            self.working(False)
            self.message.setText(error or "")
            self.client.refresh_status()
            if finished:
                finished()
        self.request(operation, args, done)

    def reject(self):
        if not self.busy:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)


class WifiSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "WLAN", "Mit einem WLAN verbinden.")
        row = QHBoxLayout()
        self.toggle = RemoteToggle()
        self.toggle.setAccessibleName("WLAN")
        row.addWidget(label("WLAN"))
        self.scan = QPushButton("Netze suchen")
        row.addWidget(self.toggle)
        row.addWidget(self.scan)
        self.body.addLayout(row)
        self.list = QListWidget()
        self.list.setAccessibleName("Verfügbare WLAN-Netze")
        self.body.addWidget(self.list, 1)
        self.password = QLineEdit()
        self.password.setPlaceholderText("WLAN-Passwort")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("WLAN-Passwort")
        self.body.addWidget(self.password)
        self.connect = QPushButton("Verbinden")
        self.connect.setObjectName("confirm")
        self.body.addWidget(self.connect)
        self.controls = [self.toggle, self.scan, self.list, self.password, self.connect]
        self.info = {}
        self.toggle.clicked.connect(lambda: self.action(
            "wifi_power", {"enabled": not self.info.get("enabled")}, lambda: self.load(True)))
        self.scan.clicked.connect(lambda: self.load(True))
        self.list.currentItemChanged.connect(self.selection)
        self.connect.clicked.connect(self.connect_selected)
        self.password.returnPressed.connect(self.connect_selected)
        self.load()

    def load(self, scan=False):
        self.working(True, "Suche nach WLAN-Netzen …" if scan else "WLAN wird gelesen …")
        self.request("wifi", {"scan": scan}, self.loaded)

    def loaded(self, data, error):
        self.working(False)
        self.list.clear()
        self.info = data or {}
        self.toggle.setChecked(bool(self.info.get("enabled")))
        self.toggle.setEnabled(bool(self.info.get("available")) and not error)
        self.scan.setEnabled(bool(self.info.get("available") and self.info.get("enabled")))
        if error:
            self.message.setText(error)
        elif not data["available"]:
            self.message.setText("Kein WLAN-Adapter erkannt. Ein Netzwerkkabel kann trotzdem verbunden sein.")
        elif not data["hardware_enabled"]:
            self.message.setText("WLAN ist am Gerät gesperrt. Bitte Flugmodus oder WLAN-Schalter prüfen.")
        elif not data["enabled"]:
            self.message.clear()
        else:
            self.message.setText("" if data["networks"] else "Keine Netze gefunden.")
            for network in data["networks"]:
                security = {"open": "Offen", "owe": "Verschlüsselt, ohne Passwort",
                            "wpa-psk": "Mit Passwort", "sae": "Mit Passwort",
                            "enterprise": "Besondere Anmeldung", "unsupported": "Besondere Einrichtung"}[network["mode"]]
                suffix = "Verbunden" if network["connected"] else f'{network["strength"]} % Empfang · {security}'
                if network["saved"] and not network["connected"]:
                    suffix += " · gespeichert"
                item = QListWidgetItem(f'{network["name"]}\n{suffix}')
                item.setSizeHint(QSize(0, 64))
                item.setData(Qt.ItemDataRole.UserRole, network)
                self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.selection()

    def selection(self, *_):
        item = self.list.currentItem()
        network = item.data(Qt.ItemDataRole.UserRole) if item else {}
        self.password.clear()
        self.password.setVisible(network.get("mode") in ("wpa-psk", "sae") and not network.get("connected"))
        self.password.setPlaceholderText("Gespeichertes Passwort verwenden oder neues eingeben" if network.get("saved") else "WLAN-Passwort")
        self.connect.setText("Verbindung trennen" if network.get("connected") else "Verbinden")
        self.connect.setEnabled(bool(network) and network.get("mode") not in ("enterprise", "unsupported"))
        if network.get("mode") in ("enterprise", "unsupported"):
            self.message.setText("Dieses WLAN benötigt eine besondere Einrichtung durch die Vereinsadministration.")

    def connect_selected(self):
        item = self.list.currentItem()
        if not item or self.busy:
            return
        network = item.data(Qt.ItemDataRole.UserRole)
        if network["connected"]:
            self.action("wifi_disconnect", finished=self.load)
            return
        password = self.password.text()
        if not (network["saved"] and not password) and not wifi_password_valid(network["mode"], password):
            self.message.setText("Bitte ein gültiges WLAN-Passwort eingeben (bei WPA2 mindestens 8 Zeichen).")
            return
        self.password.clear()
        self.working(True, "Verbinde mit dem WLAN …")
        def connected(data, error):
            self.working(False)
            self.message.setText(error or "")
            self.client.refresh_status()
            if not error:
                self.load()
        self.request("wifi_connect", {"path": network["path"], "password": password}, connected)


class BluetoothSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Bluetooth", "Lautsprecher und andere Geräte verbinden.")
        row = QHBoxLayout()
        self.toggle = RemoteToggle()
        self.toggle.setAccessibleName("Bluetooth")
        row.addWidget(label("Bluetooth"))
        self.scan = QPushButton("Geräte suchen")
        row.addWidget(self.toggle)
        row.addWidget(self.scan)
        self.body.addLayout(row)
        self.list = QListWidget()
        self.list.setAccessibleName("Bluetooth-Geräte")
        self.body.addWidget(self.list, 1)
        self.connect = QPushButton("Verbinden")
        self.connect.setObjectName("confirm")
        self.body.addWidget(self.connect)
        self.controls = [self.toggle, self.scan, self.list, self.connect]
        self.info = {}
        self.question = None
        self.searching = False
        self.cleaned = False
        self.client.pairing.connect(self.pairing_event)
        self.list.currentItemChanged.connect(self.selection)
        self.toggle.clicked.connect(lambda: self.action(
            "bt_power", {"enabled": not self.info.get("powered")}, self.load))
        self.scan.clicked.connect(self.search)
        self.connect.clicked.connect(self.connect_selected)
        self.timer = QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(lambda: self.load(quiet=True) if not self.busy else None)
        self.timer.start()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.stop_search)
        self.finished.connect(self.cleanup)
        self.load()

    def load(self, quiet=False):
        if self.closed:
            return
        self.request("bluetooth", callback=lambda data, error: self.loaded(data, error, quiet))

    def loaded(self, data, error, quiet=False):
        if self.closed or self.busy:
            return
        old = self.list.currentItem()
        selected = old.data(Qt.ItemDataRole.UserRole)["path"] if old else None
        self.list.clear()
        self.info = data or {}
        available, powered = self.info.get("available"), self.info.get("powered")
        self.toggle.setEnabled(bool(available))
        self.toggle.setChecked(bool(powered))
        self.scan.setEnabled(bool(available and powered))
        self.scan.setText("Suche beenden" if self.searching else "Geräte suchen")
        if not quiet:
            self.message.setText(error or ("Kein Bluetooth-Adapter erkannt." if not available else
                "" if not powered or self.info.get("devices") else "Keine Geräte gefunden."))
        for device in self.info.get("devices", []):
            state = "Verbunden" if device["connected"] else "Bereits gekoppelt" if device["paired"] else "Neues Gerät"
            item = QListWidgetItem(f'{device["name"]}\n{state}')
            item.setData(Qt.ItemDataRole.UserRole, device)
            item.setSizeHint(QSize(0, 64))
            self.list.addItem(item)
            if device["path"] == selected:
                self.list.setCurrentItem(item)
        if not self.list.currentItem() and self.list.count():
            self.list.setCurrentRow(0)
        self.selection()

    def selection(self, *_):
        item = self.list.currentItem()
        device = item.data(Qt.ItemDataRole.UserRole) if item else {}
        self.connect.setText("Verbindung trennen" if device.get("connected") else
                             "Verbinden" if device.get("paired") else "Koppeln und verbinden")
        self.connect.setEnabled(bool(device and self.info.get("powered")) and not self.busy)

    def search(self):
        if self.busy:
            return
        self.working(True, "Suche wird umgestellt …")
        enabled = not self.searching
        def done(data, error):
            self.working(False)
            self.searching = enabled if not error else False
            self.message.setText(error or ("Suche läuft … Bitte das Gerät in den Kopplungsmodus versetzen."
                                          if enabled else "Suche beendet."))
            if self.searching:
                self.search_timer.start(30000)
            else:
                self.search_timer.stop()
            self.load(quiet=True)
        self.request("bt_scan", {"enabled": enabled}, done)

    def stop_search(self):
        if self.searching:
            self.searching = False
            self.search_timer.stop()
            self.request("bt_scan", {"enabled": False})
            self.scan.setText("Geräte suchen")
            if not self.closed and not self.busy:
                self.message.clear()

    def connect_selected(self):
        item = self.list.currentItem()
        if not item or self.busy:
            return
        device = item.data(Qt.ItemDataRole.UserRole)
        self.action("bt_disconnect" if device["connected"] else "bt_connect",
                    {"path": device["path"]}, lambda: self.load(quiet=True))
        self.message.setText("Verbindung wird getrennt …" if device["connected"] else
                             "Verbinde … Bitte auf eine Kopplungsabfrage achten.")

    def pairing_event(self, event):
        if self.closed:
            return
        if event["event"] == "pairing_closed":
            if self.question:
                self.question.reject()
            return
        kind = event["kind"]
        if self.question:
            self.question.reject()
        question = QDialog(self)
        self.question = question
        question.setWindowTitle("Bluetooth koppeln")
        question.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        layout = QVBoxLayout(question)
        layout.setContentsMargins(28, 24, 28, 24)
        text = {"confirm": "Stimmt dieser Code auf beiden Geräten überein?",
                "pin": "Bitte den PIN-Code des Geräts eingeben.",
                "passkey": "Bitte den sechsstelligen Code eingeben.",
                "authorize": "Die Kopplung mit diesem Gerät erlauben?",
                "display": "Diesen Code am anderen Gerät eingeben und dort bestätigen."}[kind]
        layout.addWidget(label(text, "font-size: 18px;"))
        if event.get("code"):
            layout.addWidget(label(event["code"], "font-size: 34px; font-weight: 700; color: #c3b48b;"))
        entry = QLineEdit()
        entry.setAccessibleName("Bluetooth-Kopplungscode")
        entry.setMaxLength(6 if kind == "passkey" else 16)
        if kind in ("pin", "passkey"):
            layout.addWidget(entry)
        buttons = QHBoxLayout()
        cancel = QPushButton("Abbrechen" if kind != "display" else "Verstanden")
        cancel.clicked.connect(question.reject)
        buttons.addWidget(cancel)
        if kind != "display":
            accept = QPushButton("Bestätigen")
            accept.setObjectName("confirm")
            accept.clicked.connect(question.accept)
            buttons.addWidget(accept)
        layout.addLayout(buttons)
        def answer(result):
            if event.get("token"):
                self.request("pairing_reply", {"token": event["token"],
                    "accepted": result == QDialog.DialogCode.Accepted, "value": entry.text()})
            entry.clear()
            if self.question == question:
                self.question = None
            question.deleteLater()
        question.finished.connect(answer)
        question.open()

    def cleanup(self, *_):
        if self.cleaned:
            return
        self.cleaned = True
        self.stop_search()
        self.timer.stop()
        self.search_timer.stop()
        self.client.pairing.disconnect(self.pairing_event)


class BrightnessSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Bildschirmhelligkeit",
                         "Helligkeit und Anzeige anpassen.")
        self.list = QListWidget()
        self.list.setAccessibleName("Bildschirme mit Helligkeitssteuerung")
        self.body.addWidget(self.list, 1)
        self.level = label("Helligkeit", "font-size: 22px; font-weight: 700;")
        self.body.addWidget(self.level)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setAccessibleName("Bildschirmhelligkeit in Prozent")
        self.body.addWidget(self.slider)
        ends = QHBoxLayout()
        ends.addWidget(label("Dunkler"))
        ends.addStretch()
        ends.addWidget(label("Heller"))
        self.body.addLayout(ends)
        self.reload = QPushButton("Erneut laden")
        self.reload.clicked.connect(self.load)
        self.body.addWidget(self.reload)
        self.controls = [self.list, self.slider, self.reload]
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.apply)
        self.finished.connect(self.timer.stop)
        self.list.currentItemChanged.connect(self.selected)
        self.slider.valueChanged.connect(self.changed)
        self.slider.sliderReleased.connect(self.apply)
        self.load()

    def load(self):
        if self.busy:
            return
        self.working(True, "Bildschirme werden geladen …")
        self.request("brightness", callback=self.loaded)

    def loaded(self, data, error):
        selected = self.list.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole)["id"] if selected else None
        self.working(False)
        self.list.clear()
        screens = (data or {}).get("displays", []) if not error else []
        for screen in screens:
            item = QListWidgetItem(screen["name"])
            item.setData(Qt.ItemDataRole.UserRole, screen)
            item.setSizeHint(QSize(0, 64))
            self.list.addItem(item)
            if screen["id"] == selected_id:
                self.list.setCurrentItem(item)
        if screens and not self.list.currentItem():
            self.list.setCurrentRow(0)
        self.list.setEnabled(bool(screens))
        self.slider.setEnabled(bool(screens))
        self.message.setText(error or ("" if screens else
            "Kein steuerbarer Bildschirm erkannt. Bitte die Helligkeit direkt am Monitor einstellen."))

    def selected(self, *_):
        self.timer.stop()
        item = self.list.currentItem()
        self.slider.blockSignals(True)
        self.slider.setValue(item.data(Qt.ItemDataRole.UserRole)["value"] if item else 0)
        self.slider.blockSignals(False)
        self.level.setText(f"Helligkeit: {self.slider.value()} %" if item else "Helligkeit nicht verfügbar")

    def changed(self, value):
        self.level.setText(f"Helligkeit: {value} %")
        # Keep the selected screen fixed until the pending change is applied.
        self.list.setEnabled(False)
        self.reload.setEnabled(False)
        self.back.setEnabled(False)
        self.timer.start()

    def apply(self):
        if self.busy or self.closed or self.slider.isSliderDown():
            return
        self.timer.stop()
        item = self.list.currentItem()
        if not item:
            return
        self.working(True, "Helligkeit wird übernommen …")
        self.request("brightness_set", {"id": item.data(Qt.ItemDataRole.UserRole)["id"],
                                        "value": self.slider.value()}, self.loaded)

    def reject(self):
        if self.timer.isActive() or self.slider.isSliderDown():
            return
        super().reject()

    def closeEvent(self, event):
        if self.timer.isActive() or self.slider.isSliderDown():
            event.ignore()
        else:
            super().closeEvent(event)


class AudioOutputList(QListWidget):
    def keyPressEvent(self, event):
        item = self.currentItem()
        if item and event.key() == Qt.Key.Key_Space:
            item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
            event.accept()
        else:
            super().keyPressEvent(event)


class AudioSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Ton & Lautsprecher",
                         "Lautstärke und Wiedergabegeräte auswählen.")
        self.list = AudioOutputList()
        self.list.setAccessibleName("Audioausgänge für gleichzeitige Wiedergabe")
        self.list.setMinimumHeight(210)
        auto_row = QHBoxLayout()
        auto_row.addWidget(label("Bei neuer Bluetooth-Audioverbindung automatisch wechseln"), 1)
        self.auto_audio = RemoteToggle()
        self.auto_audio.setAccessibleName("Bluetooth-Audio automatisch umschalten")
        auto_row.addWidget(self.auto_audio)
        self.body.addLayout(auto_row)
        self.auto_audio.clicked.connect(lambda checked: self.change("audio_autoswitch", {"enabled": checked}, preserve=True))
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setStyleSheet("QListWidget::indicator { width: 0px; height: 0px; }")
        self.body.addWidget(self.list, 1)
        self.level = label("Gemeinsame Lautstärke", "font-size: 22px; font-weight: 700;")
        self.body.addWidget(self.level)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setAccessibleName("Gemeinsame Lautstärke in Prozent")
        self.body.addWidget(self.slider)
        row = QHBoxLayout()
        self.mute = RemoteToggle()
        self.mute.setAccessibleName("Ton eingeschaltet")
        row.addWidget(label("Ton"))
        self.reload = QPushButton("Laden")
        self.choose = QPushButton("Übernehmen")
        self.choose.setObjectName("confirm")
        row.addWidget(self.mute)
        row.addWidget(self.reload)
        row.addWidget(self.choose)
        self.body.addLayout(row)
        self.controls = [self.slider, self.mute, self.choose, self.list, self.reload, self.auto_audio]
        self.muted = False
        self.has_control = False
        self.output_sliders = []
        self.volume_timer = QTimer(self)
        self.volume_timer.setSingleShot(True)
        self.volume_timer.setInterval(350)
        self.finished.connect(self.volume_timer.stop)
        self.volume_timer.timeout.connect(self.apply_volume)
        self.slider.valueChanged.connect(self.volume_changed)
        self.slider.sliderReleased.connect(self.apply_volume)
        self.mute.clicked.connect(lambda: self.change("audio_mute", {"muted": not self.muted}, preserve=True))
        self.choose.clicked.connect(self.select_output)
        self.reload.clicked.connect(self.load)
        self.list.itemChanged.connect(self.update_controls)
        self.load()

    def load(self):
        if self.busy or self.volume_timer.isActive():
            return
        self.working(True, "Audioausgänge werden geladen …")
        self.request("audio", callback=self.loaded)

    def checked_ids(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)["id"]
                for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def update_controls(self, *_):
        for index in range(self.list.count()):
            item = self.list.item(index)
            widget = self.list.itemWidget(item)
            if widget:
                check = widget.findChild(QCheckBox)
                check.blockSignals(True)
                check.setChecked(item.checkState() == Qt.CheckState.Checked)
                check.blockSignals(False)
        output_pending = any(s.delay.isActive() or s.isSliderDown() for s in self.output_sliders)
        pending = self.busy or self.volume_timer.isActive() or self.slider.isSliderDown() or output_pending
        self.list.setEnabled(not self.busy and not self.volume_timer.isActive() and self.list.count() > 0)
        self.choose.setEnabled(not pending and bool(self.checked_ids()))
        self.reload.setEnabled(not pending)
        self.mute.setEnabled(not pending and self.has_control)
        self.slider.setEnabled(not self.busy and not output_pending and self.has_control)
        self.auto_audio.setEnabled(not pending)
        self.back.setEnabled(not pending)

    def loaded(self, data, error, message="", preserve=False):
        checked = self.checked_ids() if preserve else None
        self.working(False)
        self.list.blockSignals(True)
        for slider in self.output_sliders:
            slider.delay.stop()
        self.output_sliders = []
        self.list.clear()
        outputs = (data or {}).get("outputs", []) if not error else []
        control = (data or {}).get("control") if not error else None
        if control is None and not error:
            control = next((o for o in outputs if o.get("default")), None)
        self.has_control = control is not None
        self.auto_audio.setChecked((data or {}).get("auto_bluetooth", True))
        for output in outputs:
            selected = output.get("selected", output.get("default", False))
            item = QListWidgetItem(output["description"] + ("\nWird verwendet" if selected else "\nVerfügbar"))
            item.setData(Qt.ItemDataRole.UserRole, output)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if (output["id"] in checked if checked is not None else selected)
                               else Qt.CheckState.Unchecked)
            item.setSizeHint(QSize(0, 96))
            self.list.addItem(item)
            widget = QWidget()
            box = QVBoxLayout(widget)
            box.setContentsMargins(4, 4, 8, 4)
            check = QCheckBox(f'{output["description"]} · {output["volume"]} %')
            check.setChecked(item.checkState() == Qt.CheckState.Checked)
            check.setToolTip("Für gemeinsame Wiedergabe auswählen")
            check.toggled.connect(lambda checked, entry=item: entry.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked))
            box.addWidget(check)
            widget.setStyleSheet("background: #1e211a;")
            item.setData(Qt.ItemDataRole.ForegroundRole, self.palette().base())
            volume = PlayerSlider(output["description"] + " Lautstärke")
            volume.reflect(min(100, output["volume"]))
            volume.setToolTip(f'{output["volume"]} %')
            volume.valueChanged.connect(lambda value, text=check, name=output["description"]: text.setText(f"{name} · {value} %"))
            volume.committed.connect(lambda value, name=output["name"]: self.change(
                "audio_output_volume", {"name": name, "value": value}, preserve=True))
            self.output_sliders.append(volume)
            volume.valueChanged.connect(lambda _, active=volume: self.output_pending(active))
            box.addWidget(volume)
            self.list.setItemWidget(item, widget)
        self.list.blockSignals(False)
        self.slider.blockSignals(True)
        self.slider.setValue(min(100, control["volume"]) if control else 0)
        self.slider.blockSignals(False)
        self.level.setText(f'Gemeinsame Lautstärke: {self.slider.value()} %' if control else "Lautstärke nicht verfügbar")
        self.muted = bool(control and control["mute"])
        self.mute.setChecked(not self.muted)
        self.message.setText(error or message or (
            "" if outputs
            else "Kein Audioausgang erkannt. Bitte die Boxen anschließen."))
        self.update_controls()

    def output_pending(self, active):
        for slider in self.output_sliders:
            slider.setEnabled(slider is active)
        self.update_controls()

    def change(self, operation, args, preserve=False):
        if self.busy or self.closed:
            return
        self.working(True, "Einen Moment …")
        def done(data, error):
            self.client.refresh_status()
            self.request("audio", callback=lambda state, read_error:
                         self.loaded(state, read_error, error or "", preserve or bool(error)))
        self.request(operation, args, done)

    def volume_changed(self, value):
        self.level.setText(f"Gemeinsame Lautstärke: {value} %")
        self.volume_timer.start()
        self.update_controls()

    def apply_volume(self):
        if self.busy or self.closed or self.slider.isSliderDown():
            return
        self.volume_timer.stop()
        self.change("audio_volume", {"value": self.slider.value()}, preserve=True)

    def select_output(self):
        ids = self.checked_ids()
        if ids and not self.volume_timer.isActive():
            self.change("audio_outputs", {"ids": ids})

    def reject(self):
        if not any(s.delay.isActive() or s.isSliderDown() for s in self.output_sliders) and not self.volume_timer.isActive() and not self.slider.isSliderDown():
            super().reject()

    def closeEvent(self, event):
        if any(s.delay.isActive() or s.isSliderDown() for s in self.output_sliders) or self.volume_timer.isActive() or self.slider.isSliderDown():
            event.ignore()
        else:
            super().closeEvent(event)


class LogsSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Systemprotokolle",
                         "Fehler und Ereignisse dieses Starts anzeigen.")
        self.source = SettingsChoice([
            ("System", "system", ""),
            ("Sitzung", "session", ""),
            ("Programme", "apps", ""),
        ], compact=True)
        self.source.setAccessibleName("Protokollquelle")
        self.source.group.button(0).setAccessibleDescription("System: Warnungen und Fehler")
        self.source.group.button(1).setAccessibleDescription("Benutzersitzung")
        self.source.group.button(2).setAccessibleDescription("Vereinsprogramme")
        self.body.addWidget(self.source)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(600)
        self.output.setAccessibleName("Protokolleinträge")
        self.body.addWidget(self.output, 1)
        row = QHBoxLayout()
        self.reload = QPushButton("Aktualisieren")
        self.export = QPushButton("Als Text speichern")
        row.addWidget(self.reload)
        row.addWidget(self.export)
        self.body.addLayout(row)
        self.controls = [self.source, self.reload, self.export]
        self.process = QProcess(self)
        self.process.finished.connect(self.completed)
        self.process.errorOccurred.connect(self.failed)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.process.kill)
        self.reload.clicked.connect(self.load)
        self.source.currentIndexChanged.connect(self.load)
        self.export.clicked.connect(self.save)
        self.finished.connect(lambda: self.timeout.stop())
        self.load()

    def load(self):
        if self.busy:
            return
        self.output.clear()
        if self.client.preview:
            self.message.clear()
            self.output.setPlainText("Vorschau: Beispieldaten\n10:30:00 Vereinsoberfläche gestartet.\n10:31:02 Audioausgang verbunden.")
            return
        if self.source.currentIndex() == 2:
            try:
                path = Path.home() / ".local/state/saar-fighters/app-health.jsonl"
                with path.open("rb") as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 65536))
                    self.output.setPlainText(stream.read().decode("utf-8", errors="replace"))
                self.message.clear()
            except OSError:
                self.message.setText("Noch keine lesbaren Programmprotokolle vorhanden.")
            return
        self.working(True, "Protokolle werden geladen …")
        args = ["--no-pager", "--boot", "--lines=500", "--output=short-iso"]
        args += ["--priority=warning"] if self.source.currentIndex() == 0 else ["--user"]
        self.process.start("journalctl", args)
        self.timeout.start(10000)

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self.working(False, "Die Systemprotokolle sind auf diesem System nicht verfügbar.")

    def completed(self, code, status):
        self.timeout.stop()
        self.working(False)
        self.output.setPlainText(bytes(self.process.readAllStandardOutput()).decode(errors="replace"))
        detail = bytes(self.process.readAllStandardError()).decode(errors="replace").strip()
        self.message.setText("Protokolle konnten nicht vollständig geladen werden." if code else
                             "")
        if detail:
            self.message.setText(self.message.text() + "\n" + detail[:1500])

    def save(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Protokolle speichern", "saar-protokolle.txt", "Textdateien (*.txt)")
        if filename:
            try:
                Path(filename).write_text(self.output.toPlainText(), encoding="utf-8")
                self.message.setText("Protokolle gespeichert.")
            except OSError:
                self.message.setText("Die Datei konnte nicht gespeichert werden.")
