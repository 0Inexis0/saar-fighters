#!/usr/bin/env python3
"""Apply a reversible Firefox rendering workaround without touching profiles."""
import json
import os
from pathlib import Path
import sys
import tempfile


def configure(root=Path("/")):
    if (root / "etc/saar-live").exists():
        return False
    policy = root / "usr/lib/firefox/distribution/policies.json"
    if policy.resolve() != policy.absolute():
        raise RuntimeError("Unerwartete Verknüpfung im Firefox-Policy-Pfad")
    original = policy.read_bytes() if policy.exists() else b'{"policies": {}}\n'
    data = json.loads(original)
    if not isinstance(data, dict) or not isinstance(data.get("policies", {}), dict):
        raise RuntimeError("Ungültige Firefox-Policy; vorhandene Datei bleibt unverändert.")
    policies = data.setdefault("policies", {})
    if policies.get("HardwareAcceleration") is False:
        return False
    backup = policy.with_name("policies.before-stability.json")
    if backup.is_symlink():
        raise RuntimeError("Ungültiger Sicherungspfad")
    policy.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        backup.write_bytes(original)
        backup.chmod(0o644)
    policies["HardwareAcceleration"] = False
    fd, name = tempfile.mkstemp(prefix=".saar-policy-", dir=policy.parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        staged.chmod(0o644)
        os.replace(staged, policy)
    finally:
        staged.unlink(missing_ok=True)
    print("Firefox: Softwaredarstellung vorbereitet. Wirksam nach vollständigem Browser-Neustart.")
    return True


if __name__ == "__main__":
    if sys.argv[1:] or os.geteuid() != 0:
        raise SystemExit("Nur über das Systemupdate starten.")
    configure()
