"""Application and game-mode catalogs for the dashboard."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Application:
    id: str
    title: str
    description: str = ""
    icon: str = ""
    action: str = ""


GAMEMODES = (
    Application("rocket", "Rocket Launch", "Airsoft-Spiel starten", "rocket", "rocket"),
)

SHORTCUTS = (
    Application("spotify", "Spotify", "Der Sound für euren Tag", "music", "spotify"),
    Application("web", "Internet", "Brave öffnen", "web", "web"),
    Application("youtube", "YouTube", "Videos & Musik öffnen", "youtube", "youtube"),
    Application("files", "Dateien", "Musik, Bilder & USB-Sticks", "folder", "files"),
    Application("club", "Vereinswebseite", "Saar-Fighters AS e.V.", "club", "club"),
)


def application_catalog():
    return list(SHORTCUTS)


def gamemode_catalog():
    return list(GAMEMODES)
