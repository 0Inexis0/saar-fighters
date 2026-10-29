"""Bounded local history shared by the club UI and desktop notifications."""
from datetime import datetime
from pathlib import Path
import json
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QLabel


class NoticeLabel(QLabel):
    """Keep contextual feedback visible and also collect it in the bell."""
    def __init__(self, text="", record_notifications=True):
        super().__init__()
        self.record_notifications = record_notifications
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(text)

    def setText(self, text):
        previous = self.text()
        super().setText(text)
        self.setVisible(bool(text))
        if text and text != previous and self.record_notifications:
            owner = self.parentWidget()
            title = "Saar-Fighters"
            while owner:
                if owner.windowTitle() and title == "Saar-Fighters":
                    title = owner.windowTitle()
                center = getattr(owner, "notifications", None)
                if center is not None:
                    center.add(title, text)
                    break
                owner = owner.parentWidget()

    def clear(self):
        self.setText("")


class NotificationCenter(QObject):
    changed = Signal()

    def __init__(self, parent=None, preview=False, path=None):
        super().__init__(parent)
        self.preview = preview
        self.path = path or Path.home() / ".local/state/saar-fighters/notifications.json"
        self.items = []
        self.active = set()
        self.storage_error = ""
        self.service_error = ""
        self.desktop_items = {}
        if not preview:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.items = [item for item in data[-100:] if isinstance(item, dict)
                                  and all(isinstance(item.get(key), str) for key in ("title", "body", "time"))
                                  and isinstance(item.get("read"), bool)]
            except (OSError, ValueError):
                pass

    @property
    def unread(self):
        return sum(not item["read"] for item in self.items)

    def save(self):
        if not self.preview:
            try:
                self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                temporary = self.path.with_suffix(".tmp")
                temporary.touch(mode=0o600, exist_ok=True)
                temporary.chmod(0o600)
                temporary.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
                temporary.replace(self.path)
                self.storage_error = ""
            except OSError:
                self.storage_error = "Meldungen können momentan nur bis zum Schließen der Oberfläche gespeichert werden."
        self.changed.emit()

    def add(self, title, body, source="Saar-Fighters", desktop_key=None):
        item = {"title": title, "body": body, "source": source,
                "time": datetime.now().astimezone().isoformat(timespec="seconds"), "read": False}
        previous = self.desktop_items.get(desktop_key) if desktop_key else None
        if previous is not None and any(entry is previous for entry in self.items):
            if all(previous.get(key) == item[key] for key in ("title", "body", "source")):
                return
            self.items = [entry for entry in self.items if entry is not previous]
        self.items.append(item)
        self.items = self.items[-100:]
        if desktop_key:
            self.desktop_items[desktop_key] = item
        retained = {id(entry) for entry in self.items}
        self.desktop_items = {key: entry for key, entry in self.desktop_items.items() if id(entry) in retained}
        self.save()

    def desktop_event(self, event):
        if event.get("event") == "notification":
            values = [event.get(key) for key in ("title", "body", "source", "key")]
            if all(isinstance(value, str) for value in values):
                title, body, source, key = values
                self.add(title[:256], body[:8192], source[:256], key[:256])
        elif event.get("event") in ("ready", "unavailable"):
            self.service_error = ("Systemmitteilungen sind gerade nicht verbunden. Verbindung wird erneut versucht."
                                  if event["event"] == "unavailable" else "")
            self.condition("desktop-bridge", bool(self.service_error), "Systemmitteilungen", self.service_error)
            self.changed.emit()

    def condition(self, key, present, title, body):
        if present and key not in self.active:
            self.active.add(key)
            self.add(title, body)
        elif not present:
            self.active.discard(key)

    def devices(self, status):
        power = status.get("power", {})
        pct = power.get("percentage")
        self.condition("battery", isinstance(pct, (int, float)) and pct <= 15 and power.get("plugged") is False,
                       "Akku niedrig", "Bitte das Netzteil anschließen. Der Akku liegt bei höchstens 15 Prozent.")
        for key, name in (("network", "Netzwerk"), ("bluetooth", "Bluetooth"), ("power", "Akku und Netzteil")):
            self.condition(key, bool(status.get(key, {}).get("error")), "Gerätestatus nicht verfügbar",
                           f"{name} konnte nicht abgefragt werden. Bitte die Verbindung in den Einstellungen prüfen.")

    def disk(self, free, total):
        self.condition("disk", free is not None and bool(total) and (free < 2 * 1024**3 or free / total < .05),
                       "Wenig freier Speicher", "Auf dem Systemlaufwerk sind weniger als 2 GiB oder 5 Prozent frei.")

    def mark_read(self):
        for item in self.items:
            item["read"] = True
        self.save()

    def clear(self):
        self.items = []
        self.desktop_items.clear()
        self.save()
