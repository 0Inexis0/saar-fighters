#!/usr/bin/env python3
"""German, native installer. Destructive operations require two confirmations."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from installer.core import disks
from main import STYLE
from devices import label
from PySide6.QtCore import QLocale, QProcess, QTimer, QSize, Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget)


class Installer(QWidget):
    def __init__(self, preview=False):
        super().__init__()
        self.preview = preview
        self.running = False
        self.done = False
        self.buffer = b""
        self.setWindowTitle("Saar-Fighters OS installieren")
        self.resize(880, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)
        layout.addWidget(label("Saar-Fighters OS installieren", "font-size: 28px; font-weight: 750;"))
        layout.addWidget(label("Eine frische Installation für euren Vereinslaptop. Programme und Oberfläche sind auf dem USB-Stick enthalten."))
        self.warning = label("Alle Daten auf dem ausgewählten Laufwerk werden gelöscht. Andere Laufwerke werden nicht verändert.", "color: #ffc38a; font-weight: 600;")
        layout.addWidget(self.warning)
        self.list = QListWidget()
        self.list.setAccessibleName("Laufwerk für die Installation")
        self.list.currentItemChanged.connect(self.validate)
        layout.addWidget(self.list, 1)
        self.refresh = QPushButton("Laufwerke neu suchen")
        self.refresh.clicked.connect(self.load)
        layout.addWidget(self.refresh)
        layout.addWidget(label("Passwort für das Wartungskonto", "font-weight: 700;"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mindestens 10 Zeichen")
        self.repeat = QLineEdit()
        self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat.setPlaceholderText("Passwort wiederholen")
        password_row = QHBoxLayout()
        for field in (self.password, self.repeat):
            field.setMaxLength(128)
            field.textChanged.connect(self.validate)
            password_row.addWidget(field)
        layout.addLayout(password_row)
        layout.addWidget(label("Dieses Passwort wird für Updates benötigt. Die normale Vereinsnutzung startet automatisch ohne Anmeldung.", "color: #b8c3b9;"))
        self.erase = QCheckBox("Ich bestätige: Alle Daten auf dem ausgewählten Laufwerk dürfen gelöscht werden.")
        self.erase.toggled.connect(self.validate)
        layout.addWidget(self.erase)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.message = label()
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.back = QPushButton("Zurück zum Ausprobieren")
        self.back.clicked.connect(self.close)
        row.addWidget(self.back)
        self.install = QPushButton("Jetzt installieren")
        self.install.setObjectName("confirm")
        self.install.clicked.connect(self.begin)
        row.addWidget(self.install)
        self.reboot = QPushButton("Neu starten")
        self.reboot.clicked.connect(lambda: QProcess.startDetached("systemctl", ["reboot"]) if not self.preview else None)
        self.reboot.hide()
        row.addWidget(self.reboot)
        layout.addLayout(row)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed_start)
        self.inputs = (self.list, self.refresh, self.password, self.repeat, self.erase)
        self.load()
        self.refresh.setFocus()

    def load(self):
        self.list.clear()
        self.erase.setChecked(False)
        try:
            available = ([{"path": "/dev/example", "size": 128000000000, "model": "Beispiellaufwerk",
                           "serial": "VORSCHAU", "identity": "preview"}] if self.preview else disks())
            for disk in available:
                text = f'{disk["model"]} · {disk["size"] / 1e9:.0f} GB · {disk["path"]}'
                if disk["serial"]:
                    text += f'\nSeriennummer: {disk["serial"]}'
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, disk)
                item.setSizeHint(QSize(0, 64))
                self.list.addItem(item)
            self.list.setCurrentRow(-1)
            self.message.setText("Bitte das Ziellaufwerk bewusst auswählen." if available else
                "Kein freies Laufwerk ab 32 GB erkannt. Der USB-Stick und verwendete Laufwerke werden ausgeblendet.")
        except Exception:
            self.message.setText("Die Laufwerke konnten nicht gelesen werden. Bitte erneut suchen.")
        if self.preview:
            self.message.setText("Vorschau: Es wird nichts auf ein Laufwerk geschrieben.")
        self.validate()

    def validate(self, *_):
        valid = (self.list.currentItem() is not None and self.erase.isChecked()
                 and 10 <= len(self.password.text()) <= 128 and self.password.text() == self.repeat.text()
                 and not any(c in self.password.text() for c in "\n\r\0"))
        self.install.setEnabled(bool(valid) and not self.running and not self.done)

    def begin(self):
        if not self.install.isEnabled():
            return
        disk = self.list.currentItem().data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox(QMessageBox.Icon.Warning, "Laufwerk endgültig löschen?",
            f'{disk["model"]} · {disk["size"] / 1e9:.0f} GB\n{disk["path"]}\n'
            f'Seriennummer: {disk["serial"] or "nicht angegeben"}\n\n'
            'Alle vorhandenen Dateien und Betriebssysteme darauf werden gelöscht. Dieser Schritt kann nicht rückgängig gemacht werden.', parent=self)
        confirm.setTextFormat(Qt.TextFormat.PlainText)
        yes = confirm.addButton("Laufwerk löschen und installieren", QMessageBox.ButtonRole.DestructiveRole)
        no = confirm.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        confirm.setDefaultButton(no)
        confirm.exec()
        if confirm.clickedButton() != yes:
            return
        if self.preview:
            self.message.setText("Vorschau: Bestätigung geprüft. Es wurde nichts installiert.")
            return
        self.request = {"disk": disk["path"], "identity": disk["identity"],
                        "confirm_erase": disk["identity"], "admin_password": self.password.text()}
        self.password.clear()
        self.repeat.clear()
        self.running = True
        for control in (*self.inputs, self.back, self.install):
            control.setEnabled(False)
        self.message.setText("Installation wird gestartet … Bitte das Netzteil angeschlossen lassen.")
        self.process.started.connect(self.send_request)
        self.process.start("sudo", ["-n", "/usr/local/libexec/saar-install"])

    def send_request(self):
        self.process.write((json.dumps(self.request) + "\n").encode())
        self.request.clear()
        self.process.closeWriteChannel()

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if "error" in event:
                self.message.setText(event["error"])
            if "percent" in event:
                self.progress.setValue(event["percent"])
                self.message.setText(event["message"])

    def finished(self, code, status):
        self.read()
        self.running = False
        self.done = code == 0 and status == QProcess.ExitStatus.NormalExit and self.progress.value() == 100
        self.back.setEnabled(True)
        if self.done:
            self.reboot.show()
            self.message.setText("Fertig! Beim Neustart den USB-Stick entfernen. Das Wartungskonto heißt „wartung“.")
        else:
            self.message.setText(self.message.text() + "\nInstallation nicht abgeschlossen. Bitte erneut vom USB-Stick starten.")

    def failed_start(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.running = False
            getattr(self, "request", {}).clear()
            self.message.setText("Der Installer konnte nicht gestartet werden. Bitte erneut vom USB-Stick starten.")
            self.back.setEnabled(True)

    def closeEvent(self, event):
        if self.running:
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv[:1])
    QLocale.setDefault(QLocale("de_DE"))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE + "QWidget { background-color: #18271f; } QProgressBar { border: 1px solid #64745b; border-radius: 7px; text-align: center; min-height: 24px; } QProgressBar::chunk { background: #6c9858; } QCheckBox { color: #ffc38a; }")
    preview = "--preview" in sys.argv
    if not preview and not Path("/etc/saar-live").exists():
        QMessageBox.information(None, "Installation", "Bitte den Rechner vom Saar-Fighters-USB-Stick starten.")
        return 1
    window = Installer(preview)
    window.showMaximized() if not preview else window.show()
    result = app.exec()
    import shiboken6
    shiboken6.delete(window)
    return result


if __name__ == "__main__":
    sys.exit(main())
