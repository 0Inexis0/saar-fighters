#!/usr/bin/env python3
"""Install Brave through the existing Flatpak channel and set desktop defaults."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

APP_ID = "com.brave.Browser"


def desktop_home():
    import pwd
    return pwd.getpwnam("saar").pw_dir


def configure(run=subprocess.run, which=shutil.which):
    native = next((name for name in ("brave", "brave-browser", "brave-browser-stable") if which(name)), None)
    desktop = "brave-browser.desktop" if native else APP_ID + ".desktop"
    if not native:
        if not which("flatpak"):
            raise RuntimeError("Flatpak fehlt. Bitte zuerst die Systempakete aktualisieren.")
        installed = run(["flatpak", "info", "--system", APP_ID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if installed.returncode:
            run(["flatpak", "remote-add", "--system", "--if-not-exists", "flathub",
                 "https://flathub.org/repo/flathub.flatpakrepo"], check=True)
            run(["flatpak", "install", "--system", "--noninteractive", "flathub", APP_ID], check=True)
        run(["flatpak", "info", "--system", APP_ID], stdout=subprocess.DEVNULL, check=True)
    # Keep existing Firefox profiles and running sessions intact. No profile migration.
    home = desktop_home()
    run(["runuser", "-u", "saar", "--", "env", "HOME=" + home,
         "XDG_CONFIG_HOME=" + home + "/.config", "xdg-mime", "default", desktop,
         "text/html", "x-scheme-handler/http", "x-scheme-handler/https"], check=True)
    print("Brave ist installiert und als Standardbrowser eingerichtet.", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] or os.geteuid() != 0:
        raise SystemExit("Nur über das Systemupdate starten.")
    if not Path("/etc/saar-live").exists():
        configure()
