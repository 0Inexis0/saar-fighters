#!/usr/bin/env python3
"""Maintenance pages and a standalone rescue window, independent of Home."""
import json
import sys
from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox,
                              QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout)

HELPER = "/usr/local/libexec/saar-maintenance"


def text_label(text, size=14):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setStyleSheet(f"font-size: {size}px;")
    return widget


class MaintenancePage(QDialog):
    def __init__(self, parent=None, preview=False, section="remote"):
        super().__init__(parent)
        self.preview, self.section = preview, section
        self.busy, self.closed = False, False
        self.snapshot = {}
        self.action_name = None
        self.setWindowTitle("Fernwartung" if section == "remote" else "Wiederherstellung")
        body = QVBoxLayout(self)
        body.setSpacing(14)
        body.addWidget(text_label(self.windowTitle(), 26))
        explanation = ("Zugriff auf diesen Rechner im gleichen WLAN oder LAN. Die Anmeldung erfolgt ausschließlich mit dem hinterlegten SSH-Schlüssel."
                       if section == "remote" else
                       "Stellt die vor dem letzten Oberflächenupdate gesicherte Version wieder her. Persönliche Dateien, Anmeldungen, SSH und Systempakete bleiben erhalten.")
        body.addWidget(text_label(explanation))
        if preview:
            body.addWidget(text_label("Vorschau mit Beispieldaten. Es werden keine Änderungen ausgeführt.", 12))
        self.summary = text_label("Status wird geladen …", 20)
        body.addWidget(self.summary)
        self.details = text_label("")
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.details)
        self.notice = text_label("", 12)
        body.addWidget(self.notice)
        row = QHBoxLayout()
        self.action = QPushButton("Fernwartung einschalten" if section == "remote" else "Vorherige Oberfläche wiederherstellen")
        self.action.setEnabled(False)
        self.reload = QPushButton("Aktualisieren")
        row.addWidget(self.action, 1)
        row.addWidget(self.reload)
        body.addLayout(row)
        self.message = text_label("")
        body.addWidget(self.message)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(125)
        self.output.hide()
        body.addWidget(self.output)
        body.addStretch()
        self.back = QPushButton("Zurück")
        self.back.clicked.connect(self.reject)
        body.addWidget(self.back)
        for button in (self.back, self.action, self.reload):
            button.setAutoDefault(False)
        self.reader = QProcess(self)
        self.reader.finished.connect(self.read_status)
        self.reader.errorOccurred.connect(self.status_error)
        self.worker = QProcess(self)
        self.worker.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.worker.readyReadStandardOutput.connect(self.read_output)
        self.worker.finished.connect(self.completed)
        self.worker.errorOccurred.connect(self.action_error)
        self.action.clicked.connect(self.begin)
        self.reload.clicked.connect(self.refresh)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        if self.busy or self.closed or self.reader.state() != QProcess.ProcessState.NotRunning:
            return
        if self.preview:
            self.show_status({"ssh": {"state": "active", "disabled": False, "addresses": ["192.168.1.42"]},
                              "surface": {"current": "a" * 40, "previous": "b" * 40,
                                          "available": True, "backup_id": "c" * 64}, "live": False})
        else:
            self.reader.start(HELPER, ["status"])

    def status_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and not self.closed:
            self.summary.setText("Wartung noch nicht verfügbar")
            self.details.setText("Bitte zuerst ein Systemupdate ausführen und die Einstellungen erneut öffnen.")
            self.action.setEnabled(False)

    def read_status(self, code, exit_status):
        if self.closed or self.busy:
            return
        try:
            if code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
                raise ValueError()
            self.show_status(json.loads(bytes(self.reader.readAllStandardOutput())))
        except (ValueError, TypeError, KeyError):
            self.summary.setText("Status konnte nicht gelesen werden")
            self.action.setEnabled(False)

    def show_status(self, data):
        self.snapshot = data
        live = data.get("live", False)
        if self.section == "remote":
            ssh = data.get("ssh", {})
            active = ssh.get("state") == "active"
            self.summary.setText("Fernwartung aktiv" if active else
                                 "Fernwartung ausgeschaltet" if ssh.get("state") in ("inactive", "failed") or ssh.get("disabled") else
                                 "SSH-Status unbekannt")
            addresses = ssh.get("addresses", [])
            self.details.setText("\n".join(f"ssh -p 2222 wartung@{ip}" for ip in addresses)
                                 if addresses else "Keine lokale IPv4-Adresse gefunden. Bitte WLAN oder LAN verbinden.")
            self.notice.setText("Port 2222 · Konto wartung · Nur Schlüsselanmeldung\n"
                                "Beim Ausschalten werden neue Verbindungen gesperrt. Bereits offene Sitzungen können weiterlaufen.")
            self.action_name = "disable-ssh" if active else "enable-ssh"
            self.action.setText("Fernwartung ausschalten" if active else "Fernwartung einschalten")
            self.action.setEnabled(not live and ssh.get("state") != "unknown")
        else:
            surface = data.get("surface", {})
            short = lambda value: value[:12] if len(value) == 40 else value
            self.summary.setText("Sicherung verfügbar" if surface.get("available") else "Keine Wiederherstellung verfügbar")
            self.details.setText(f"Aktuelle Oberfläche: {short(surface.get('current', 'Unbekannt'))}\n"
                                 f"Gesicherte Oberfläche: {short(surface.get('previous', 'Keine'))}")
            self.notice.setText(surface.get("reason") or "Die Sicherung wurde vor dem Update erstellt. Ob sie auf diesem Gerät fehlerfrei lief, wurde nicht automatisch geprüft.")
            self.action_name = "restore"
            self.action.setEnabled(bool(surface.get("available")) and not live)
        if live:
            self.notice.setText("Diese Funktion ist nur auf dem installierten Rechner verfügbar.")

    def working(self, busy):
        self.busy = busy
        self.back.setEnabled(not busy)
        self.reload.setEnabled(not busy)
        self.action.setEnabled(not busy)

    def begin(self):
        if self.busy or not self.action.isEnabled():
            return
        if self.preview:
            self.message.setText("Vorschau: Es wurde nichts verändert.")
            return
        if self.action_name == "restore":
            answer = QMessageBox.question(self, "Oberfläche wiederherstellen?",
                "Die aktuelle Oberfläche wird durch die angezeigte Sicherung ersetzt. Danach ist ein Neustart nötig.\n\n"
                "Persönliche Daten und Systempakete bleiben erhalten. Jetzt wiederherstellen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.working(True)
        self.message.setText("Warte auf Wartungspasswort / Änderung läuft …")
        self.output.clear()
        self.output.show()
        args = [HELPER, self.action_name]
        if self.action_name == "restore":
            args.append(self.snapshot.get("surface", {}).get("backup_id", ""))
        self.worker.start("pkexec", args)

    def read_output(self):
        self.output.appendPlainText(bytes(self.worker.readAllStandardOutput()).decode(errors="replace"))

    def completed(self, code, exit_status):
        self.working(False)
        if code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self.message.setText("Oberfläche wiederhergestellt. Bitte den Rechner neu starten."
                                 if self.action_name == "restore" else "Fernwartung geändert.")
        elif code in (126, 127):
            self.message.setText("Änderung nicht freigegeben oder abgebrochen.")
        else:
            self.message.setText("Änderung fehlgeschlagen. Details stehen in der Ausgabe.")
        self.action.setEnabled(False)
        self.refresh()

    def action_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.working(False)
            self.message.setText("Die Wartungsverwaltung konnte nicht gestartet werden.")
            self.action.setEnabled(False)

    def reject(self):
        if self.busy:
            return
        self.closed = True
        self.timer.stop()
        if self.reader.state() != QProcess.ProcessState.NotRunning:
            self.reader.kill()
            self.reader.waitForFinished(500)
        super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            self.reject()
            event.accept()


class MaintenanceWindow(QDialog):
    def __init__(self, preview=False):
        super().__init__()
        self.setWindowTitle("Saar-Fighters Wartung")
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.pages = []
        for section, title in (("recovery", "Wiederherstellung"), ("remote", "Fernwartung")):
            page = MaintenancePage(self, preview, section)
            page.setWindowFlags(Qt.WindowType.Widget)
            page.back.hide()
            self.pages.append(page)
            tabs.addTab(page, title)
        layout.addWidget(tabs)

    def reject(self):
        if any(page.busy for page in self.pages):
            return
        for page in self.pages:
            page.reject()
        super().reject()

    def closeEvent(self, event):
        if any(page.busy for page in self.pages):
            event.ignore()
        else:
            self.reject()
            event.accept()


def main():
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet("QDialog,QWidget {background:#25281f;color:#eeece1;font-size:14px;}"
                      "QPushButton {padding:10px;background:#3c4430;border-radius:6px;}"
                      "QPushButton:disabled {color:#929382;}")
    window = MaintenanceWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
