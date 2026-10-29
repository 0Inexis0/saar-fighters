"""Launch one Spotify instance with conservative rendering and audio settings."""
import os
from pathlib import Path
import subprocess
import sys

FLAGS = ["--disable-gpu", "--audio-api=pulseaudio"]
PLAYER = "org.mpris.MediaPlayer2.spotify"


def raise_existing(run=subprocess.run):
    try:
        result = run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
                      "--object-path", "/org/freedesktop/DBus", "--method",
                      "org.freedesktop.DBus.NameHasOwner", PLAYER],
                     capture_output=True, text=True, timeout=3)
        if result.returncode or result.stdout.strip() != "(true,)":
            return False
        # Never create a second player if Raise is unsupported or times out.
        try:
            run(["gdbus", "call", "--session", "--dest", PLAYER,
                 "--object-path", "/org/mpris/MediaPlayer2", "--method",
                 "org.mpris.MediaPlayer2.Raise"], capture_output=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    import fcntl
    if sys.argv[1:]:
        raise SystemExit("Keine Argumente erlaubt.")
    runtime = Path(f"/run/user/{os.getuid()}")
    fd = os.open(runtime / "saar-spotify.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise_existing()
            return 0
        if raise_existing():
            return 0
        return subprocess.call(["flatpak", "run", "com.spotify.Client", *FLAGS])


if __name__ == "__main__":
    sys.exit(main())
