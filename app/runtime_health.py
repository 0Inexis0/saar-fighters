"""Bounded app diagnostics without URLs, titles, credentials, or raw output."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

APPS = {"spotify", "web", "youtube", "club", "rocket", "files"}
PATTERNS = {"memory": ("corrupted", "double free", "malloc", "out of memory"),
            "graphics": ("gpu process", "gpu hang", "egl_bad", "failed to create renderer"),
            "audio": ("failed to connect to pulseaudio", "pipewire connection failed")}


def categories(text):
    text = text.lower()
    return {name for name, patterns in PATTERNS.items() if any(p in text for p in patterns)}


def record(app, event, code=None, category=None, home=None):
    if app not in APPS or event not in {"start", "exit", "error"}:
        return
    row = {"time": datetime.now(timezone.utc).isoformat(), "app": app, "event": event}
    if isinstance(code, int):
        row["code"] = code
    if category in PATTERNS:
        row["category"] = category
    try:
        path = (home or Path.home()) / ".local/state/saar-fighters/app-health.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            return
        if path.exists() and path.stat().st_size > 65536:
            path.replace(path.with_suffix(".previous"))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
    except OSError:
        pass  # Diagnostics must never prevent launching an app.
