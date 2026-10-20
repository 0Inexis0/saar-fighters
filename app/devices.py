"""Shared native device screens; all visible copy is German."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QProcess, Qt, QTimer, Signal, QSize
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                              QListWidgetItem, QPushButton, QSlider, QVBoxLayout)

from hardware import wifi_password_valid

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


class DeviceClient(QObject):
    status_changed = Signal(dict)
    pairing = Signal(dict)

    def __init__(self, parent=None, preview=False):
        super().__init__(parent)
        self.preview = preview
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
            QTimer.singleShot(0, lambda: self.preview_reply(operation, callback))
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

    def preview_reply(self, operation, callback):
        data = {
            "status": EXAMPLE_STATUS,
            "wifi": {"available": True, "enabled": True, "hardware_enabled": True, "networks": [
                {"path": "/example/1", "name": "Vereinsheim", "strength": 91, "mode": "wpa-psk", "connected": True, "saved": "yes"},
                {"path": "/example/2", "name": "Gastnetz", "strength": 63, "mode": "wpa-psk", "connected": False, "saved": ""},
            ]},
            "bluetooth": {"available": True, "powered": True, "devices": [
                {"path": "/example/box", "name": "Vereinsboxen", "connected": True, "paired": True},
                {"path": "/example/new", "name": "Neuer Lautsprecher", "connected": False, "paired": False},
            ]},
            "audio": {"outputs": [{"id": "1", "name": "example", "description": "Vereinsboxen",
                                  "default": True, "mute": False, "volume": 55}]},
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
        self.body.addWidget(label(description, "color: #b8c3b9;"))
        if client.preview:
            self.body.addWidget(label("Vorschau · Beispieldaten · keine Änderungen am Rechner", "color: #edaa66;"))
        self.message = label("Wird geladen …", "color: #cbdcb9;")
        self.body.addWidget(self.message)
        self.controls = []
        self.finished.connect(lambda _: setattr(self, "closed", True))

    def working(self, busy, message=""):
        self.busy = busy
        self.back.setEnabled(not busy)
        for control in self.controls:
            control.setEnabled(not busy)
        if message:
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
            self.message.setText(error or data.get("message", "Einstellung übernommen."))
            self.client.refresh_status()
            if finished and not error:
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
        super().__init__(parent, client, "WLAN", "Netz auswählen, bei Bedarf Passwort eingeben und verbinden.")
        row = QHBoxLayout()
        self.toggle = QPushButton("WLAN einschalten")
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
        self.toggle.setText("WLAN ausschalten" if self.info.get("enabled") else "WLAN einschalten")
        self.toggle.setEnabled(bool(self.info.get("available")) and not error)
        self.scan.setEnabled(bool(self.info.get("available") and self.info.get("enabled")))
        if error:
            self.message.setText(error)
        elif not data["available"]:
            self.message.setText("Kein WLAN-Adapter erkannt. Ein Netzwerkkabel kann trotzdem verbunden sein.")
        elif not data["hardware_enabled"]:
            self.message.setText("WLAN ist am Gerät gesperrt. Bitte Flugmodus oder WLAN-Schalter prüfen.")
        elif not data["enabled"]:
            self.message.setText("WLAN ist ausgeschaltet.")
        else:
            self.message.setText("Wähle dein WLAN aus." if data["networks"] else "Noch keine Netze gefunden. Bitte erneut suchen.")
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
            self.message.setText(error or data["message"])
            self.client.refresh_status()
            if not error:
                self.load()
        self.request("wifi_connect", {"path": network["path"], "password": password}, connected)


class BluetoothSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Bluetooth", "Boxen oder andere Geräte auswählen. Neue Geräte vorher in den Kopplungsmodus versetzen.")
        row = QHBoxLayout()
        self.toggle = QPushButton("Bluetooth einschalten")
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
        self.toggle.setText("Bluetooth ausschalten" if powered else "Bluetooth einschalten")
        self.scan.setEnabled(bool(available and powered))
        self.scan.setText("Suche beenden" if self.searching else "Geräte suchen")
        if not quiet:
            self.message.setText(error or ("Kein Bluetooth-Adapter erkannt." if not available else
                "Bluetooth ist ausgeschaltet." if not powered else "Wähle ein Gerät aus oder starte die Suche."))
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
                self.message.setText("Suche beendet. Du kannst erneut nach Geräten suchen.")

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
            layout.addWidget(label(event["code"], "font-size: 34px; font-weight: 700; color: #edaa66;"))
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


class AudioSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Lautstärke & Boxen", "Audioausgang auswählen und die Lautstärke einstellen.")
        self.list = QListWidget()
        self.list.setAccessibleName("Audioausgänge")
        self.body.addWidget(self.list, 1)
        self.level = label("Lautstärke", "font-size: 22px; font-weight: 700;")
        self.body.addWidget(self.level)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setAccessibleName("Lautstärke in Prozent")
        self.body.addWidget(self.slider)
        row = QHBoxLayout()
        self.mute = QPushButton("Stummschalten")
        self.choose = QPushButton("Diesen Ausgang verwenden")
        self.choose.setObjectName("confirm")
        row.addWidget(self.mute)
        row.addWidget(self.choose)
        self.body.addLayout(row)
        self.controls = [self.slider, self.mute, self.choose, self.list]
        self.muted = False
        self.slider.valueChanged.connect(lambda value: self.level.setText(f"Lautstärke: {value} %"))
        self.volume_timer = QTimer(self)
        self.volume_timer.setSingleShot(True)
        self.finished.connect(self.volume_timer.stop)
        self.volume_timer.timeout.connect(lambda: self.action("audio_volume", {"value": self.slider.value()}))
        self.slider.valueChanged.connect(lambda _: self.volume_timer.start(350))
        self.mute.clicked.connect(lambda: self.action("audio_mute", {"muted": not self.muted}, self.load))
        self.choose.clicked.connect(self.select_output)
        self.load()

    def load(self):
        self.request("audio", callback=self.loaded)

    def loaded(self, data, error):
        self.list.clear()
        outputs = (data or {}).get("outputs", [])
        self.message.setText(error or ("Wähle die Boxen aus, über die die Musik laufen soll." if outputs
                                       else "Kein Audioausgang erkannt. Bitte die Boxen anschließen."))
        for control in self.controls:
            control.setEnabled(bool(outputs) and not error)
        for output in outputs:
            item = QListWidgetItem(output["description"] + ("\nWird verwendet" if output["default"] else "\nVerfügbar"))
            item.setData(Qt.ItemDataRole.UserRole, output)
            item.setSizeHint(QSize(0, 64))
            self.list.addItem(item)
            if output["default"]:
                self.list.setCurrentItem(item)
                self.slider.blockSignals(True)
                self.slider.setValue(min(100, output["volume"]))
                self.slider.blockSignals(False)
                self.level.setText(f'Lautstärke: {output["volume"]} %')
                self.muted = output["mute"]
                self.mute.setText("Ton einschalten" if self.muted else "Stummschalten")

    def select_output(self):
        item = self.list.currentItem()
        if item:
            self.action("audio_output", {"id": item.data(Qt.ItemDataRole.UserRole)["id"]}, self.load)
