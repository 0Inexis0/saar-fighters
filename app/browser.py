"""One browser entry point for web links, media, and the local game."""
import shutil

APP_ID = "com.brave.Browser"


def browser_command(url):
    for binary in ("brave", "brave-browser", "brave-browser-stable"):
        if shutil.which(binary):
            return [binary, "--new-window", url]
    return ["flatpak", "run", APP_ID, "--new-window", url]
