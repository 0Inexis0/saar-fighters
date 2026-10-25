"""Behavioral checks for the public launcher and disruptive action boundaries."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from main import Home, SettingsDialog, STYLE, UpdateDialog
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
        with patch.object(QProcess, "start") as start, patch.object(self.home, "show_settings") as settings:
            for action, tile in self.home.tiles.items():
                QTest.mouseClick(tile, Qt.MouseButton.LeftButton)
                self.assertEqual(self.home.last_action, action)
                if action == "settings":
                    settings.assert_called_once_with()
                else:
                    self.assertIn("Vorschau", self.home.feedback.text())
            start.assert_not_called()

    def test_controls_fit_small_laptop(self):
        for size in ((1024, 600), (800, 540), (1366, 768)):
            self.home.resize(*size)
            self.app.processEvents()
            self.assertEqual((self.home.width(), self.home.height()), size)
            for tile in self.home.tiles.values():
                self.assertTrue(self.home.rect().contains(tile.geometry()))
                self.assertGreaterEqual(tile.width(), 150)
                self.assertGreaterEqual(tile.height(), 104)

    def test_settings_navigation_and_return(self):
        self.assertEqual(set(self.home.tiles), {"rocket", "spotify", "web", "youtube", "files", "club", "settings"})
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        with patch.object(self.home, "open_device") as device, patch.object(self.home, "show_updates") as updates:
            for action in ("wifi", "bluetooth", "sound"):
                QTest.mouseClick(dialog.tiles[action], Qt.MouseButton.LeftButton)
                device.assert_called_with(action, dialog)
            QTest.mouseClick(dialog.tiles["updates"], Qt.MouseButton.LeftButton)
            updates.assert_called_once_with(dialog)
        QTest.mouseClick(dialog.back_button, Qt.MouseButton.LeftButton)
        self.assertFalse(dialog.isVisible())
        self.assertTrue(self.home.isVisible())
        dialog.deleteLater()

    def test_quick_controls_follow_real_status_and_errors(self):
        self.home.quick_status("media", {"available": True, "playing": True,
                                        "player": "org.mpris.MediaPlayer2.spotify"}, None)
        self.assertEqual(self.home.play_button.text(), "Pause")
        self.home.quick_status("audio", {"outputs": [{"default": True, "mute": True}]}, None)
        self.assertEqual(self.home.mute_button.text(), "Ton einschalten")
        with patch.object(self.home.device_client, "request") as request:
            self.home.play_button.click()
            self.home.mute_button.click()
            request.assert_not_called()
        self.home.quick_status("media", None, "Verbindung unterbrochen")
        self.home.quick_status("audio", {"outputs": []}, None)
        self.assertFalse(self.home.play_button.isEnabled())
        self.assertFalse(self.home.mute_button.isEnabled())

    def test_quick_action_prevents_double_click_and_refreshes_after_failure(self):
        self.home.preview = False
        self.home.media_state = {"player": "org.mpris.MediaPlayer2.spotify"}
        with patch.object(self.home.device_client, "request") as request:
            self.home.quick_action("media")
            self.home.quick_action("media")
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[:2],
                             ("media_playpause", {"player": "org.mpris.MediaPlayer2.spotify"}))
            request.call_args.args[2](None, "Player geschlossen")
            self.assertIn("Player geschlossen", self.home.feedback.text())
            self.assertFalse(self.home.quick_busy["media"])
        self.home.preview = True

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

    def test_rocket_tile_launches_local_helper_without_admin_rights(self):
        self.home.preview = False
        with patch("main.shutil.which", return_value="python"), patch.object(QProcess, "start") as start:
            QTest.mouseClick(self.home.tiles["rocket"], Qt.MouseButton.LeftButton)
            self.assertEqual(start.call_args.args, (sys.executable,
                [str(Path(__file__).resolve().parents[1] / "app/rocket.py")]))
            QTest.mouseClick(self.home.tiles["rocket"], Qt.MouseButton.LeftButton)
            self.assertEqual(start.call_count, 1)
        self.home.preview = True


if __name__ == "__main__":
    unittest.main()
