"""Exercise the real file transaction in an isolated filesystem, never the host."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("custom_update", PROJECT / "system/update_custom.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class CustomUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "root"
        self.checkout = Path(self.temp.name) / "checkout"
        for folder in ("app", "system", "installer"):
            shutil.copytree(PROJECT / folder, self.checkout / folder,
                            ignore=shutil.ignore_patterns("__pycache__"))
        self.project = self.root / "opt/saar-fighters"
        self.project.mkdir(parents=True)
        (self.project / "old-version").write_text("working version")
        self.helper = self.root / "usr/local/libexec/saar-update"
        self.helper.parent.mkdir(parents=True)
        self.helper.write_text("old helper")
        self.state = self.root / "var/lib/saar-fighters-update"

    def test_complete_update_and_subsequent_update_preserve_previous_and_user_data(self):
        user = self.root / "home/saar/.config"
        user.mkdir(parents=True)
        (user / "kdeglobals").write_text("personal settings")
        update.validate_checkout(self.checkout)
        update.install_checkout(self.checkout, "a" * 40, self.root)
        self.assertEqual((self.state / "previous/old-version").read_text(), "working version")
        self.assertTrue((self.project / "app/main.py").is_file())
        self.assertTrue((self.project / "app/rocket.py").is_file())
        self.assertTrue((self.project / "app/rocket-launch/index.html").is_file())
        self.assertIn("saar-update-custom.py", self.helper.read_text())
        self.assertEqual(self.helper.stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.root / "usr/local/libexec/saar-install").exists())
        update.install_checkout(self.checkout, "b" * 40, self.root)
        self.assertEqual((self.state / "previous/.revision").read_text().strip(), "a" * 40)
        self.assertEqual((self.state / "current-revision").read_text().strip(), "b" * 40)
        self.assertFalse((self.state / "recovery.json").exists())
        self.assertEqual((user / "kdeglobals").read_text(), "personal settings")

    def test_same_version_preserves_recovery_copy(self):
        self.assertTrue(update.install_checkout(self.checkout, "a" * 40, self.root))
        self.assertFalse(update.install_checkout(self.checkout, "a" * 40, self.root))
        self.assertEqual((self.state / "previous/old-version").read_text(), "working version")

    def test_missing_rocket_asset_rejects_incomplete_update(self):
        (self.checkout / "app/rocket-launch/js/missile.js").unlink()
        with self.assertRaisesRegex(RuntimeError, "missile.js"):
            update.validate_checkout(self.checkout)

    def test_missing_application_runner_rejects_incomplete_update(self):
        (self.checkout / "app/application_runner.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "application_runner.py"):
            update.validate_checkout(self.checkout)

    def test_mid_install_failure_restores_all_old_files(self):
        rename = Path.rename
        def fail(source, destination):
            if source.name == "saar-update-custom.py.saar-new":
                raise OSError("simulated disk failure")
            return rename(source, destination)
        with patch.object(Path, "rename", fail), self.assertRaises(OSError):
            update.install_checkout(self.checkout, "a" * 40, self.root)
        self.assertEqual((self.project / "old-version").read_text(), "working version")
        self.assertEqual(self.helper.read_text(), "old helper")
        self.assertFalse((self.state / "current-revision").exists())
        self.assertFalse((self.state / "recovery.json").exists())
        self.assertFalse(list(self.root.rglob("*.saar-new")))
        self.assertFalse(list(self.root.rglob("*.saar-previous")))

    def test_backup_failure_does_not_modify_installed_version(self):
        copytree = shutil.copytree
        def fail(source, destination, *args, **kwargs):
            if Path(source) == self.project:
                raise OSError("simulated full backup disk")
            return copytree(source, destination, *args, **kwargs)
        with patch.object(update.shutil, "copytree", fail), self.assertRaises(OSError):
            update.install_checkout(self.checkout, "a" * 40, self.root)
        self.assertEqual((self.project / "old-version").read_text(), "working version")
        self.assertEqual(self.helper.read_text(), "old helper")
        self.assertFalse(list(self.root.rglob("*.saar-new")))
        self.assertFalse((self.state / "recovery.json").exists())

    def test_incomplete_download_is_rejected(self):
        (self.checkout / "app/main.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "unvollständig"):
            update.validate_checkout(self.checkout)
        self.assertEqual(self.helper.read_text(), "old helper")

    def test_invalid_python_is_rejected(self):
        (self.checkout / "app/main.py").write_text("def broken(")
        with self.assertRaises(SyntaxError):
            update.validate_checkout(self.checkout)

    def test_symlink_in_download_is_rejected(self):
        (self.checkout / "app/link").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(RuntimeError, "Dateityp"):
            update.validate_checkout(self.checkout)

    def test_unfinished_transaction_blocks_new_update(self):
        self.state.mkdir(parents=True)
        (self.state / "recovery.json").write_text("[]")
        with self.assertRaisesRegex(RuntimeError, "unterbrochen"):
            update.install_checkout(self.checkout, "a" * 40, self.root)
        self.assertEqual(self.helper.read_text(), "old helper")

    def test_download_error_never_installs(self):
        with patch.object(update, "fetch_checkout", side_effect=TimeoutError), \
             patch.object(update, "install_checkout") as install, \
             patch.object(update.os, "geteuid", return_value=0), \
             patch.object(update.sys, "argv", ["saar-update-custom.py"]):
            with self.assertRaises(TimeoutError):
                update.main()
            install.assert_not_called()

    def test_check_mode_validates_without_installing(self):
        def fetch(destination):
            shutil.copytree(self.checkout, destination)
            return "a" * 40
        with patch.object(update, "fetch_checkout", side_effect=fetch), \
             patch.object(update, "install_checkout") as install, \
             patch.object(update.sys, "argv", ["saar-update-custom.py", "--check"]):
            update.main()
            install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
