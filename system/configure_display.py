"""Keep the club display on, including after updates of existing installations."""
import configparser
from pathlib import Path
import shutil


def configure(config_dir, profile=None):
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    preference = config_dir / "saar-fighters/energy.json"
    # Once the user chooses a profile, login must not overwrite their settings.
    if profile is None and preference.exists():
        return False
    if profile not in (None, "club", "laptop", "custom"):
        raise ValueError("Unbekanntes Energieprofil")
    if profile == "custom":
        return False
    changed = False
    for filename in ("powerdevilrc", "kscreenlockerrc"):
        path = config_dir / filename
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.optionxform = str
        if path.exists():
            config.read(path, encoding="utf-8")
        updates = {}
        if filename == "powerdevilrc":
            display = {"DimDisplayWhenIdle": "false", "TurnOffDisplayWhenIdle": "false",
                       "LockBeforeTurnOffDisplay": "false"}
            suspend = {"AutoSuspendAction": "0", "AutoSuspendWhenIdle": "false"}
            if profile == "laptop":
                display.update(DimDisplayWhenIdle="true", TurnOffDisplayWhenIdle="true",
                               DimDisplayIdleTimeoutSec="120", TurnOffDisplayIdleTimeoutSec="300")
                suspend.update(AutoSuspendAction="1", AutoSuspendWhenIdle="true",
                               AutoSuspendIdleTimeoutSec="900")
            for power_source in ("AC", "Battery", "LowBattery"):
                # Plasma releases use both flat and nested profile groups.
                updates[power_source] = {**display, **suspend}
                updates[power_source + "][Display"] = display
                updates[power_source + "][SuspendAndShutdown"] = suspend
        elif profile != "laptop":
            updates["Daemon"] = {"Autolock": "false", "LockOnResume": "false"}
        dirty = False
        for section, values in updates.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in values.items():
                if config.get(section, key, fallback=None) != value:
                    config.set(section, key, value)
                    dirty = True
        if dirty:
            backup = path.with_name(path.name + ".before-saar-display")
            if path.exists() and not backup.exists():
                shutil.copy2(path, backup)
            temporary = path.with_name(path.name + ".saar-new")
            with temporary.open("w", encoding="utf-8") as stream:
                config.write(stream, space_around_delimiters=False)
            temporary.replace(path)
            changed = True
    return changed


if __name__ == "__main__":
    print("changed" if configure(Path.home() / ".config") else "unchanged")
