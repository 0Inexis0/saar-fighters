#!/usr/bin/env python3
"""Fixed maintenance operations. Recovery replaces only the desktop surface."""
import ast
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

SURFACE = (
    ("app", "opt/saar-fighters/app"),
    ("system/plasmoid", "usr/share/plasma/plasmoids/de.saarfighters.home"),
    ("system/plasmoid", "opt/saar-fighters/system/plasmoid"),
    ("system/desktoptheme/saar-olive", "usr/share/plasma/desktoptheme/saar-olive"),
    ("system/desktoptheme/saar-olive", "opt/saar-fighters/system/desktoptheme/saar-olive"),
    ("system/plasma-layout.js", "opt/saar-fighters/system/plasma-layout.js"),
    ("system/maximize-apps.js", "opt/saar-fighters/system/maximize-apps.js"),
    ("system/configure_display.py", "opt/saar-fighters/system/configure_display.py"),
)
TOOLS = (
    ("system/maintenance.py", "usr/local/libexec/saar-maintenance-admin.py", 0o755),
    ("system/saar-maintenance", "usr/local/libexec/saar-maintenance", 0o755),
    ("app/maintenance.py", "usr/local/libexec/saar-maintenance-ui.py", 0o755),
    ("system/de.saarfighters.maintenance.policy", "usr/share/polkit-1/actions/de.saarfighters.maintenance.policy", 0o644),
    ("system/de.saarfighters.Maintenance.desktop", "usr/share/applications/de.saarfighters.Maintenance.desktop", 0o644),
)


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_write(path, data, mode=0o644):
    if path.is_symlink():
        raise RuntimeError("Unerwartete Verknüpfung in der Wartungskonfiguration")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".saar-", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        staged.chmod(mode)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def revision(project):
    try:
        value = (project / ".revision").read_text().strip()
        if len(value) == 40 and all(c in "0123456789abcdef" for c in value):
            return value
    except OSError:
        pass
    return "Ältere Installation"


def validate_surface(source):
    if source.is_symlink() or not (source / "app/main.py").is_file():
        raise RuntimeError("Keine vollständige Sicherung der Oberfläche vorhanden.")
    manifest_file = source / ".surface-manifest.json"
    if manifest_file.exists():
        manifest = read_json(manifest_file)
        if not manifest or "app/main.py" not in manifest:
            raise RuntimeError("Die Prüfsummen der Sicherung fehlen.")
        for relative, expected in manifest.items():
            path = source / relative
            if Path(relative).is_absolute() or ".." in Path(relative).parts or not path.resolve().is_relative_to(source.resolve()):
                raise RuntimeError("Ungültiger Sicherungspfad")
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError("Die Sicherung stimmt nicht mit ihren Prüfsummen überein.")
    digest = hashlib.sha256((revision(source) + "\n").encode())
    checked = set()
    for relative, _ in SURFACE:
        path = source / relative
        if not path.exists():
            if relative in ("app", "system/plasmoid", "system/desktoptheme/saar-olive"):
                raise RuntimeError(f"Die Sicherung ist unvollständig: {relative}")
            continue  # Older desktops did not have these optional helpers.
        for entry in [path, *sorted(path.rglob("*"))] if path.is_dir() else [path]:
            if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
                raise RuntimeError("Die Sicherung enthält unzulässige Verknüpfungen oder Dateien.")
            if entry.suffix == ".py":
                tree = ast.parse(entry.read_text(encoding="utf-8"))
                if entry.parent == source / "app":
                    for node in ast.walk(tree):
                        names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                            [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                        for name in names:
                            module = name.split(".")[0]
                            if (module not in sys.stdlib_module_names and module not in {"PySide6", "dbus_next", "shiboken6"}
                                    and not (source / "app" / (module + ".py")).exists()
                                    and not (source / "app" / module / "__init__.py").exists()):
                                raise RuntimeError(f"Der Sicherung fehlt ein Oberflächenmodul: {module}")
            elif entry.suffix == ".json":
                json.loads(entry.read_text(encoding="utf-8"))
            elif entry.suffix == ".svg":
                ET.parse(entry)
            if entry.is_file() and entry not in checked and "__pycache__" not in entry.parts:
                checked.add(entry)
                digest.update(entry.relative_to(source).as_posix().encode() + b"\0")
                digest.update(hashlib.sha256(entry.read_bytes()).digest())
    return digest.hexdigest()


def refresh(root=Path("/")):
    state = root / "var/lib/saar-fighters-update"
    project = root / "opt/saar-fighters"
    backup = state / "previous"
    restored = read_json(project / ".surface-restored.json")
    backup_version = read_json(backup / ".surface-restored.json").get("revision", revision(backup))
    data = {"current": restored.get("revision", revision(project)), "previous": backup_version,
            "available": False, "reason": "Noch keine Sicherung vorhanden.",
            "restored_at": restored.get("at")}
    try:
        identity = validate_surface(backup)
        if (state / "recovery.json").exists():
            data["reason"] = "Ein unterbrochener Vorgang muss zuerst durch die Administration geprüft werden."
        elif restored.get("backup_id") == identity:
            data["reason"] = "Diese Sicherung wurde bereits wiederhergestellt."
        else:
            data.update(available=True, reason="", backup_id=identity)
    except (OSError, ValueError, SyntaxError, RuntimeError, ET.ParseError):
        if backup.exists():
            data["reason"] = "Die vorhandene Sicherung ist unvollständig oder beschädigt."
    public = root / "var/lib/saar-fighters"
    if public.is_symlink():
        raise RuntimeError("Ungültiges Statusverzeichnis")
    public.mkdir(parents=True, exist_ok=True, mode=0o755)
    public.chmod(0o755)
    atomic_write(public / "surface-status.json", json.dumps(data, ensure_ascii=False).encode())
    return data


def install_tools(root=Path("/")):
    project = root / "opt/saar-fighters"
    for source, destination, mode in TOOLS:
        atomic_write(root / destination, (project / source).read_bytes(), mode)
    return refresh(root)


def remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def restore_surface(root=Path("/"), expected=None):
    state = root / "var/lib/saar-fighters-update"
    source = state / "previous"
    project = root / "opt/saar-fighters"
    if (root / "etc/saar-live").exists():
        raise RuntimeError("Wiederherstellung ist nur auf einem installierten Rechner möglich.")
    if (state / "recovery.json").exists():
        raise RuntimeError("Ein vorheriger Vorgang wurde unterbrochen. Administration erforderlich.")
    identity = validate_surface(source)
    if expected is not None and expected != identity:
        raise RuntimeError("Die Sicherung hat sich geändert. Bitte den Status neu laden.")
    if read_json(project / ".surface-restored.json").get("backup_id") == identity:
        raise RuntimeError("Diese Sicherung wurde bereits wiederhergestellt.")
    records, committed = [], []
    journal = state / "recovery.json"
    marker = project / ".surface-restored.json"
    old_marker = marker.read_bytes() if marker.exists() else None
    try:
        for relative, destination in SURFACE:
            original = source / relative
            if not original.exists():
                continue
            target = root / destination
            staged = target.with_name(target.name + ".saar-restore-new")
            saved = target.with_name(target.name + ".saar-restore-old")
            if target.is_symlink() or staged.exists() or saved.exists() or staged.is_symlink() or saved.is_symlink():
                raise RuntimeError("Ein früherer Dateiaustausch ist noch nicht bereinigt.")
            target.parent.mkdir(parents=True, exist_ok=True)
            records.append((target, staged, saved, target.exists()))
            if original.is_dir():
                shutil.copytree(original, staged)
            else:
                shutil.copy2(original, staged)
        atomic_write(journal, json.dumps([[str(p) if isinstance(p, Path) else p for p in r] for r in records]).encode(), 0o600)
        for target, staged, saved, existed in records:
            committed.append((target, staged, saved, existed))
            if existed:
                target.rename(saved)
            staged.rename(target)
        backup_version = read_json(source / ".surface-restored.json").get("revision", revision(source))
        atomic_write(marker, json.dumps({"backup_id": identity, "revision": backup_version,
                     "at": datetime.now(timezone.utc).isoformat()}).encode())
    except BaseException:
        for target, staged, saved, existed in reversed(committed):
            if saved.exists():
                remove(target)
                saved.rename(target)
            elif not existed:
                remove(target)
        if old_marker is None:
            marker.unlink(missing_ok=True)
        else:
            atomic_write(marker, old_marker)
        for _, staged, _, _ in records:
            remove(staged)
        journal.unlink(missing_ok=True)
        raise
    # Retain the immediate pre-restore files until every replacement succeeded.
    for _, staged, saved, _ in records:
        remove(saved)
        remove(staged)
    journal.unlink()
    refresh(root)
    print("Oberfläche wiederhergestellt. Bitte den Rechner neu starten. Persönliche Daten und Systempakete wurden nicht verändert.")


def command(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=12,
                          env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})


def status(root=Path("/"), run=command):
    result = {"surface": read_json(root / "var/lib/saar-fighters/surface-status.json"),
              "live": (root / "etc/saar-live").exists(), "ssh": {"state": "unknown", "addresses": [],
              "disabled": (root / "etc/saar-fighters/ssh/disabled").exists()}}
    try:
        check = run(["systemctl", "show", "saar-sshd.service", "--property=ActiveState", "--value"])
        if check.returncode == 0:
            result["ssh"]["state"] = check.stdout.strip()
        addresses = run(["ip", "-j", "-4", "address", "show", "scope", "global"])
        networks = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
        for interface in json.loads(addresses.stdout or "[]"):
            for info in interface.get("addr_info", []):
                address = ipaddress.ip_address(info.get("local", "0.0.0.0"))
                if any(address in network for network in networks):
                    result["ssh"]["addresses"].append(str(address))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return result


def set_ssh(enabled, root=Path("/"), run=command):
    if (root / "etc/saar-live").exists():
        raise RuntimeError("Fernwartung ist im Live-System ausgeschaltet.")
    marker = root / "etc/saar-fighters/ssh/disabled"
    if not enabled:
        atomic_write(marker, b"Disabled in Saar-Fighters settings\n")
        result = run(["systemctl", "disable", "--now", "saar-sshd.service"])
        if result.returncode:
            raise RuntimeError("Fernwartung konnte nicht gestoppt werden.")
        print("Fernwartung ausgeschaltet. Diese Einstellung bleibt bei Updates erhalten.")
    else:
        old = marker.read_bytes() if marker.exists() else None
        marker.unlink(missing_ok=True)
        try:
            result = run(["/usr/bin/python", "-I", "/opt/saar-fighters/system/configure_ssh.py"])
            if result.returncode:
                raise RuntimeError("Fernwartung konnte nicht aktiviert werden. Bitte Systemupdate prüfen.")
        except BaseException:
            if old is not None:
                atomic_write(marker, old)
                run(["systemctl", "disable", "--now", "saar-sshd.service"])
            raise
        print("Fernwartung eingeschaltet.")


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("status", "install", "restore", "enable-ssh", "disable-ssh"):
        raise SystemExit("Unzulässige Wartungsaktion")
    action = args[0]
    if action == "restore":
        if len(args) != 2 or len(args[1]) != 64 or any(c not in "0123456789abcdef" for c in args[1]):
            raise SystemExit("Ungültige Sicherungskennung")
    elif len(args) != 1:
        raise SystemExit("Unzulässige Argumente")
    if action == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return
    if os.geteuid() != 0:
        raise SystemExit("Wartungspasswort erforderlich")
    if action == "install":
        install_tools()
    elif action == "restore":
        restore_surface(expected=args[1])
    else:
        set_ssh(action == "enable-ssh")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Wartung fehlgeschlagen: {error}", file=sys.stderr)
        sys.exit(1)
