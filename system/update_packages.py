#!/usr/bin/env python3
"""Full Arch upgrade, with one isolated retry for package signature failures."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def run_upgrade(extra=()):
    command = ["pacman", *extra, "-Syu", "--needed", "--noconfirm", "git", "openssh"]
    signature_error = False
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", env={**os.environ, "LC_ALL": "C"}) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            if "(PGP signature)" in line or ("signature from" in line and "is invalid" in line):
                signature_error = True
        return process.wait(), signature_error


def mirror_config(source):
    # Use a temporary configuration; keep repositories, SigLevel, and the user's
    # permanent mirror list unchanged. Do not rewrite custom includes.
    pattern = r"(?m)^\s*Include\s*=\s*/etc/pacman\.d/mirrorlist\s*$"
    result, count = re.subn(pattern, "Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch", source)
    if not count:
        raise RuntimeError("Eigene Paketserver-Konfiguration: automatischer Serverwechsel nicht möglich.")
    return result


def upgrade():
    code, signature_error = run_upgrade()
    if code == 0:
        return
    if not signature_error:
        raise RuntimeError("Paketupdate fehlgeschlagen. Siehe Ausgabe oben.")
    print("Signaturprüfung fehlgeschlagen. Ein neuer Versuch lädt die Pakete von einem anderen Server in einen leeren Cache. Die Signaturprüfung bleibt aktiv.", flush=True)
    config = mirror_config(Path("/etc/pacman.conf").read_text())
    with tempfile.TemporaryDirectory(prefix="saar-package-retry-", dir="/var/cache/pacman") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        path = directory / "pacman.conf"
        path.write_text(config)
        cache = directory / "packages"
        cache.mkdir(mode=0o755)
        code, _ = run_upgrade(["--config", str(path), "--cachedir", str(cache), "-yy"])
    if code:
        raise RuntimeError("Auch der neue Download wurde abgelehnt. Keine Signaturprüfung wurde umgangen.")


if __name__ == "__main__":
    if sys.argv[1:] or os.geteuid() != 0:
        raise SystemExit("Nur über die Update- oder Fernwartungsseite starten.")
    try:
        upgrade()
    except Exception as error:
        print(f"Systemupdate fehlgeschlagen: {error}", flush=True)
        sys.exit(1)
