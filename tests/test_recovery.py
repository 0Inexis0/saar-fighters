import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "system" / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


maintenance = module("maintenance")
update = module("update_custom")


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "var/lib/saar-fighters-update"
        self.backup = self.state / "previous"
        self.project = self.root / "opt/saar-fighters"
        for folder in ("app", "system", "installer"):
            shutil.copytree(PROJECT / folder, self.backup / folder, ignore=shutil.ignore_patterns("__pycache__"))
        (self.backup / ".revision").write_text("a" * 40)
        shutil.copytree(self.backup, self.project)
        (self.project / ".revision").write_text("b" * 40)
        (self.project / "app/main.py").write_text("print('broken-new-version')\n")

    def test_restore_is_surface_only_and_keeps_rescue_and_user_data(self):
        personal = self.root / "home/saar/.mozilla/profile"
        personal.parent.mkdir(parents=True)
        personal.write_text("personal browser data")
        maintenance.install_tools(self.root)
        helper = self.root / "usr/local/libexec/saar-maintenance-admin.py"
        old_helper = helper.read_bytes()
        ssh = self.project / "system/configure_ssh.py"
        ssh.write_text("new ssh setup remains")
        before = maintenance.refresh(self.root)
        self.assertTrue(before["available"])
        maintenance.restore_surface(self.root, before["backup_id"])
        self.assertEqual((self.project / "app/main.py").read_bytes(), (self.backup / "app/main.py").read_bytes())
        self.assertEqual((self.project / ".revision").read_text(), "b" * 40)
        self.assertEqual(ssh.read_text(), "new ssh setup remains")
        self.assertEqual(helper.read_bytes(), old_helper)
        self.assertEqual(personal.read_text(), "personal browser data")
        self.assertEqual(maintenance.refresh(self.root)["current"], "a" * 40)
        self.assertFalse(maintenance.refresh(self.root)["available"])
        with self.assertRaisesRegex(RuntimeError, "bereits"):
            maintenance.restore_surface(self.root)

    def test_failed_swap_restores_current_surface_and_clears_journal(self):
        original = (self.project / "app/main.py").read_bytes()
        rename = Path.rename
        def fail(source, destination):
            if source.name == "de.saarfighters.home.saar-restore-new":
                raise OSError("disk failure")
            return rename(source, destination)
        with patch.object(Path, "rename", fail), self.assertRaises(OSError):
            maintenance.restore_surface(self.root)
        self.assertEqual((self.project / "app/main.py").read_bytes(), original)
        self.assertFalse((self.state / "recovery.json").exists())
        self.assertFalse((self.project / ".surface-restored.json").exists())
        self.assertFalse(list(self.root.rglob("*.saar-restore-*")))

    def test_corrupt_backup_and_interrupted_update_block_restore(self):
        (self.backup / "app/main.py").write_text("def broken(")
        self.assertFalse(maintenance.refresh(self.root)["available"])
        with self.assertRaises(SyntaxError):
            maintenance.restore_surface(self.root)
        (self.backup / "app/main.py").write_text("pass\n")
        (self.state / "recovery.json").write_text("[]")
        with self.assertRaisesRegex(RuntimeError, "unterbrochen"):
            maintenance.restore_surface(self.root)

    def test_changed_backup_is_not_restored_after_old_confirmation(self):
        expected = maintenance.refresh(self.root)["backup_id"]
        (self.backup / "app/main.py").write_text("print('different-backup')")
        with self.assertRaisesRegex(RuntimeError, "geändert"):
            maintenance.restore_surface(self.root, expected)

    def test_explicit_update_reinstalls_latest_after_surface_restore(self):
        maintenance.restore_surface(self.root)
        self.assertTrue(update.install_checkout(PROJECT, "b" * 40, self.root))
        self.assertFalse((self.project / ".surface-restored.json").exists())
        self.assertEqual((self.project / "app/main.py").read_bytes(), (PROJECT / "app/main.py").read_bytes())

    def test_missing_module_and_changed_asset_are_detected(self):
        (self.backup / "app/devices.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "Oberflächenmodul"):
            maintenance.validate_surface(self.backup)
        shutil.copy2(PROJECT / "app/devices.py", self.backup / "app/devices.py")
        update.install_checkout(PROJECT, "c" * 40, self.root)
        (self.backup / "app/assets/home.svg").write_text("<svg/>")
        with self.assertRaisesRegex(RuntimeError, "Prüfsummen"):
            maintenance.validate_surface(self.backup)

    def test_backup_with_symlink_is_rejected(self):
        try:
            (self.backup / "app/link").symlink_to(self.project / "app/main.py")
        except OSError:
            self.skipTest("Symlinks unavailable on this host")
        with self.assertRaisesRegex(RuntimeError, "Verknüpfungen"):
            maintenance.restore_surface(self.root)

    def test_disable_persists_and_failed_enable_keeps_opt_out(self):
        ok = lambda args: subprocess.CompletedProcess(args, 0, "", "")
        maintenance.set_ssh(False, self.root, ok)
        marker = self.root / "etc/saar-fighters/ssh/disabled"
        self.assertTrue(marker.exists())
        fail = lambda args: subprocess.CompletedProcess(args, 1, "", "")
        with self.assertRaises(RuntimeError):
            maintenance.set_ssh(True, self.root, fail)
        self.assertTrue(marker.exists())
        maintenance.set_ssh(True, self.root, ok)
        self.assertFalse(marker.exists())

    def test_status_never_invents_active_service_or_public_addresses(self):
        def run(args):
            value = "failed\n" if args[0] == "systemctl" else json.dumps([
                {"addr_info": [{"local": "192.168.1.5"}, {"local": "8.8.8.8"}]}])
            return subprocess.CompletedProcess(args, 0, value, "")
        state = maintenance.status(self.root, run)
        self.assertEqual(state["ssh"]["state"], "failed")
        self.assertEqual(state["ssh"]["addresses"], ["192.168.1.5"])


if __name__ == "__main__":
    unittest.main()
