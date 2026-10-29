"""Offline Airsoft game host and Brave launcher, using only Python's stdlib."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent / "rocket-launch"
PORT = 18741
APP_ID = "saar-fighters-rocket-launch"


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "saar-fighters/rocket-launch.json"


def activity_path():
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "saar-fighters/rocket-active"


def game_active():
    try:
        return 0 <= time.time() - activity_path().stat().st_mtime < 90
    except OSError:
        return False


def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError("Ungültige Einstellungen.")
    result = {}
    for key in ("startCode", "disarmCode"):
        value = data.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4,12}", value):
            raise ValueError("Codes müssen aus 4 bis 12 Ziffern bestehen.")
        result[key] = value
    if result["startCode"] == result["disarmCode"]:
        raise ValueError("Start- und Entschärfungscode müssen verschieden sein.")
    for key in ("timerSeconds", "flightTimeSeconds"):
        value = data.get(key)
        if type(value) is not int or not 1 <= value <= 3600:
            raise ValueError("Zeiten müssen ganze Sekunden zwischen 1 und 3600 sein.")
        result[key] = value
    for key in ("allowDisarmDuringCountdown", "allowDisarmDuringFlight", "lockoutAfterFailedAttempts"):
        value = data.get(key, True)
        if type(value) is not bool:
            raise ValueError("Ungültige Schalter-Einstellung.")
        result[key] = value
    return result


class GameServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_path=None):
        self.data_path = Path(data_path) if data_path else config_path()
        self.config_lock = threading.Lock()
        super().__init__(address, GameHandler)

    def read_config(self):
        source = self.data_path if self.data_path.exists() else ROOT / "config.json"
        with self.config_lock:
            return validate_config(json.loads(source.read_text(encoding="utf-8")))

    def save_config(self, data):
        data = validate_config(data)
        with self.config_lock:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.data_path.parent,
                                                 delete=False) as output:
                    name = output.name
                    json.dump(data, output, ensure_ascii=False, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(name, self.data_path)
            finally:
                if name and Path(name).exists():
                    Path(name).unlink()


class GameHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript",
                      ".css": "text/css", ".svg": "image/svg+xml", ".mp3": "audio/mpeg"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def json_response(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            self.send_error(403)
            return
        route = urlsplit(self.path).path
        if route == "/api/health":
            self.json_response(200, {"app": APP_ID})
        elif route == "/api/config":
            try:
                self.json_response(200, self.server.read_config())
            except (OSError, ValueError):
                self.json_response(500, {"error": "Einstellungen konnten nicht geladen werden."})
        elif self.public_asset(route):
            super().do_GET()
        elif route == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def do_HEAD(self):
        if self.valid_host() and self.public_asset(urlsplit(self.path).path):
            super().do_HEAD()
        else:
            self.send_error(404)

    def public_asset(self, route):
        if route in ("/", "/index.html"):
            return True
        relative = Path(unquote(route).lstrip("/"))
        candidate = (ROOT / relative).resolve()
        return (relative.parts and relative.parts[0] in ("js", "css", "assets")
                and not any(part.startswith(".") for part in relative.parts)
                and candidate.is_relative_to(ROOT.resolve()) and candidate.is_file())

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self.valid_host() or self.headers.get("Origin") != origin:
            self.json_response(403, {"error": "Nur aus der lokalen Spielkonsole möglich."})
            return
        if self.path not in ("/api/config", "/api/activity"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096 or self.headers.get_content_type() != "application/json":
                raise ValueError("Ungültige Anfrage.")
            data = json.loads(self.rfile.read(length))
            if self.path == "/api/config":
                self.server.save_config(data)
            elif isinstance(data, dict) and data.get("active") is True:
                marker = activity_path()
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch()
            self.json_response(200, {"success": True})
        except (ValueError, TypeError):
            self.json_response(400, {"error": "Codes: 4 bis 12 verschiedene Ziffernfolgen. Zeiten: 1 bis 3600 Sekunden."})
        except OSError:
            self.json_response(500, {"error": "Einstellungen konnten nicht gespeichert werden."})


def server_ready(port=PORT):
    try:
        # Local requests must not use a machine's HTTP proxy.
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
            return json.loads(response.read(512)).get("app") == APP_ID
    except (OSError, URLError, ValueError, AttributeError):
        return False


def ensure_server():
    if server_ready():
        return
    options = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NO_WINDOW}
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, **options)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if server_ready():
            return
        if child.poll() is not None:
            break
        time.sleep(0.1)
    raise RuntimeError("Rocket Launch konnte nicht starten. Der lokale Port 18741 ist möglicherweise belegt.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    if args.serve:
        with GameServer(("127.0.0.1", PORT)) as server:
            server.serve_forever()
    else:
        from browser import browser_command
        command = browser_command(f"http://127.0.0.1:{PORT}")
        if not shutil.which(command[0]):
            raise RuntimeError("Brave fehlt. Bitte zuerst das Systemupdate ausführen.")
        ensure_server()
        subprocess.run(command, check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
