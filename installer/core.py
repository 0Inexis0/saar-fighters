"""Read-only disk inventory and validation, shared with the installer UI."""
import hashlib
import json
import subprocess

MIN_DISK_BYTES = 32_000_000_000


def descendants(device):
    yield device
    for child in device.get("children", []):
        yield from descendants(child)


def candidates(tree):
    result = []
    for device in tree.get("blockdevices", []):
        if device.get("type") != "disk" or device.get("ro") or int(device.get("size", 0)) < MIN_DISK_BYTES:
            continue
        children = list(descendants(device))
        # Includes the ISO's USB device, mounted filesystems, active swap and LVM.
        if any(any(node.get("mountpoints") or []) or node.get("type") not in ("disk", "part")
               for node in children):
            continue
        identity = hashlib.sha256(json.dumps({key: device.get(key) for key in
            ("name", "size", "serial", "wwn", "maj:min", "model")}, sort_keys=True).encode()).hexdigest()
        result.append({"path": device["name"], "size": int(device["size"]),
                       "model": (device.get("model") or "Laufwerk").strip(),
                       "serial": (device.get("serial") or "").strip(), "identity": identity})
    return result


def disks():
    data = subprocess.run(["lsblk", "--json", "--bytes", "--paths", "--output",
        "NAME,TYPE,SIZE,MODEL,SERIAL,WWN,MAJ:MIN,RO,MOUNTPOINTS"], check=True, capture_output=True, text=True)
    return candidates(json.loads(data.stdout))


def validate_request(request, available):
    target = next((disk for disk in available if disk["path"] == request.get("disk")
                   and disk["identity"] == request.get("identity")), None)
    if not target:
        raise ValueError("Das gewählte Laufwerk ist nicht mehr verfügbar oder wird verwendet. Bitte neu auswählen.")
    if request.get("confirm_erase") != target["identity"]:
        raise ValueError("Das Löschen des ausgewählten Laufwerks wurde nicht bestätigt.")
    password = request.get("admin_password", "")
    if not isinstance(password, str) or not 10 <= len(password) <= 128 or any(c in password for c in "\n\r\0"):
        raise ValueError("Das Wartungspasswort muss 10 bis 128 Zeichen enthalten, ohne Zeilenumbrüche.")
    return target
