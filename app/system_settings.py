"""System pages integrated into the club settings, using native Plasma controls."""
import re
import shutil
from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer
from PySide6.QtWidgets import QPushButton, QPlainTextEdit
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
        self.body.itemAt(0).layout().itemAt(0).widget().setText("Bildschirm & Helligkeit")
        self.advanced = QPushButton("Anzeige einrichten …")
        self.advanced.clicked.connect(lambda: open_module(self, "display"))
        self.body.insertWidget(1, self.advanced)
        self.body.insertWidget(2, label("Anzeige einrichten: Auflösung, Größe, Drehung sowie Anordnung und Spiegelung mehrerer Monitore im KDE-Fenster."))
        self.controls.append(self.advanced)


class EnergySheet(Sheet):
    PROFILES = (
        ("Energiesparen", "power-saver", "Weniger Energieverbrauch, längere Akkulaufzeit."),
        ("Ausgeglichen", "balanced", "Eine ausgewogene Mischung aus Leistung und Energieverbrauch."),
        ("Leistung", "performance", "Mehr Leistung bei höherem Energieverbrauch."),
    )

    def __init__(self, parent, client):
        super().__init__(parent, client, "Energie & Leistung", "Leistungsprofil für diesen Rechner. Änderungen werden direkt übernommen.")
        self.profile = SettingsChoice(self.PROFILES)
        self.profile.setAccessibleName("Linux-Leistungsprofil")
        self.body.addWidget(self.profile)
        self.availability = label("")
        self.body.addWidget(self.availability)
        self.advanced = QPushButton("Bildschirm und Standby einrichten …")
        self.advanced.clicked.connect(lambda: open_module(self, "energy"))
        self.body.addWidget(self.advanced)
        self.body.addStretch()
        self.controls = [self.profile, self.advanced]
        self.available = set()
        self.active = None
        self.phase = None
        self.pending_profile = None
        self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        self.process.setProcessEnvironment(environment)
        self.process.finished.connect(self.completed)
        self.process.errorOccurred.connect(self.failed)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.process.kill)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(10000)
        self.refresh_timer.timeout.connect(self.load)
        self.finished.connect(self.refresh_timer.stop)
        self.profile.currentIndexChanged.connect(self.apply)
        self.load()
        self.refresh_timer.start()

    def run(self, phase, arguments):
        self.phase = phase
        self.working(True)
        self.timeout.start(10000)
        self.process.start("powerprofilesctl", arguments)

    def load(self):
        if self.busy or self.closed:
            return
        if self.client.preview:
            self.available = {key for _, key, _ in self.PROFILES}
            self.show_active(self.active or "balanced")
        else:
            self.run("list", ["list"])

    def show_active(self, key):
        if key not in self.available:
            self.unavailable("Das aktuelle Leistungsprofil konnte nicht gelesen werden.")
            return
        self.active = key
        self.working(False)
        self.profile.blockSignals(True)
        self.profile.setCurrentIndex(self.profile.findData(key))
        self.profile.blockSignals(False)
        for index, (_, profile, _) in enumerate(self.PROFILES):
            self.profile.group.button(index).setEnabled(profile in self.available)
        self.availability.setText("Leistung wird von diesem Rechner nicht angeboten." if "performance" not in self.available else "")
        self.availability.setVisible(bool(self.availability.text()))
        self.message.setText(("Vorschau · Aktiv: " if self.client.preview else "Aktiv: ") + self.profile.currentText())

    def apply(self, *_):
        key = self.profile.currentData()
        if self.busy or key not in self.available:
            return
        if self.client.preview:
            self.show_active(key)
            return
        self.pending_profile = key
        self.message.setText("Leistungsprofil wird geändert …")
        self.run("set", ["set", key])

    def completed(self, code, status):
        self.timeout.stop()
        if self.closed:
            return
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        detail = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if code or status != QProcess.ExitStatus.NormalExit:
            if self.phase == "set" and self.active:
                self.show_active(self.active)
                self.message.setText("Leistungsprofil konnte nicht geändert werden. " + detail[:250])
            else:
                self.unavailable("Linux-Energieverwaltung ist nicht erreichbar. Bitte Systemupdate und Energiedienst prüfen.")
            return
        if self.phase == "list":
            self.available = set(re.findall(r"(?m)^\s*\*?\s*(power-saver|balanced|performance):\s*$", output))
            if not self.available:
                self.unavailable("Dieser Rechner bietet keine unterstützten Leistungsprofile an.")
                return
            self.run("get", ["get"])
        elif self.phase == "set":
            self.run("verify", ["get"])
        else:
            self.show_active(output)
            if self.phase == "verify" and output != self.pending_profile:
                self.message.setText("Das angeforderte Profil ist nicht aktiv. Aktuell: " + self.profile.currentText())

    def unavailable(self, message):
        self.working(False, message)
        self.profile.setEnabled(False)
        self.profile.blockSignals(True)
        self.profile.group.setExclusive(False)
        for button in self.profile.group.buttons():
            button.setChecked(False)
        self.profile.group.setExclusive(True)
        self.profile.blockSignals(False)
        self.active = None

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self.unavailable("Linux-Leistungsprofile fehlen. Bitte ein Systemupdate ausführen (power-profiles-daemon).")


class SystemSheet(Sheet):
    def __init__(self, parent, client):
        super().__init__(parent, client, "Systeminformationen", "Lokale Systemdaten. Aktualisierung alle zehn Sekunden.")
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
        super().__init__(parent, client, "Mitteilungen", "Updateergebnisse, Geräteprobleme, Akku und Speicher. Bis zu 100 lokale Einträge.")
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
