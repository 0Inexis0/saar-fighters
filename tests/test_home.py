"""Behavioral checks for the public launcher and disruptive action boundaries."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from main import Home, STYLE, UpdateDialog
from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox


class HomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(1024, 600)
        self.home.show()
        self.app.processEvents()

    def tearDown(self):
        self.home.close()
        self.home.deleteLater()
        self.app.processEvents()

    def test_all_tiles_are_clickable_without_launching_in_preview(self):
        with patch.object(QProcess, "start") as start:
            for action, tile in self.home.tiles.items():
                QTest.mouseClick(tile, Qt.MouseButton.LeftButton)
                self.assertEqual(self.home.last_action, action)
                self.assertIn("Vorschau", self.home.feedback.text())
            start.assert_not_called()

    def test_controls_fit_small_laptop(self):
        for size in ((1024, 600), (800, 540), (1366, 768)):
            self.home.resize(*size)
            self.app.processEvents()
            for tile in self.home.tiles.values():
                self.assertTrue(self.home.rect().contains(tile.geometry()))
                self.assertGreaterEqual(tile.width(), 170)
                self.assertGreaterEqual(tile.height(), 113)
            self.assertTrue(self.home.rect().contains(self.home.update_button.geometry()))

    def choose_power(self, confirm):
        modal = QApplication.activeModalWidget()
        self.assertIsInstance(modal, QMessageBox)
        role = QMessageBox.ButtonRole.AcceptRole if confirm else QMessageBox.ButtonRole.RejectRole
        for button in modal.buttons():
            if modal.buttonRole(button) == role:
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                break

    def test_cancel_shutdown_does_nothing(self):
        QTimer.singleShot(20, lambda: self.choose_power(False))
        with patch.object(QProcess, "start") as start:
            self.home.power("poweroff")
            start.assert_not_called()
        self.assertIsNone(self.home.last_action)

    def test_preview_confirmed_reboot_is_safe(self):
        QTimer.singleShot(20, lambda: self.choose_power(True))
        with patch.object(QProcess, "start") as start:
            self.home.power("reboot")
            start.assert_not_called()
        self.assertEqual(self.home.last_action, "reboot")

    def test_arbitrary_power_commands_rejected(self):
        with self.assertRaises(ValueError):
            self.home.power("shell")

    def test_update_reports_failure_and_success_separately(self):
        dialog = UpdateDialog(self.home, preview=True)
        dialog.finished_update(1, QProcess.ExitStatus.NormalExit)
        self.assertIn("fehlgeschlagen", dialog.state.text())
        dialog.finished_update(0, QProcess.ExitStatus.CrashExit)
        self.assertIn("fehlgeschlagen", dialog.state.text())
        dialog.finished_update(0, QProcess.ExitStatus.NormalExit)
        self.assertIn("erfolgreich", dialog.state.text())
        dialog.finished_update(126, QProcess.ExitStatus.NormalExit)
        self.assertIn("nicht freigegeben", dialog.state.text())

    def test_update_uses_only_the_fixed_privileged_helper(self):
        dialog = UpdateDialog(self.home)
        with patch.object(dialog.process, "start") as start:
            dialog.begin(preview=False)
            start.assert_called_once_with("pkexec", ["/usr/local/libexec/saar-update"])
        self.assertFalse(dialog.close_button.isEnabled())

    def test_missing_app_is_reported(self):
        self.home.preview = False
        with patch("main.shutil.which", return_value=None):
            self.home.launch("web")
        self.assertIn("fehlt", self.home.feedback.text())
        self.home.preview = True


if __name__ == "__main__":
    unittest.main()
