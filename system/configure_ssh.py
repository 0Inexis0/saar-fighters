#!/usr/bin/env python3
"""Apply the explicitly requested LAN maintenance access after a system update."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SERVICE = "saar-sshd.service"
NETWORKS = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
SUDOERS = 'wartung ALL=(root) NOPASSWD: /usr/local/libexec/saar-diagnose-firefox ""\n'


def public_key(text):
    fields = text.strip().split()
    if len(fields) not in (2, 3) or fields[0] != "ssh-ed25519":
        raise ValueError("Ungültiger SSH-Wartungsschlüssel")
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except ValueError as error:
        raise ValueError("Ungültiger SSH-Wartungsschlüssel") from error
    if len(blob) != 51 or blob[:19] != b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20":
        raise ValueError("Ungültiger SSH-Wartungsschlüssel")
    return "ssh-ed25519 " + fields[1] + " saar-fighters-support\n"


def run(args):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=60,
                          env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})


def local_addresses(data):
    addresses = set()
    for interface in data:
        for info in interface.get("addr_info", []):
            try:
                address = ipaddress.ip_address(info.get("local", ""))
            except ValueError:
                continue
            if any(address in network for network in NETWORKS):
                addresses.add(str(address))
    return sorted(addresses)


def configure(root=Path("/"), command=run):
    if (root / "etc/saar-live").exists():
        print("SSH-Fernwartung bleibt im Live-System ausgeschaltet.", flush=True)
        return False
    if not (root / "var/lib/saar-base-ready").is_file():
        raise RuntimeError("Keine eingerichtete Saar-Fighters-Installation")
    directory = root / "etc/saar-fighters/ssh"
    if (directory / "disabled").exists():
        command(["systemctl", "disable", "--now", SERVICE])
        print("SSH-Fernwartung wurde durch die Administration deaktiviert.", flush=True)
        return False
    command(["id", "wartung"])
    source = root / "opt/saar-fighters/system"
    key = public_key((source / "ssh/support_ed25519.pub").read_text(encoding="utf-8"))
    directory.mkdir(parents=True, exist_ok=True, mode=0o755)
    # sshd drops privileges when checking authorized_keys; all users may read the
    # public key, but only root may replace it. The host private key stays 0600.
    if directory.is_symlink():
        raise RuntimeError("SSH-Konfiguration darf keine Verknüpfung sein")
    directory.chmod(0o755)
    host_key = directory / "host_ed25519"
    if host_key.is_symlink():
        raise RuntimeError("Ungültiger SSH-Hostschlüssel")
    if not host_key.exists():
        command(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(host_key)])
    host_key.chmod(0o600)
    contents = {
        directory / "authorized_keys": (key.encode(), 0o644),
        directory / "sshd_config": ((source / "ssh/sshd_config").read_bytes(), 0o644),
        root / "etc/systemd/system" / SERVICE: ((source / "ssh" / SERVICE).read_bytes(), 0o644),
        root / "usr/local/libexec/saar-diagnose-firefox": ((source / "diagnose_firefox.py").read_bytes(), 0o755),
        root / "etc/sudoers.d/60-saar-firefox-diagnose": (SUDOERS.encode(), 0o440),
    }
    changed = False
    # Stage each file beside its destination, including on separate /usr mounts.
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=directory) as temporary:
        staged = []
        previous = []
        try:
            for index, (target, (content, mode)) in enumerate(contents.items()):
                if target.is_symlink():
                    raise RuntimeError(f"Unerwartete Verknüpfung: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, name = tempfile.mkstemp(prefix=".saar-ssh-", dir=target.parent)
                candidate = Path(name)
                staged.append((target, candidate, mode))
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                candidate.chmod(mode)
            command(["sshd", "-t", "-f", str(staged[1][1])])
            command(["visudo", "-cf", str(staged[4][1])])
            for target, candidate, mode in staged:
                old = (target.read_bytes(), target.stat().st_mode & 0o777) if target.exists() else None
                previous.append((target, old))
                if old is None or old[0] != candidate.read_bytes():
                    os.replace(candidate, target)
                    changed = True
                target.chmod(mode)
        except BaseException:
            for target, old in reversed(previous):
                if old is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(old[0])
                    target.chmod(old[1])
            raise
        finally:
            for _, candidate, _ in staged:
                if candidate.exists():
                    candidate.chmod(0o600)
                candidate.unlink(missing_ok=True)
    command(["systemctl", "daemon-reload"])
    command(["systemctl", "enable", "--now", SERVICE])
    if changed:
        command(["systemctl", "reload", SERVICE])
    command(["systemctl", "is-active", "--quiet", SERVICE])
    print("SSH-Fernwartung aktiv: nur Wartungsschlüssel, LAN und Tailscale-IPv4, Port 2222.", flush=True)
    try:
        data = json.loads(command(["ip", "-j", "-4", "address", "show", "scope", "global"]).stdout)
        for address in local_addresses(data):
            print(f"Verbindung: ssh -p 2222 wartung@{address}", flush=True)
        fingerprint = command(["ssh-keygen", "-lf", str(host_key) + ".pub"]).stdout.strip()
        print("Hostschlüssel: " + fingerprint, flush=True)
    except (subprocess.SubprocessError, OSError, ValueError):
        print("SSH läuft; die lokale Adresse konnte nicht angezeigt werden.", flush=True)
    return True


def main():
    if sys.argv[1:] or os.geteuid() != 0:
        raise SystemExit("Nur über den System-Update-Knopf starten.")
    try:
        # This hook also runs from the already installed SSH updater on its first
        # update, before that older updater knows about the new maintenance tools.
        subprocess.run(["/usr/bin/python", "-I", "/opt/saar-fighters/system/maintenance.py", "install"], check=True)
        configure()
    except Exception as error:
        print(f"SSH-Einrichtung fehlgeschlagen: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
