"""Discover visible desktop applications, including user and Flatpak installs."""
from configparser import ConfigParser, Error as ConfigError
from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import shutil


@dataclass(frozen=True)
class Application:
    id: str
    title: str
    description: str = ""
    icon: str = ""
    action: str = ""
    desktop_file: Path | None = None


SHORTCUTS = (
    Application("rocket", "Rocket Launch", "Airsoft-Spiel starten", "rocket", "rocket"),
    Application("spotify", "Spotify", "Der Sound für euren Tag", "music", "spotify"),
    Application("web", "Internet", "Firefox öffnen", "web", "web"),
    Application("youtube", "YouTube", "Videos & Musik öffnen", "youtube", "youtube"),
    Application("files", "Dateien", "Musik, Bilder & USB-Sticks", "folder", "files"),
    Application("club", "Vereinswebseite", "Saar-Fighters AS e.V.", "club", "club"),
)
SHORTCUT_IDS = {
    "firefox.desktop": "web", "org.mozilla.firefox.desktop": "web",
    "com.spotify.Client.desktop": "spotify", "spotify.desktop": "spotify",
    "org.kde.dolphin.desktop": "files",
}
EXCLUDED_IDS = {"de.saarfighters.Home.desktop"}


def application_directories():
    """Keep XDG precedence; include Flatpak exports even in older sessions."""
    home = Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    roots = [data_home, *map(Path, filter(None, data_dirs.split(os.pathsep))),
             home / ".local/share/flatpak/exports/share",
             Path("/var/lib/flatpak/exports/share")]
    return list(dict.fromkeys(root / "applications" for root in roots if root.is_absolute()))


def desktop_text(value):
    escapes = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    return re.sub(r"\\([sntr\\])", lambda match: escapes[match[1]], value)


def localized(entry, key):
    # The club desktop and Qt interface consistently use German.
    return desktop_text(next((entry[name] for name in (f"{key}[de_DE]", f"{key}[de]", key)
                              if entry.get(name)), ""))


def read_application(path, desktop_id, desktops):
    parser = ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read_string(path.read_text(encoding="utf-8"))
        entry = parser["Desktop Entry"]
    except (OSError, UnicodeError, ConfigError, KeyError):
        return None
    if entry.get("Type") != "Application" or any(
            entry.get(key, "").lower() == "true" for key in ("Hidden", "NoDisplay")):
        return None
    only = set(filter(None, entry.get("OnlyShowIn", "").split(";")))
    excluded = set(filter(None, entry.get("NotShowIn", "").split(";")))
    visible = not only
    for desktop in desktops:
        if desktop in only or desktop in excluded:
            visible = desktop in only
            break
    if not visible:
        return None
    executable = desktop_text(entry.get("TryExec", ""))
    if executable and not shutil.which(executable):
        return None
    title = localized(entry, "Name")
    if not title or not (entry.get("Exec") or entry.get("DBusActivatable", "").lower() == "true"):
        return None
    return Application(desktop_id, title,
                       localized(entry, "GenericName") or localized(entry, "Comment"),
                       desktop_text(entry.get("Icon", "")), desktop_file=path.absolute())


def discover_applications(directories=None):
    directories = application_directories() if directories is None else directories
    desktops = (os.environ.get("XDG_CURRENT_DESKTOP") or "KDE").split(":")
    seen = set()
    applications = []
    for directory in directories:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.desktop")):
            desktop_id = "-".join(path.relative_to(directory).parts)
            if desktop_id in seen:
                continue
            # Hidden user entries also mask system entries with the same ID.
            seen.add(desktop_id)
            if desktop_id in EXCLUDED_IDS:
                continue
            application = read_application(path, desktop_id, desktops)
            if application:
                applications.append(application)
    return applications


def application_catalog(directories=None):
    shortcuts = {app.id: app for app in SHORTCUTS}
    applications = []
    replaced = set()
    for application in discover_applications(directories):
        shortcut = SHORTCUT_IDS.get(application.id)
        if shortcut:
            if shortcut not in replaced:
                # Use the installed launcher, including native Spotify and Flatpaks.
                shortcuts[shortcut] = replace(shortcuts[shortcut], action="",
                                               desktop_file=application.desktop_file)
                replaced.add(shortcut)
        else:
            applications.append(application)
    return sorted([*shortcuts.values(), *applications], key=lambda app: (app.title.casefold(), app.id))
