"""Behavioral checks for the public launcher and disruptive action boundaries."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from main import Home, SettingsDialog, STYLE, UpdateDialog
from maintenance import MaintenancePage
from devices import AudioSheet, BluetoothSheet, BrightnessSheet, WifiSheet
from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox


class HomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if sys.platform == "win32":
            for name in ("segoeui.ttf", "segoeuib.ttf"):
                QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name))
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

    def test_widget_seek_is_cancelled_when_track_changes(self):
        tile = self.home.music_tile
        state = {"player": "org.mpris.MediaPlayer2.spotify", "track_id": "/first",
                 "duration": 200, "position": 10, "can_seek": True}
        tile.update_state(state)
        tile.capture_seek()
        tile.position.setValue(500)
        tile.update_state({**state, "track_id": "/second"})
        with patch.object(self.home, "quick_action") as action:
            tile.seek(500)
            action.assert_not_called()
        self.assertFalse(tile.position.delay.isActive())

    def test_widget_output_and_volume_actions(self):
        tile = self.home.music_tile
        tile.update_audio({"outputs": [{"id": "7", "description": "USB", "selected": True}],
                           "control": {"volume": 42}})
        self.assertEqual(tile.volume.value(), 42)
        with patch.object(self.home, "quick_action") as action:
            tile.choose_output(0)
            action.assert_called_with("audio", "output", id="7")
            tile.volume.committed.emit(28)
            action.assert_called_with("audio", "volume", value=28)

    def test_all_tiles_are_clickable_without_launching_in_preview(self):
        with patch.object(QProcess, "start") as start, patch.object(self.home, "show_settings") as settings, \
                patch.object(self.home, "show_apps") as apps, \
                patch.object(self.home, "show_gamemodes") as gamemodes:
            for action, tile in self.home.tiles.items():
                QTest.mouseClick(tile, Qt.MouseButton.LeftButton)
                self.assertEqual(self.home.last_action, action)
                if action == "settings":
                    settings.assert_called_once_with()
                elif action == "apps":
                    apps.assert_called_once_with()
                elif action == "gamemodes":
                    gamemodes.assert_called_once_with()
            start.assert_not_called()

    def test_controls_fit_small_laptop(self):
        for size in ((1024, 600), (800, 540), (1366, 768)):
            self.home.resize(*size)
            self.app.processEvents()
            self.assertEqual((self.home.width(), self.home.height()), size)
            for tile in (*self.home.tiles.values(), self.home.music_tile):
                self.assertTrue(self.home.rect().contains(tile.geometry()))
                self.assertGreaterEqual(tile.width(), 150)
                self.assertGreaterEqual(tile.height(), 104)
            settings = self.home.tiles["settings"].geometry()
            music = self.home.music_tile.geometry()
            self.assertGreater(music.left(), settings.right())
            self.assertEqual(music.top(), settings.top())
            games = self.home.tiles["gamemodes"].geometry()
            self.assertGreater(games.top(), settings.bottom())
            self.assertEqual(games.left(), self.home.tiles["apps"].geometry().left())
            self.assertEqual(games.right(), settings.right())
            for button in self.home.music_tile.buttons.values():
                self.assertTrue(self.home.music_tile.rect().contains(button.geometry()))

    def test_settings_navigation_and_return(self):
        self.assertEqual(set(self.home.tiles), {"apps", "gamemodes", "settings"})
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        with patch.object(QProcess, "start") as start:
            for action, page_type in (("wifi", WifiSheet), ("bluetooth", BluetoothSheet),
                                      ("sound", AudioSheet), ("brightness", BrightnessSheet),
                                      ("updates", UpdateDialog)):
                QTest.mouseClick(dialog.nav_buttons[action], Qt.MouseButton.LeftButton)
                self.app.processEvents()
                self.assertIsInstance(dialog.page, page_type)
                self.assertFalse(dialog.page.isWindow())
                self.assertTrue(dialog.page.isVisible())
                self.assertTrue(dialog.sidebar.isVisible())
                self.assertTrue(dialog.nav_buttons[action].isChecked())
                self.assertEqual(sum(b.isChecked() for b in dialog.nav_buttons.values()), 1)
            QTest.mouseClick(dialog.page.start, Qt.MouseButton.LeftButton)
            self.assertTrue(dialog.page.state.isHidden())
            start.assert_not_called()
        QTest.mouseClick(dialog.back_button, Qt.MouseButton.LeftButton)
        self.assertFalse(dialog.isVisible())
        self.assertTrue(self.home.isVisible())
        dialog.deleteLater()

    def test_settings_fit_small_screens(self):
        for size in ((800, 540), (1024, 600), (1366, 768)):
            self.home.resize(*size)
            dialog = SettingsDialog(self.home)
            dialog.show()
            self.app.processEvents()
            self.assertLessEqual(dialog.width(), size[0])
            self.assertLessEqual(dialog.height(), size[1])
            for button in dialog.nav_buttons.values():
                self.assertTrue(dialog.sidebar.rect().contains(button.geometry()))
            self.assertTrue(dialog.rect().contains(dialog.back_button.mapTo(dialog, dialog.back_button.rect().center())))
            for action in dialog.nav_buttons:
                QTest.mouseClick(dialog.nav_buttons[action], Qt.MouseButton.LeftButton)
                self.app.processEvents()
                self.assertEqual(dialog.content.horizontalScrollBar().maximum(), 0, (size, action))
                self.assertLessEqual(dialog.width(), size[0])
                self.assertLessEqual(dialog.height(), size[1])
                self.assertTrue(dialog.rect().contains(dialog.content.geometry()))
            dialog.close()
            dialog.deleteLater()

    def test_maintenance_sections_block_navigation_during_changes(self):
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        for section in ("remote", "recovery"):
            dialog.select_section(section)
            self.assertIsInstance(dialog.page, MaintenancePage)
            page = dialog.page
            page.working(True)
            self.assertFalse(dialog.back_button.isEnabled())
            dialog.select_section("wifi")
            dialog.reject()
            self.assertIs(dialog.page, page)
            self.assertTrue(dialog.isVisible())
            page.working(False)
        dialog.reject()
        dialog.deleteLater()

    def test_settings_wait_for_volume_and_brightness_changes(self):
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        for section in ("sound", "brightness"):
            QTest.mouseClick(dialog.nav_buttons[section], Qt.MouseButton.LeftButton)
            self.app.processEvents()
            page = dialog.page
            QTest.keyClick(page.slider, Qt.Key.Key_Right)
            self.assertFalse(dialog.back_button.isEnabled())
            self.assertTrue(all(not button.isEnabled() for button in dialog.nav_buttons.values()))
            dialog.select_section("updates")
            dialog.reject()
            self.assertIs(dialog.page, page)
            self.assertTrue(dialog.isVisible())
            QTest.qWait(450)
            self.assertTrue(dialog.back_button.isEnabled())
            self.assertTrue(all(button.isEnabled() for button in dialog.nav_buttons.values()))
        dialog.reject()
        dialog.deleteLater()

    def test_settings_escape_closes_the_whole_window(self):
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        page = dialog.page
        QTest.keyClick(page.scan, Qt.Key.Key_Escape)
        self.assertFalse(dialog.isVisible())
        self.assertTrue(page.closed)
        self.assertTrue(self.home.isVisible())
        dialog.deleteLater()

    def test_settings_leave_bluetooth_stops_search_and_ignores_late_replies(self):
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        QTest.mouseClick(dialog.nav_buttons["bluetooth"], Qt.MouseButton.LeftButton)
        self.app.processEvents()
        page = dialog.page
        QTest.mouseClick(page.scan, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertTrue(page.searching)
        callbacks = []
        with patch.object(page.client, "request", side_effect=lambda op, args=None, callback=None:
                          callbacks.append(callback)) as request:
            page.load(quiet=True)
            QTest.mouseClick(dialog.nav_buttons["updates"], Qt.MouseButton.LeftButton)
            request.assert_any_call("bt_scan", {"enabled": False}, None)
        self.assertTrue(page.closed)
        self.assertFalse(page.timer.isActive())
        self.assertFalse(page.search_timer.isActive())
        with patch.object(page, "loaded") as loaded:
            callbacks[0]({}, None)
            loaded.assert_not_called()
        dialog.reject()
        dialog.deleteLater()

    def test_settings_keep_update_result_and_block_navigation_while_running(self):
        dialog = SettingsDialog(self.home)
        dialog.show()
        self.app.processEvents()
        QTest.mouseClick(dialog.nav_buttons["updates"], Qt.MouseButton.LeftButton)
        update = dialog.page
        with patch.object(update.process, "start"):
            update.begin(preview=False)
        self.assertFalse(dialog.back_button.isEnabled())
        dialog.select_section("wifi")
        dialog.close()
        self.assertIs(dialog.page, update)
        self.assertTrue(dialog.isVisible())
        update.output.setPlainText("Testausgabe")
        update.finished_update(0, QProcess.ExitStatus.NormalExit)
        QTest.mouseClick(dialog.nav_buttons["wifi"], Qt.MouseButton.LeftButton)
        self.app.processEvents()
        QTest.mouseClick(dialog.nav_buttons["updates"], Qt.MouseButton.LeftButton)
        self.assertIs(dialog.page, update)
        self.assertEqual(update.output.toPlainText(), "Testausgabe")
        self.assertIn("erfolgreich", update.state.text())
        dialog.reject()
        dialog.deleteLater()

    def test_quick_controls_follow_real_status_and_errors(self):
        self.home.quick_status("media", {"available": True, "playing": True,
                                        "player": "org.mpris.MediaPlayer2.spotify"}, None)
        self.assertEqual(self.home.play_button.accessibleName(), "Pause")
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

    def test_music_metadata_capabilities_and_closed_player(self):
        state = {"available": True, "playing": True, "player": "org.mpris.MediaPlayer2.spotify",
                 "player_name": "Spotify", "title": "Ein langer Titel " * 15,
                 "artist": "<b>Interpret</b>", "can_previous": False, "can_next": True}
        self.home.quick_status("media", state, None)
        music = self.home.music_tile
        self.app.processEvents()
        self.assertEqual(music.track.toolTip(), state["title"])
        self.assertEqual(music.artist.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(music.artist.full_text, state["artist"])
        self.assertEqual(music.source.full_text, "Spotify · Läuft")
        self.assertFalse(music.buttons["previous"].isEnabled())
        self.assertTrue(music.buttons["next"].isEnabled())
        self.assertEqual(self.home.width(), 1024)
        self.home.quick_status("media", {"available": False}, None)
        self.assertEqual(music.track.full_text, "Bereit für Musik")
        self.assertEqual(music.artist.full_text, "Spotify oder YouTube öffnen")
        self.assertTrue(all(not button.isEnabled() for button in music.buttons.values()))
        self.home.quick_status("media", None, "Player geschlossen")
        self.assertEqual(music.track.full_text, "Player nicht erreichbar")

    def test_music_skip_buttons_target_the_displayed_player(self):
        self.home.preview = False
        state = {"player": "org.mpris.MediaPlayer2.firefox", "available": True,
                 "playing": False, "can_previous": True, "can_next": True}
        try:
            for action in ("previous", "next"):
                self.home.quick_status("media", state, None)
                with patch.object(self.home.device_client, "request") as request:
                    QTest.mouseClick(self.home.music_tile.buttons[action], Qt.MouseButton.LeftButton)
                    request.assert_called_once()
                    self.assertEqual(request.call_args.args[:2],
                                     (f"media_{action}", {"player": state["player"]}))
                    self.assertTrue(all(not button.isEnabled()
                                        for button in self.home.music_tile.buttons.values()))
                    request.call_args.args[2]({}, None)
                    self.assertFalse(self.home.quick_busy["media"])
        finally:
            self.home.preview = True

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
        self.home.show_gamemodes()
        dialog = self.home.gamemodes_page
        dialog.search.setText("Rocket Launch")
        with patch("main.shutil.which", return_value="python"), patch.object(QProcess, "start") as start:
            QTest.mouseClick(dialog.tiles["rocket"], Qt.MouseButton.LeftButton)
            self.assertEqual(start.call_args.args, (sys.executable,
                [str(Path(__file__).resolve().parents[1] / "app/rocket.py")]))
            self.home.show_gamemodes()
            QTest.mouseClick(dialog.tiles["rocket"], Qt.MouseButton.LeftButton)
            self.assertEqual(start.call_count, 1)
        self.home.preview = True


if __name__ == "__main__":
    unittest.main()
