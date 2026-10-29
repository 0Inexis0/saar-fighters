#!/usr/bin/env python3
"""One-time migration back to LAN-only maintenance."""
import os
from pathlib import Path
import subprocess
import sys


def remove(root=Path("/"), run=subprocess.run):
    if (root / "etc/saar-live").exists():
        return
    config = root / "etc/saar-fighters/ssh/sshd_config"
    if config.is_file() and "100.64.0.0/10" in config.read_text():
        # Reuse validation, rollback, and the permanent SSH opt-out marker.
        run(["/usr/bin/python", "-I", "/opt/saar-fighters/system/configure_ssh.py"], check=True)
    installed = run(["pacman", "-Q", "tailscale"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if installed.returncode == 0:
        run(["systemctl", "disable", "--now", "tailscaled.service"], check=True)
        run(["pacman", "-R", "--noconfirm", "tailscale"], check=True)
        print("Tailscale entfernt. Fernwartung ist nur noch im lokalen Netz verfügbar.", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] or os.geteuid() != 0:
        raise SystemExit("Nur über das Systemupdate starten.")
    remove()
