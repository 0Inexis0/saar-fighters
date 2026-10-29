"""Apply an explicit per-user choice; never needs root or changes lid actions."""
import json
from pathlib import Path
import subprocess
import sys
from configure_display import configure


def apply(profile, config_dir):
    if profile not in ("club", "laptop", "custom"):
        raise ValueError("Unbekanntes Energieprofil")
    configure(config_dir, profile)
    path = Path(config_dir) / "saar-fighters/energy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"profile": profile}), encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("Bitte genau ein Energieprofil wählen.")
        apply(sys.argv[1], Path.home() / ".config")
        result = subprocess.run(["systemctl", "--user", "restart", "plasma-powerdevil.service"],
                                timeout=12, capture_output=True)
        if result.returncode:
            raise RuntimeError("Profil gespeichert. Der Energiedienst konnte nicht neu geladen werden. Bitte abmelden und erneut anmelden.")
        print("Energieprofil gespeichert und Energiedienst neu geladen.")
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error))
        sys.exit(1)
