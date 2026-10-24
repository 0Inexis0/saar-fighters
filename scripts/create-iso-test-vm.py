#!/usr/bin/env python3
"""Create an isolated empty-disk ISO test VM, never overwrite an existing VM/disk."""
import argparse
from pathlib import Path
import shutil
import subprocess
import uuid
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("iso", type=Path)
parser.add_argument("--firmware", choices=["bios", "uefi"], required=True)
parser.add_argument("--name", help="Unique saar- test VM name for a new release")
parser.add_argument("--offline", action="store_true", help="Start with the virtual network cable disconnected")
args = parser.parse_args()
iso = args.iso.resolve(strict=True)
name = args.name or "saar-iso-test-" + args.firmware
if not name.startswith("saar-") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
    raise SystemExit("Test name must start with saar- and contain only lowercase letters, digits and hyphens")
existing = subprocess.run(["virsh", "-c", "qemu:///session", "dominfo", name], capture_output=True)
if existing.returncode == 0:
    raise SystemExit("Test-VM existiert bereits. Zuerst den vorhandenen Teststand prüfen.")
out = ROOT / "build" / name
out.mkdir(parents=True, exist_ok=False)
images = Path.home() / ".local/share/gnome-boxes/images"
images.mkdir(parents=True, exist_ok=True)
disks = [images / f"{name}-{suffix}.qcow2" for suffix in ("target", "keep")]
if any(p.exists() for p in disks):
    raise SystemExit("Vorhandene Testlaufwerke werden nicht überschrieben.")
for disk in disks:
    subprocess.run(["qemu-img", "create", "-f", "qcow2", str(disk), "40G"], check=True)
subprocess.run(["qemu-io", "-f", "qcow2", "-c", "write -P 0x5a 0 4096", str(disks[1])], check=True)
shutil.copyfile(disks[1], out / "keep-reference.qcow2")
root = ET.fromstring(f'''<domain type="kvm">
<name>{name}</name><uuid>{uuid.uuid4()}</uuid><title>Saar-Fighters Installation {args.firmware.upper()}</title>
<memory unit="MiB">4096</memory><vcpu>4</vcpu>
<os><type arch="x86_64" machine="q35">hvm</type><boot dev="cdrom"/><boot dev="hd"/><bootmenu enable="yes"/></os>
<features><acpi/><apic/></features><cpu mode="host-passthrough"/>
<clock offset="utc"/><on_poweroff>destroy</on_poweroff><on_reboot>restart</on_reboot>
<devices><emulator>/usr/bin/qemu-system-x86_64</emulator>
<interface type="user"><model type="virtio"/></interface>
<controller type="usb" model="qemu-xhci"/>
<serial type="pty"><target port="0"/></serial><console type="pty"><target type="serial" port="0"/></console>
<channel type="unix"><target type="virtio" name="org.qemu.guest_agent.0"/></channel>
<channel type="spicevmc"><target type="virtio" name="com.redhat.spice.0"/></channel>
<input type="tablet" bus="usb"/><graphics type="spice"><listen type="none"/><gl enable="no"/></graphics>
<video><model type="virtio" heads="1" primary="yes"><acceleration accel3d="no"/></model></video>
<sound model="ich9"/><audio id="1" type="spice"/>
<rng model="virtio"><backend model="random">/dev/urandom</backend></rng>
</devices></domain>''')
devices = root.find("devices")
if args.offline:
    ET.SubElement(devices.find("interface"), "link", state="down")
for index, disk in enumerate(disks):
    node = ET.SubElement(devices, "disk", type="file", device="disk")
    ET.SubElement(node, "driver", name="qemu", type="qcow2", discard="unmap")
    ET.SubElement(node, "source", file=str(disk))
    ET.SubElement(node, "target", dev="vda" if index == 0 else "vdb", bus="virtio")
    ET.SubElement(node, "serial").text = "SAAR_INSTALL_TARGET" if index == 0 else "SAAR_KEEP_UNCHANGED"
node = ET.SubElement(devices, "disk", type="file", device="cdrom")
ET.SubElement(node, "driver", name="qemu", type="raw")
ET.SubElement(node, "source", file=str(iso))
ET.SubElement(node, "target", dev="sda", bus="sata")
ET.SubElement(node, "readonly")
if args.firmware == "uefi":
    choices = [("/usr/share/edk2/x64/OVMF_CODE.4m.fd", "/usr/share/edk2/x64/OVMF_VARS.4m.fd"),
               ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd")]
    code, variables = next(pair for pair in choices if all(Path(p).exists() for p in pair))
    nvram = out / "nvram.fd"
    shutil.copyfile(variables, nvram)
    ET.SubElement(root.find("os"), "loader", readonly="yes", type="pflash").text = code
    ET.SubElement(root.find("os"), "nvram").text = str(nvram)
ET.indent(root)
xml = out / "domain.xml"
ET.ElementTree(root).write(xml, encoding="unicode")
subprocess.run(["virsh", "-c", "qemu:///session", "define", str(xml)], check=True)
print(f"Vorbereitet: {name}. Start: virsh -c qemu:///session start {name}")
