import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("remove_tailscale", Path(__file__).resolve().parents[1] / "system/remove_tailscale.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class RemoveTailscaleTests(unittest.TestCase):
    def test_restricts_ssh_before_stopping_and_uninstalling_vpn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "etc/saar-fighters/ssh/sshd_config"
            config.parent.mkdir(parents=True)
            config.write_text("AllowUsers wartung@100.64.0.0/10")
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                return subprocess.CompletedProcess(args, 0)
            migration.remove(root, run)
            self.assertEqual(calls, [
                ["/usr/bin/python", "-I", "/opt/saar-fighters/system/configure_ssh.py"],
                ["pacman", "-Q", "tailscale"],
                ["systemctl", "disable", "--now", "tailscaled.service"],
                ["pacman", "-R", "--noconfirm", "tailscale"]])

    def test_absent_package_does_not_change_services_or_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                return subprocess.CompletedProcess(args, 1)
            migration.remove(Path(temporary), run)
            self.assertEqual(calls, [["pacman", "-Q", "tailscale"]])

    def test_live_media_never_changes_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "etc").mkdir()
            (root / "etc/saar-live").touch()
            def run(*args, **kwargs):
                self.fail("Must not run a command on live media")
            migration.remove(root, run)

    def test_service_stop_failure_does_not_remove_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                if args[0] == "systemctl":
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(args, 0)
            with self.assertRaises(subprocess.CalledProcessError):
                migration.remove(Path(temporary), run)
            self.assertFalse(any(args[:2] == ["pacman", "-R"] for args in calls))
