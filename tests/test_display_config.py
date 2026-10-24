import configparser
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "system/configure_display.py"
spec = importlib.util.spec_from_file_location("display_config", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisplayConfigTests(unittest.TestCase):
    def test_existing_profiles_are_migrated_and_unrelated_settings_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "powerdevilrc"
            original = "[Battery][Display]\nDimDisplayWhenIdle=true\nDisplayBrightness=75\n[Battery][SuspendAndShutdown]\nLidAction=1\n"
            path.write_text(original, encoding="utf-8")
            self.assertTrue(module.configure(folder))
            config = configparser.ConfigParser()
            config.read(path, encoding="utf-8")
            for profile in ("AC", "Battery", "LowBattery"):
                for section in (profile, profile + "][Display"):
                    self.assertFalse(config.getboolean(section, "DimDisplayWhenIdle"))
                    self.assertFalse(config.getboolean(section, "TurnOffDisplayWhenIdle"))
                self.assertEqual(config.getint(profile + "][SuspendAndShutdown", "AutoSuspendAction"), 0)
            self.assertEqual(config.getint("Battery][Display", "DisplayBrightness"), 75)
            self.assertEqual(config.getint("Battery][SuspendAndShutdown", "LidAction"), 1)
            self.assertEqual(path.with_name(path.name + ".before-saar-display").read_text(encoding="utf-8"), original)
            self.assertFalse(module.configure(folder))

    def test_new_profile_disables_automatic_locking(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(module.configure(folder))
            config = configparser.ConfigParser()
            config.read(Path(folder) / "kscreenlockerrc")
            self.assertFalse(config.getboolean("Daemon", "Autolock"))
            self.assertFalse(config.getboolean("Daemon", "LockOnResume"))
