#!/usr/bin/env python3
"""Undo the old installer wallet opt-out once, without touching stored secrets."""
import os
from pathlib import Path
import subprocess
import sys


def configure(config_dir, state_dir, run=subprocess.run):
    marker = state_dir / "saar-fighters/kwallet-enabled-v1"
    if marker.exists():
        return False
    config = config_dir / "kwalletrc"
    backup = config_dir / "kwalletrc.before-saar-wallet-fix"
    if config.is_symlink() or backup.is_symlink() or marker.is_symlink():
        raise RuntimeError("Unerwartete Verknüpfung in der Wallet-Konfiguration")
    config_dir.mkdir(parents=True, exist_ok=True)
    if config.exists() and not backup.exists():
        with backup.open("xb") as stream:
            stream.write(config.read_bytes())
        backup.chmod(0o600)
    run(["kwriteconfig6", "--file", str(config), "--group", "Wallet", "--key", "Enabled", "true"], check=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("Old installer opt-out corrected; future user choices are preserved.\n")
    marker.chmod(0o600)
    return True


if __name__ == "__main__":
    import pwd
    if sys.argv[1:] or pwd.getpwuid(os.getuid()).pw_name != "saar":
        raise SystemExit("Nur im Vereinsbenutzer ausführen.")
    configure(Path.home() / ".config", Path.home() / ".local/state")
