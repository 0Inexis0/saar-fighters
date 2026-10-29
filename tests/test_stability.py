import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, PROJECT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stability = load("system/configure_stability.py")
spotify = load("app/spotify_launcher.py")
health = load("app/runtime_health.py")
maintenance = load("system/maintenance.py")


class StabilityTests(unittest.TestCase):
    def test_legacy_install_hook_applies_stability_after_installing_tools(self):
        order = []
        with patch.object(maintenance.sys, "argv", ["maintenance.py", "install"]), \
                patch.object(maintenance.os, "geteuid", return_value=0, create=True), \
                patch.object(maintenance, "install_tools", side_effect=lambda: order.append("tools")), \
                patch.object(maintenance.subprocess, "run", side_effect=lambda *a, **k: order.append("policy")) as run:
            maintenance.main()
        self.assertEqual(order, ["tools", "policy"])
        run.assert_called_once_with(["/usr/bin/python", "-I", "/opt/saar-fighters/system/configure_stability.py"], check=True)

    def test_firefox_policy_preserves_existing_settings_and_original_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "usr/lib/firefox/distribution/policies.json"
            path.parent.mkdir(parents=True)
            original = b'{"policies":{"DisableAppUpdate":true,"Preferences":{"keep":true}}}'
            path.write_bytes(original)
            self.assertTrue(stability.configure(root))
            self.assertFalse(stability.configure(root))
            self.assertEqual(path.with_name("policies.before-stability.json").read_bytes(), original)
            self.assertEqual(json.loads(path.read_text())["policies"],
                             {"DisableAppUpdate": True, "Preferences": {"keep": True}, "HardwareAcceleration": False})

    def test_invalid_policy_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "usr/lib/firefox/distribution/policies.json"
            path.parent.mkdir(parents=True)
            path.write_text("broken")
            with self.assertRaises(ValueError):
                stability.configure(root)
            self.assertEqual(path.read_text(), "broken")

    def test_live_media_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "etc").mkdir()
            (root / "etc/saar-live").touch()
            self.assertFalse(stability.configure(root))
            self.assertFalse((root / "usr").exists())

    def test_existing_spotify_is_reused_even_when_raise_times_out(self):
        run = Mock(side_effect=[subprocess.CompletedProcess([], 0, "(true,)\n"),
                                subprocess.TimeoutExpired("gdbus", 3)])
        self.assertTrue(spotify.raise_existing(run))
        self.assertEqual(run.call_count, 2)

    def test_missing_spotify_allows_first_launch(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, "(false,)\n"))
        self.assertFalse(spotify.raise_existing(run))
        self.assertEqual(run.call_count, 1)

    def test_diagnostics_never_save_raw_output_and_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            text = "malloc(): corrupted size https://private.example/?token=secret"
            self.assertEqual(health.categories(text), {"memory"})
            health.record("spotify", "error", category="memory", home=home)
            path = home / ".local/state/saar-fighters/app-health.jsonl"
            self.assertNotIn("private", path.read_text())
            self.assertNotIn("secret", path.read_text())
            path.write_text("x" * 65537)
            health.record("spotify", "exit", code=6, home=home)
            self.assertLess(path.stat().st_size, 1024)
            self.assertEqual(path.with_suffix(".previous").stat().st_size, 65537)


if __name__ == "__main__":
    unittest.main()
