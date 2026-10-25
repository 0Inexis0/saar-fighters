"""Exercise the local game host with real HTTP and isolated user settings."""
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rocket", PROJECT / "app/rocket.py")
rocket = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rocket)


class RocketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / "profile/game.json"
        self.server = rocket.GameServer(("127.0.0.1", 0), self.config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.port = self.server.server_port
        self.origin = f"http://127.0.0.1:{self.port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path, data=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        self.addCleanup(connection.close)
        actual = {"Content-Type": "application/json", "Origin": self.origin, **(headers or {})}
        connection.request("POST" if data is not None else "GET", path,
                           json.dumps(data) if data is not None else None, actual)
        response = connection.getresponse()
        return response.status, response.read(), response.headers

    def test_offline_assets_and_health(self):
        self.assertTrue(rocket.server_ready(self.port))
        for path, mime in (("/", "text/html"), ("/js/main.js", "text/javascript"),
                           ("/css/layout.css", "text/css"), ("/assets/world-map.svg", "image/svg+xml"),
                           ("/assets/Explosion%20-%20Sound%20Effect.mp3", "audio/mpeg")):
            status, body, headers = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body)
            self.assertIn(mime, headers["Content-Type"])

    def test_saved_settings_survive_new_server_and_keep_defaults_unchanged(self):
        default = (rocket.ROOT / "config.json").read_bytes()
        config = json.loads(self.request("/api/config")[1])
        config.update(startCode="1234", disarmCode="5678", timerSeconds=90, allowDisarmDuringFlight=False)
        self.assertEqual(self.request("/api/config", config)[0], 200)
        with rocket.GameServer(("127.0.0.1", 0), self.config) as second:
            self.assertEqual(second.read_config(), config)
        self.assertEqual((rocket.ROOT / "config.json").read_bytes(), default)

    def test_invalid_settings_never_replace_saved_round(self):
        config = self.server.read_config()
        self.server.save_config(config)
        original = self.config.read_bytes()
        for change in ({"timerSeconds": 0}, {"flightTimeSeconds": True}, {"startCode": "x"},
                       {"disarmCode": config["startCode"]}, {"allowDisarmDuringFlight": "false"}):
            self.assertEqual(self.request("/api/config", {**config, **change})[0], 400)
            self.assertEqual(self.config.read_bytes(), original)

    def test_broken_saved_file_reports_error_instead_of_silent_defaults(self):
        self.config.parent.mkdir(parents=True)
        self.config.write_text("broken")
        self.assertEqual(self.request("/api/config")[0], 500)

    def test_foreign_sites_and_private_paths_are_rejected(self):
        self.assertEqual(self.request("/api/config", self.server.read_config(), {"Origin": "https://example.org"})[0], 403)
        self.assertEqual(self.request("/api/config", headers={"Host": "example.org"})[0], 403)
        for path in ("/config.json", "/rocket.py", "/js/../../rocket.py", "/assets/", "/js/%2e%2e/config.json"):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_running_server_is_reused_without_spawning_or_killing_processes(self):
        with patch.object(rocket, "server_ready", return_value=True), patch.object(rocket.subprocess, "Popen") as spawn:
            rocket.ensure_server()
            spawn.assert_not_called()

    def test_recent_activity_suppresses_slideshow_but_expires(self):
        marker = Path(self.temp.name) / "activity"
        with patch.object(rocket, "activity_path", return_value=marker):
            self.assertFalse(rocket.game_active())
            self.assertEqual(self.request("/api/activity", {"active": True})[0], 200)
            self.assertTrue(rocket.game_active())
            with patch.object(rocket.time, "time", return_value=marker.stat().st_mtime + 91):
                self.assertFalse(rocket.game_active())
