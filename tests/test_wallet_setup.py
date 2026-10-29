import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("configure_wallet", Path(__file__).resolve().parents[1] / "system/configure_wallet.py")
wallet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wallet)


class WalletSetupTests(unittest.TestCase):
    def test_backup_and_one_time_migration_preserve_later_user_choices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            original = b"[Wallet]\nEnabled=false\nCloseWhenIdle=true\n"
            (config / "kwalletrc").write_bytes(original)
            run = Mock()
            self.assertTrue(wallet.configure(config, root / "state", run))
            self.assertEqual((config / "kwalletrc.before-saar-wallet-fix").read_bytes(), original)
            run.assert_called_once_with(["kwriteconfig6", "--file", str(config / "kwalletrc"),
                                        "--group", "Wallet", "--key", "Enabled", "true"], check=True)
            self.assertFalse(wallet.configure(config, root / "state", run))
            self.assertEqual(run.call_count, 1)

    def test_failed_write_is_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(subprocess.CalledProcessError):
                wallet.configure(root / "config", root / "state", Mock(side_effect=subprocess.CalledProcessError(1, "kwriteconfig6")))
            self.assertFalse((root / "state/saar-fighters/kwallet-enabled-v1").exists())

    @unittest.skipUnless(shutil.which("kwriteconfig6"), "KDE config tools required")
    def test_real_kde_writer_changes_only_enabled_setting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            (config / "kwalletrc").write_text("[Wallet]\nEnabled=false\nCloseWhenIdle=true\n[Other]\nKeep=value\n")
            wallet.configure(config, root / "state")
            result = (config / "kwalletrc").read_text()
            self.assertIn("Enabled=true", result)
            self.assertIn("CloseWhenIdle=true", result)
            self.assertIn("Keep=value", result)
