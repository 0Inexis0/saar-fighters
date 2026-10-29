#!/usr/bin/env python3
"""Install the fixed club repository without running its installation scripts.

The entry point is root-only. Functions accept a filesystem root for isolated
transaction tests; the command line never accepts paths, repositories or refs.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

REPOSITORY = "https://github.com/0Inexis0/saar-fighters.git"
BRANCH = "main"
# Only these project-owned integration files are replaced. No account, boot,
# partition, network, authentication or desktop-preference setup is rerun.
INTEGRATIONS = (
    ("system/saar-update", "usr/local/libexec/saar-update", 0o755),
    ("system/update_custom.py", "usr/local/libexec/saar-update-custom.py", 0o755),
    ("system/de.saarfighters.update.policy", "usr/share/polkit-1/actions/de.saarfighters.update.policy", 0o644),
    ("system/de.saarfighters.Home.desktop", "usr/share/applications/de.saarfighters.Home.desktop", 0o644),
    ("system/plasmoid", "usr/share/plasma/plasmoids/de.saarfighters.home", None),
    ("system/desktoptheme/saar-olive", "usr/share/plasma/desktoptheme/saar-olive", None),
)
REQUIRED = (
    "system/configure_wallet.py",
    "app/system_settings.py", "app/system_status.py", "app/notifications.py", "system/energy_profile.py",
    "system/update_packages.py",
    "system/remove_tailscale.py",
    "system/configure_stability.py", "app/spotify_launcher.py",
    "system/playback_status.py", "app/runtime_health.py",
    "system/configure_browser.py", "app/browser.py",
    "app/maintenance.py", "system/maintenance.py", "system/saar-maintenance",
    "system/de.saarfighters.maintenance.policy", "system/de.saarfighters.Maintenance.desktop",
    "system/configure_ssh.py", "system/diagnose_firefox.py",
    "system/ssh/sshd_config", "system/ssh/saar-sshd.service", "system/ssh/support_ed25519.pub",
    "app/rocket.py", "app/rocket-launch/index.html", "app/rocket-launch/config.json",
    "app/rocket-launch/js/main.js", "app/rocket-launch/js/missile.js",
    "app/rocket-launch/js/ui.js", "app/rocket-launch/js/map.js", "app/rocket-launch/js/audio.js",
    "app/rocket-launch/css/base.css", "app/rocket-launch/css/layout.css", "app/rocket-launch/css/map.css",
    "app/rocket-launch/assets/world-map.svg",
    "app/rocket-launch/assets/Explosion - Sound Effect.mp3",
    "app/rocket-launch/assets/Tactical Nuke Test Countdown and Explosion Sound Effect.mp3",
    "system/configure_display.py",
    "app/slideshow.py", "app/idle_watch.py", "app/assets/slideshow/credits.json",
    "app/assets/slideshow/airsoft-shooter.jpg", "app/assets/slideshow/airsoft-squad.jpg",
    "app/assets/slideshow/airsoft-team.jpg",
    "app/main.py", "app/applications.py", "app/devices.py", "app/backend.py", "app/hardware.py", "app/brightness.py", "app/audio.py",
    "app/media.py", "app/media_content.py", "app/music_player.py",
    "app/assets/terrain.svg", "app/assets/home.svg", "app/assets/club-logo.gif",
    "installer/ui.py", "system/first-login.sh", "system/plasma-layout.js",
    "system/plasmoid/metadata.json", "system/plasmoid/contents/ui/main.qml",
    "system/desktoptheme/saar-olive/metadata.json",
    "system/desktoptheme/saar-olive/colors",
    "system/desktoptheme/saar-olive/widgets/panel-background.svg",
    "system/desktoptheme/saar-olive/widgets/tasks.svg",
)


def report(message):
    print(message, flush=True)


def fetch_checkout(destination):
    # Ignore inherited git config and disable interactive authentication/hooks.
    env = {"PATH": "/usr/bin:/bin", "HOME": str(destination.parent),
           "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
    try:
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "clone", "--depth=1",
                        "--single-branch", "--branch", BRANCH, "--", REPOSITORY,
                        str(destination)], env=env, check=True, timeout=180)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("GitHub-Download nicht möglich. Internetverbindung und "
                           "Lesezugriff auf das Update-Repository prüfen; "
                           "die eigene Oberfläche wurde nicht verändert.") from error
    revision = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"],
                                       env=env, text=True, timeout=15).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("Ungültige GitHub-Version")
    return revision


def validate_checkout(checkout):
    for name in REQUIRED + tuple(item[0] for item in INTEGRATIONS):
        if not (checkout / name).exists():
            raise RuntimeError(f"Update unvollständig: {name} fehlt")
    for folder in ("app", "system", "installer"):
        if (checkout / folder).is_symlink() or not (checkout / folder).is_dir():
            raise RuntimeError(f"Ungültiges Projektverzeichnis: {folder}")
        for path in (checkout / folder).rglob("*"):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise RuntimeError(f"Unzulässiger Dateityp: {path.relative_to(checkout)}")
            if path.suffix == ".py":
                ast.parse(path.read_text(), filename=str(path))
            elif path.suffix == ".json":
                json.loads(path.read_text())
            elif path.suffix in (".svg", ".policy"):
                ET.parse(path)
            elif path.suffix == ".sh" or path.name in ("saar-update", "saar-install", "saar-maintenance"):
                subprocess.run(["bash", "-n", str(path)], check=True, timeout=10)


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def copy(source, target, mode=None):
    if source.is_dir():
        shutil.copytree(source, target)
        for entry in [target, *target.rglob("*")]:
            entry.chmod(0o755 if entry.is_dir() or os.access(entry, os.X_OK) else 0o644)
    else:
        shutil.copyfile(source, target)
        target.chmod(mode or 0o644)


def install_checkout(checkout, revision, root=Path("/")):
    """Stage all replacements before touching installed files; rollback on error."""
    state = root / "var/lib/saar-fighters-update"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (state / "recovery.json").exists():
        raise RuntimeError("Vorheriges Update wurde unterbrochen. Administration muss recovery.json prüfen.")
    # Each sibling backup stays on the target filesystem for atomic renames.
    records = []
    committed = []
    project = root / "opt/saar-fighters"
    if not project.is_dir() or project.is_symlink():
        raise RuntimeError("Installierte Vereinsoberfläche fehlt oder ist kein Verzeichnis")
    version_file = project / ".revision"
    if (version_file.is_file() and version_file.read_text().strip() == revision
            and not (project / ".surface-restored.json").exists()):
        return False
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=state) as temp:
        payload = Path(temp) / "project"
        payload.mkdir()
        for folder in ("app", "system", "installer"):
            copy(checkout / folder, payload / folder)
        (payload / ".revision").write_text(revision + "\n")
        targets = [(payload, project, None)] + [
            (checkout / src, root / dst, mode) for src, dst, mode in INTEGRATIONS]
        # Preserve the live-only installer boundary on installed machines.
        if (root / "etc/saar-live").exists():
            targets.append((checkout / "installer/saar-install", root / "usr/local/libexec/saar-install", 0o755))
        try:
            for source, target, mode in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                staged = target.with_name(target.name + ".saar-new")
                backup = target.with_name(target.name + ".saar-previous")
                if staged.exists() or backup.exists() or staged.is_symlink() or backup.is_symlink():
                    raise RuntimeError(f"Unbereinigtes Update bei {target}")
                if target.is_symlink():
                    raise RuntimeError(f"Unerwartete Verknüpfung: {target}")
                records.append((target, staged, backup, target.exists()))
                copy(source, staged, mode)
            # Reserve space for the retained backup before changing the system.
            previous_new = Path(temp) / "previous"
            shutil.copytree(project, previous_new)
            manifest = {p.relative_to(previous_new).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in previous_new.rglob("*") if p.is_file()
                        and "__pycache__" not in p.parts and p.name != ".surface-manifest.json"}
            (previous_new / ".surface-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal = state / "recovery.json"
            journal.write_text(json.dumps([[str(p) if isinstance(p, Path) else p for p in row]
                                           for row in records], indent=2))
            for target, staged, backup, existed in records:
                committed.append((target, staged, backup, existed))
                if existed:
                    target.rename(backup)
                staged.rename(target)
        except BaseException:
            # Leave the journal and backups intact if rollback itself fails.
            for target, staged, backup, existed in reversed(committed):
                if backup.exists():
                    remove(target)
                    backup.rename(target)
                elif not existed:
                    remove(target)
            for _, staged, _, _ in records:
                remove(staged)
            (state / "recovery.json").unlink(missing_ok=True)
            raise
        # Retain the previous project before deleting any transaction backups.
        # A cleanup failure keeps recovery.json, so the next update stops safely.
        previous = state / "previous"
        remove(previous)
        previous_new.rename(previous)
        (state / "current-revision").write_text(revision + "\n")
        for _, staged, backup, _ in records:
            remove(backup)
            remove(staged)
        (state / "recovery.json").unlink()
    return True


def main():
    if sys.argv[1:] not in ([], ["--check"]):
        raise SystemExit("Nur über die Update-Schaltfläche starten.")
    check_only = sys.argv[1:] == ["--check"]
    if not check_only and os.geteuid() != 0:
        raise SystemExit("Administratorfreigabe erforderlich.")
    report("Saar-Fighters: GitHub/main wird heruntergeladen …")
    with tempfile.TemporaryDirectory(prefix="saar-github-") as temporary:
        checkout = Path(temporary) / "source"
        revision = fetch_checkout(checkout)
        report(f"Saar-Fighters: Version {revision[:12]} wird geprüft …")
        validate_checkout(checkout)
        if check_only:
            report("Prüfung erfolgreich. Es wurde nichts installiert.")
            return
        installed = install_checkout(checkout, revision)
    if installed:
        report(f"Saar-Fighters {revision[:12]} installiert. Oberfläche und Taskleiste werden beim Neustart aktiviert.")
    else:
        report(f"Saar-Fighters {revision[:12]} ist bereits aktuell.")
    # Also usable independently of pacman when system package updates fail.
    subprocess.run(["/usr/bin/python", "-I", "/opt/saar-fighters/system/maintenance.py", "install"], check=True)
    subprocess.run(["/usr/bin/python", "-I", "/opt/saar-fighters/system/remove_tailscale.py"], check=True)
    subprocess.run(["/usr/bin/python", "-I", "/opt/saar-fighters/system/configure_browser.py"], check=True)
    subprocess.run(["runuser", "-u", "saar", "--", "/usr/bin/python", "-I", "/opt/saar-fighters/system/configure_wallet.py"], check=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        report(f"Saar-Fighters-Update fehlgeschlagen: {error}")
        sys.exit(1)
