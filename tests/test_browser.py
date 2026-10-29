import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


browser = load("app/browser.py")
setup = load("system/configure_browser.py")


class BrowserTests(unittest.TestCase):
    def test_flatpak_launch_preserves_urls_and_local_game_address(self):
        for url in ("https://www.youtube.com/", "http://127.0.0.1:18741", "https://example.org/a b"):
            with patch.object(browser.shutil, "which", return_value=None):
                self.assertEqual(browser.browser_command(url), ["flatpak", "run", "com.brave.Browser", "--start-fullscreen", "--new-window", url])

    def test_native_brave_is_preferred(self):
        with patch.object(browser.shutil, "which", side_effect=lambda name: "/usr/bin/brave" if name == "brave" else None):
            self.assertEqual(browser.browser_command("https://example.org"), ["brave", "--start-fullscreen", "--new-window", "https://example.org"])

    def test_first_install_checks_success_before_setting_default(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1 if len(calls) == 1 else 0)
        with patch.object(setup, "desktop_home", return_value="/home/saar"):
            setup.configure(run, lambda name: "/usr/bin/flatpak" if name == "flatpak" else None)
        self.assertEqual(calls[2], ["flatpak", "install", "--system", "--noninteractive", "flathub", "com.brave.Browser"])
        self.assertEqual(calls[3], ["flatpak", "info", "--system", "com.brave.Browser"])
        self.assertEqual(calls[-1][-4:], ["com.brave.Browser.desktop", "text/html", "x-scheme-handler/http", "x-scheme-handler/https"])

    def test_failed_install_keeps_existing_default(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["flatpak", "install"]:
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 1 if len(calls) == 1 else 0)
        with self.assertRaises(subprocess.CalledProcessError):
            setup.configure(run, lambda name: "/usr/bin/flatpak" if name == "flatpak" else None)
        self.assertFalse(any(args[0] == "runuser" for args in calls))

    def test_existing_install_is_not_downloaded_again(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0)
        with patch.object(setup, "desktop_home", return_value="/home/saar"):
            setup.configure(run, lambda name: "/usr/bin/flatpak" if name == "flatpak" else None)
        self.assertFalse(any(args[:2] == ["flatpak", "install"] for args in calls))
