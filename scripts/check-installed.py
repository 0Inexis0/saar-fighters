#!/usr/bin/env python3
"""Read-only post-install checks via the selected test VM's QEMU agent."""
import base64
import json
import time
from guest import call

code = r'''
import json, os, pathlib, subprocess
P=pathlib.Path
checks={}
def command(*args):
 return subprocess.run(args, capture_output=True, text=True)
checks["installed_root_ext4"] = command("findmnt", "-n", "-o", "FSTYPE", "/").stdout.strip() == "ext4"
checks["live_marker_removed"] = not P("/etc/saar-live").exists()
checks["live_sudo_rule_removed"] = not P("/etc/sudoers.d/90-saar-live").exists()
checks["installer_entry_removed"] = not P("/usr/local/libexec/saar-install").exists()
checks["normal_initramfs"] = not P("/etc/mkinitcpio.conf.d/archiso.conf").exists()
checks["german_locale"] = "de_DE.utf8" in command("locale", "-a").stdout
checks["sddm_running"] = command("systemctl", "is-active", "sddm").returncode == 0
checks["networkmanager_running"] = command("systemctl", "is-active", "NetworkManager").returncode == 0
saar_uid = command("id", "-u", "saar").stdout.strip()
checks["home_running"] = command("runuser", "-u", "saar", "--", "env", f"XDG_RUNTIME_DIR=/run/user/{saar_uid}",
 f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{saar_uid}/bus", "systemctl", "--user", "is-active", "saar-home").returncode == 0
checks["custom_updater_installed"] = P("/usr/local/libexec/saar-update-custom.py").is_file()
checks["public_updates_without_login"] = "https://github.com/0Inexis0/saar-fighters.git" in P("/usr/local/libexec/saar-update-custom.py").read_text() if checks["custom_updater_installed"] else False
checks["modern_icons_present"] = all(P("/opt/saar-fighters/app/assets/fluent", name + ".svg").is_file() for name in ("folder", "wifi", "sound", "bluetooth"))
checks["git_installed"] = command("git", "--version").returncode == 0
checks["spotify_installed"] = command("flatpak", "info", "--system", "com.spotify.Client").returncode == 0
checks["brave_installed"] = command("flatpak", "info", "--system", "com.brave.Browser").returncode == 0
runtime = P("/var/lib/flatpak/runtime/org.freedesktop.Platform/x86_64")
checks["flatpak_runtime_executable"] = any(os.access(p, os.X_OK) for p in runtime.glob("*/active/files/bin/ldconfig"))
checks["saar_not_administrator"] = command("runuser", "-u", "saar", "--", "sudo", "-n", "true").returncode != 0
shadow=command("getent", "shadow", "wartung").stdout.split(":")
checks["wartung_has_password"] = len(shadow)>1 and shadow[1].startswith("$")
checks["uefi_bootloader_exists"] = P("/boot/efi/EFI/BOOT/BOOTX64.EFI").is_file()
checks["swap_active"] = "/swapfile" in command("swapon", "--show", "--noheadings").stdout
secret=P("/run/saar-test-password")
if secret.exists():
 result=subprocess.run(["runuser", "-u", "wartung", "--", "sudo", "-S", "-k", "true"],
  input=secret.read_text().strip()+"\n", capture_output=True, text=True)
 checks["wartung_authentication"] = result.returncode == 0
 secret.unlink()
print(json.dumps({"firmware": "UEFI" if P("/sys/firmware/efi").exists() else "BIOS", "checks":checks},ensure_ascii=False))
raise SystemExit(0 if all(checks.values()) else 1)
'''
pid = call({"execute": "guest-exec", "arguments": {
    "path": "/usr/bin/python", "arg": ["-c", code], "capture-output": True}})["pid"]
for _ in range(60):
    result = call({"execute": "guest-exec-status", "arguments": {"pid": pid}})
    if result.get("exited"):
        for key in ("out-data", "err-data"):
            if key in result:
                print(base64.b64decode(result[key]).decode(), end="")
        raise SystemExit(result.get("exitcode", 1))
    time.sleep(1)
raise SystemExit("Post-install checks timed out")
