"""Bounded local notification history for club OS events, without personal data."""
from datetime import datetime
from pathlib import Path
import json
from PySide6.QtCore import QObject, Signal


class NotificationCenter(QObject):
    changed = Signal()

    def __init__(self, parent=None, preview=False, path=None):
        super().__init__(parent)
        self.preview = preview
        self.path = path or Path.home() / ".local/state/saar-fighters/notifications.json"
        self.items = []
        self.active = set()
        self.storage_error = ""
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
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(".tmp")
                temporary.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
                temporary.replace(self.path)
                self.storage_error = ""
            except OSError:
                self.storage_error = "Meldungen können momentan nur bis zum Schließen der Oberfläche gespeichert werden."
        self.changed.emit()

    def add(self, title, body):
        self.items.append({"title": title, "body": body, "time": datetime.now().astimezone().isoformat(timespec="seconds"), "read": False})
        self.items = self.items[-100:]
        self.save()

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
        self.save()
