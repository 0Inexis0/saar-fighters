"""Keep desktop apps outside the dashboard service and bound their diagnostics."""
import os
from pathlib import Path
import subprocess
import sys

from runtime_health import APPS, categories, record


def session_command(command, *, wait=True):
    # A detached fork still belongs to saar-home.service's cgroup. A separate
    # user service survives dashboard restarts, but stops with the desktop.
    result = ["systemd-run", "--user", "--quiet", "--collect", "--service-type=exec",
              "--expand-environment=no", "--description=Saar-Fighters application",
              "--property=ExitType=cgroup", "--property=PartOf=graphical-session.target",
              "--property=After=graphical-session.target",
              "--property=StandardOutput=null", "--property=StandardError=null"]
    if wait:
        result.append("--wait")
    # Use the current desktop's display, including manual dashboard launches.
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR",
                 "DBUS_SESSION_BUS_ADDRESS", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE",
                 "XDG_SESSION_DESKTOP", "LANG", "LANGUAGE", "LC_ALL"):
        if name in os.environ:
            result.append(f"--setenv={name}={os.environ[name]}")
    return [*result, "--", *command]


def application_command(command, action):
    if sys.platform != "linux" or action not in APPS:
        return command
    return session_command([sys.executable, str(Path(__file__).resolve()), action, *command])


def supervise(action, command):
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except OSError:
        record(action, "exit", code=127)
        return 127
    record(action, "start")
    seen, tail = set(), ""
    with child.stderr:
        while chunk := child.stderr.read1(8192):
            text = tail + chunk.decode("utf-8", errors="replace")
            found = categories(text)
            for category in found - seen:
                record(action, "error", category=category)
            seen.update(found)
            tail = text[-128:]
    code = child.wait()
    record(action, "exit", code=code)
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in APPS:
        raise SystemExit(2)
    sys.exit(supervise(sys.argv[1], sys.argv[2:]))
