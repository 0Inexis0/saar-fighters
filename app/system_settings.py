"""System pages integrated into the club settings, using native Plasma controls."""
import json
from pathlib import Path
import shutil
import sys
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QPushButton, QPlainTextEdit, QHBoxLayout
from devices import Sheet, BrightnessSheet, SettingsChoice, label
from system_status import snapshot, gib

MODULES = {"display": "kcm_kscreen", "energy": "kcm_powerdevilprofilesconfig"}


def open_module(page, name):
    if page.client.preview:
        page.message.setText("Vorschau: Die KDE-Einstellungen werden auf dem Vereinsrechner geöffnet.")
        return
    executable = shutil.which("systemsettings")
    if not executable:
        page.message.setText("KDE-Systemeinstellungen fehlen. Bitte zuerst ein Systemupdate ausführen.")
        return
    started, _ = QProcess.startDetached(executable, [MODULES[name]])
    page.message.setText("KDE-Einstellungen im eigenen Fenster geöffnet." if started else "Die KDE-Einstellungen konnten nicht gestartet werden.")


class DisplaySheet(BrightnessSheet):
    def __init__(self, parent, client):
        super().__init__(parent, client)
        self.body.itemAt(0).layout().itemAt(0).widget().setText("Bildschirm")
        self.advanced = QPushButton("Anzeige einrichten …")
        self.advanced.clicked.connect(lambda: open_module(self, "display"))
        self.body.insertWidget(1, self.advanced)
        self.body.insertWidget(2, label("Anzeige einrichten: Auflösung, Größe, Drehung sowie Anordnung und Spiegelung mehrerer Monitore im KDE-Fenster."))
        self.controls.append(self.advanced)


class EnergySheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Energie", "Das gewählte Profil bleibt auch nach Anmeldung und Updates erhalten.")
        self.center = parent.home.notifications
        self.profile = SettingsChoice([
            ("Vereinsbetrieb", "club", "Bildschirm bleibt an. Kein automatischer Standby."),
            ("Laptopbetrieb", "laptop", "Nach 2 Min. abdunkeln, nach 5 Min. Bildschirm aus, nach 15 Min. Standby. Am Netzteil und am Akku."),
            ("Eigene Einstellungen", "custom", "Zeiten und Verhalten selbst in den Energieeinstellungen festlegen."),
        ])
        self.profile.setAccessibleName("Energieprofil")
        try:
            key = json.loads((Path.home() / ".config/saar-fighters/energy.json").read_text()).get("profile", "club") if not client.preview else "club"
        except (OSError, ValueError, AttributeError):
            key = "club"
        self.profile.setCurrentIndex(max(0, self.profile.findData(key)))
        self.body.addWidget(self.profile)
        self.apply_button = QPushButton("Profil übernehmen")
        self.apply_button.setObjectName("confirm")
        self.apply_button.clicked.connect(self.apply)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.apply_button)
        self.body.addLayout(actions)
        self.advanced = QPushButton("Weitere Energieeinstellungen …")
        self.advanced.clicked.connect(lambda: open_module(self, "energy"))
        self.body.addWidget(self.advanced)
        self.controls = [self.profile, self.apply_button, self.advanced]
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self.completed)
        self.process.errorOccurred.connect(self.failed)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.process.kill)
        self.message.setText("Aktuelle Auswahl: " + self.profile.currentText())
        self.profile.currentIndexChanged.connect(lambda _: self.message.setText(
            "Ausgewählt: " + self.profile.currentText() + ". Mit „Profil übernehmen“ anwenden."))
        self.body.addStretch()

    def apply(self):
        if self.client.preview:
            self.message.setText("Vorschau: Profil ausgewählt, keine Systemänderung.")
            return
        self.working(True, "Profil wird übernommen …")
        helper = Path(__file__).resolve().parents[1] / "system/energy_profile.py"
        self.process.start(sys.executable, [str(helper), self.profile.currentData()])
        self.timeout.start(20000)

    def completed(self, code, status):
        self.timeout.stop()
        self.working(False)
        message = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        self.message.setText(message or "Das Energieprofil konnte nicht vollständig übernommen werden.")
        center = self.center
        if center:
            center.add("Energieprofil" if code == 0 else "Energieprofil prüfen", self.message.text())

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self.working(False, "Die Energieverwaltung konnte nicht gestartet werden.")


class SystemSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Systemübersicht", "Lokale Systemdaten. Aktualisierung alle zehn Sekunden.")
        self.info = label("")
        self.body.addWidget(self.info)
        self.body.addStretch()
        self.timer = QTimer(self)
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.refresh)
        self.finished.connect(self.timer.stop)
        self.timer.start()
        self.refresh()

    def refresh(self):
        data = snapshot() if not self.client.preview else {"version": "Vorschau", "kernel": "Linux (Beispiel)", "architecture": "x86_64", "memory_used": 2 * 1024**3, "memory_total": 4 * 1024**3, "disk_free": 20 * 1024**3, "disk_total": 32 * 1024**3, "last_update": "Beispiel: heute, 10:30"}
        self.message.setText("Saar-Fighters OS · Arch Linux")
        self.info.setText(f"Oberflächenstand: {data['version']}\n\nKernel: {data['kernel']}\nArchitektur: {data['architecture']}\n\nArbeitsspeicher: {gib(data['memory_used'])} von {gib(data['memory_total'])} belegt\n\nSystemlaufwerk: {gib(data['disk_free'])} von {gib(data['disk_total'])} frei\n\nLetztes erfolgreiches Systemupdate:\n{data['last_update']}")


class NotificationsSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Meldungen", "Updateergebnisse, Geräteprobleme, Akku und Speicher. Bis zu 100 lokale Einträge.")
        self.center = parent.home.notifications
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setAccessibleName("Benachrichtigungsverlauf")
        self.body.addWidget(self.output, 1)
        read = QPushButton("Alle als gelesen markieren")
        read.clicked.connect(self.center.mark_read)
        self.body.addWidget(read)
        clear = QPushButton("Verlauf leeren")
        clear.clicked.connect(self.center.clear)
        self.body.addWidget(clear)
        self.center.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.message.setText(self.center.storage_error or (f"{self.center.unread} ungelesene Meldungen" if self.center.items else "Keine Meldungen vorhanden."))
        self.output.setPlainText("\n\n".join(f"{'NEU · ' if not item['read'] else ''}{item['title']}\n{item['time']}\n{item['body']}" for item in reversed(self.center.items)))
