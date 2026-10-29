import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "system" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maintenance = load("maintenance")
packages = load("update_packages")


class InternetMaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        binary = self.root / "usr/bin/tailscale"
        binary.parent.mkdir(parents=True)
        binary.touch()

    def result(self, data):
        return lambda args: subprocess.CompletedProcess(args, 0, json.dumps(data), "")

    def test_status_exposes_only_own_ipv4_and_trusted_login_url(self):
        result = maintenance.internet_status(self.root, self.result({
            "BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/example",
            "TailscaleIPs": ["100.101.1.2", "fd7a:115c:a1e0::1", "8.8.8.8"],
            "Peer": {"private-device": {}}, "User": {"email": "private@example.com"}}))
        self.assertEqual(result, {"state": "NeedsLogin", "addresses": ["100.101.1.2"],
                                  "auth_url": "https://login.tailscale.com/a/example"})

    def test_untrusted_auth_urls_never_reach_browser(self):
        for url in ("http://login.tailscale.com/a/x", "https://login.tailscale.com.evil/a/x",
                    "https://login.tailscale.com@evil/a/x", "file:///etc/passwd",
                    "https://login.tailscale.com/admin"):
            self.assertEqual(maintenance.internet_status(self.root, self.result({"AuthURL": url}))["auth_url"], "")

    def test_daemon_failure_and_missing_package_have_distinct_states(self):
        with patch.object(maintenance, "command", side_effect=FileNotFoundError):
            result = maintenance.internet_status(self.root, lambda args: (_ for _ in ()).throw(FileNotFoundError()))
            self.assertEqual(result["state"], "unavailable")
        (self.root / "usr/bin/tailscale").unlink()
        self.assertEqual(maintenance.internet_status(self.root)["state"], "missing")

    def test_pending_login_is_successful_setup_not_false_connected_claim(self):
        calls = []
        def run(args):
            calls.append(args)
            if args[:2] == ["tailscale", "status"]:
                return self.result({"BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/test"})(args)
            return subprocess.CompletedProcess(args, 1 if args[0] == "tailscale" else 0, "", "")
        with patch.object(maintenance, "set_ssh") as ssh:
            maintenance.set_internet(True, self.root, run)
            ssh.assert_called_once_with(True, self.root, run)
        self.assertIn(["tailscale", "up", "--timeout=15s"], calls)

    def test_failed_start_does_not_continue_to_login(self):
        calls = []
        def run(args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, "", "failed")
        with patch.object(maintenance, "set_ssh"), self.assertRaisesRegex(RuntimeError, "gestartet"):
            maintenance.set_internet(True, self.root, run)
        self.assertEqual(len(calls), 1)

    def test_live_media_rejects_connect_disconnect_and_package_install(self):
        (self.root / "etc").mkdir()
        (self.root / "etc/saar-live").touch()
        for enabled in (True, False):
            with self.assertRaisesRegex(RuntimeError, "Live-System"):
                maintenance.set_internet(enabled, self.root)
        with self.assertRaisesRegex(RuntimeError, "Live-System"):
            maintenance.install_remote(self.root)

    def test_disconnect_leaves_local_ssh_untouched(self):
        calls = []
        def run(args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        maintenance.set_internet(False, self.root, run)
        self.assertEqual(calls, [["tailscale", "down"]])


class PackageRetryTests(unittest.TestCase):
    def test_retry_preserves_signatures_and_custom_repository(self):
        source = "[options]\nSigLevel = Required DatabaseOptional\n[core]\nInclude = /etc/pacman.d/mirrorlist\n[custom]\nServer = https://example.org/$arch\n"
        result = packages.mirror_config(source)
        self.assertIn("SigLevel = Required DatabaseOptional", result)
        self.assertIn("Server = https://example.org/$arch", result)
        self.assertIn("Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch", result)

    def test_custom_configuration_without_standard_mirror_is_not_rewritten(self):
        with self.assertRaises(RuntimeError):
            packages.mirror_config("[core]\nServer = https://custom.invalid/$arch\n")

    def test_unrelated_failure_never_retries_or_changes_configuration(self):
        with patch.object(packages, "run_upgrade", return_value=(1, False)) as run, \
                patch.object(packages.Path, "read_text") as read:
            with self.assertRaises(RuntimeError):
                packages.upgrade()
            run.assert_called_once_with()
            read.assert_not_called()

    def test_signature_failure_retries_once_with_isolated_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            def run(extra=()):
                if not extra:
                    return 1, True
                self.assertIn("--cachedir", extra)
                self.assertTrue(Path(extra[extra.index("--config") + 1]).is_file())
                return 1, True
            real_temp = tempfile.TemporaryDirectory
            with patch.object(packages, "run_upgrade", side_effect=run) as runner, \
                    patch.object(packages.Path, "read_text", return_value="[core]\nInclude = /etc/pacman.d/mirrorlist\n"), \
                    patch.object(packages.tempfile, "TemporaryDirectory", side_effect=lambda **kw: real_temp(dir=directory)):
                with self.assertRaisesRegex(RuntimeError, "neue Download"):
                    packages.upgrade()
                self.assertEqual(runner.call_count, 2)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
