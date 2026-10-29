"""Local, unprivileged system facts. Missing facts are never reported as zero."""
from pathlib import Path
import json
import platform
import shutil


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def snapshot(root=Path("/")):
    root = Path(root)
    memory = {}
    for line in read_text(root / "proc/meminfo").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            memory[parts[0].rstrip(":")] = int(parts[1]) * 1024
    total, available = memory.get("MemTotal"), memory.get("MemAvailable")
    try:
        disk = shutil.disk_usage(root)
        disk_total, disk_free = disk.total, disk.free
    except OSError:
        disk_total = disk_free = None
    version = ""
    for name in ("opt/saar-fighters/.surface-restored.json",):
        try:
            version = json.loads(read_text(root / name)).get("revision", "")
        except (ValueError, AttributeError):
            pass
        if version:
            break
    return {"kernel": platform.release(), "architecture": platform.machine(),
            "version": version or read_text(root / "opt/saar-fighters/.revision") or "Nicht erfasst",
            "memory_total": total, "memory_used": total - available if total and available is not None else None,
            "disk_total": disk_total, "disk_free": disk_free,
            "last_update": read_text(root / "var/lib/saar-last-update") or "Noch kein erfolgreicher Updatezeitpunkt erfasst"}


def gib(value):
    return f"{value / 1024**3:.1f} GiB" if value is not None else "Nicht verfügbar"
