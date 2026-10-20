#!/usr/bin/env python3
"""Prepare a fresh Arch/Boxes VM; never touches existing virtual disks."""
import argparse
import hashlib
import secrets
import subprocess
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = "saar-fighters-os"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if hashlib.file_digest(args.base.open("rb"), "sha256").hexdigest() != args.sha256:
        raise SystemExit("Base image checksum does not match")
    out = ROOT / "build/vm"
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    disk = Path.home() / ".local/share/gnome-boxes/images" / f"{NAME}.qcow2"
    if disk.exists():
        raise SystemExit(f"Refusing to replace {disk}")
    disk.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "--reflink=auto", "--sparse=always", str(args.base), str(disk)], check=True)
    subprocess.run(["qemu-img", "resize", str(disk), "40G"], check=True)
    password = secrets.token_urlsafe(18)
    # Hash stdin with openssl; the password is never an argv value.
    hashed = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input=password,
                            text=True, capture_output=True, check=True).stdout.strip()
    creds = out / "credentials.txt"
    creds.write_text(f"VM administrator: wartung\nPassword: {password}\n")
    creds.chmod(0o600)
    config = {
        "hostname": NAME, "manage_etc_hosts": True,
        "users": [
            {"name": "saar", "gecos": "Saar-Fighters AV", "lock_passwd": True,
             "groups": ["audio", "video"], "shell": "/bin/bash"},
            {"name": "wartung", "gecos": "Wartung", "lock_passwd": False,
             "passwd": hashed, "groups": ["wheel"], "shell": "/bin/bash"},
        ],
        "disable_root": True, "ssh_pwauth": False,
        "growpart": {"mode": "auto", "devices": ["/"], "ignore_growroot_disabled": False},
        "resize_rootfs": True,
        "write_files": [
            {"path": "/root/saar-bootstrap.sh", "permissions": "0700",
             "content": (ROOT / "system/bootstrap.sh").read_text()},
            {"path": "/etc/systemd/system/systemd-time-wait-sync.service.d/timeout.conf",
             "content": "[Service]\nTimeoutStartSec=30\n"},
        ],
        "bootcmd": [
            ["systemctl", "daemon-reload"],
            ["systemctl", "restart", "--no-block", "systemd-time-wait-sync.service"],
        ],
        "runcmd": [["bash", "/root/saar-bootstrap.sh"]],
    }
    (out / "user-data").write_text("#cloud-config\n" + yaml.safe_dump(config))
    (out / "user-data").chmod(0o600)
    (out / "meta-data").write_text(f"instance-id: {NAME}-{uuid.uuid4()}\nlocal-hostname: {NAME}\n")
    seed = out / "seed.iso"
    subprocess.run(["genisoimage", "-quiet", "-output", str(seed), "-volid", "CIDATA",
                    "-joliet", "-rock", str(out / "user-data"), str(out / "meta-data")], check=True)
    seed.chmod(0o600)
    ET.register_namespace("boxes", "https://wiki.gnome.org/Apps/Boxes")
    domain = ET.fromstring(f"""<domain type="kvm">
      <name>{NAME}</name><uuid>{uuid.uuid4()}</uuid><title>Saar-Fighters OS</title>
      <metadata><boxes:gnome-boxes xmlns:boxes="https://wiki.gnome.org/Apps/Boxes"><boxes:os-state>installed</boxes:os-state></boxes:gnome-boxes></metadata>
      <memory unit="MiB">4096</memory><vcpu>4</vcpu>
      <os><type arch="x86_64" machine="q35">hvm</type><boot dev="hd"/></os>
      <features><acpi/><apic/></features><cpu mode="host-passthrough"/>
      <clock offset="utc"/><on_poweroff>destroy</on_poweroff><on_reboot>restart</on_reboot>
      <devices><emulator>/usr/bin/qemu-system-x86_64</emulator>
      <disk type="file" device="disk"><driver name="qemu" type="qcow2" discard="unmap"/>
        <source file="{disk}"/><target dev="vda" bus="virtio"/></disk>
      <disk type="file" device="cdrom"><driver name="qemu" type="raw"/>
        <source file="{seed}"/><target dev="sda" bus="sata"/><readonly/></disk>
      <interface type="user"><model type="virtio"/></interface>
      <controller type="usb" model="qemu-xhci"/>
      <serial type="pty"><target port="0"/></serial><console type="pty"><target type="serial" port="0"/></console>
      <channel type="unix"><target type="virtio" name="org.qemu.guest_agent.0"/></channel>
      <channel type="spicevmc"><target type="virtio" name="com.redhat.spice.0"/></channel>
      <input type="tablet" bus="usb"/><graphics type="spice"><listen type="none"/><gl enable="no"/></graphics>
      <video><model type="virtio" heads="1" primary="yes"><acceleration accel3d="no"/></model></video>
      <sound model="ich9"/><audio id="1" type="spice"/>
      <rng model="virtio"><backend model="random">/dev/urandom</backend></rng>
      </devices></domain>""")
    ET.indent(domain)
    xml = out / "domain.xml"
    ET.ElementTree(domain).write(xml, encoding="unicode")
    print(f"Prepared {xml}\nCredentials stored privately in {creds}")


if __name__ == "__main__":
    main()
