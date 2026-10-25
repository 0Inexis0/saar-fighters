"""Exercise the Plasma protocol and real Qt input without changing host hardware."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from dbus_next import MessageType, Variant
from brightness import brightness_request, DISPLAY, PATH, SERVICE
from devices import BrightnessSheet
from main import Home, SettingsDialog, STYLE
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class BrightnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.raw = 400
        self.maximum = 800
        self.bus = Mock()
        self.bus.connect = AsyncMock(return_value=self.bus)
        self.bus.call = AsyncMock(side_effect=self.reply)
        self.factory = patch("brightness.MessageBus", return_value=self.bus)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    async def reply(self, message):
        self.assertEqual(message.destination, SERVICE)
        if message.member == "Get":
            body = [Variant("as", ["display0"])]
        elif message.member == "GetAll":
            body = [{"Label": Variant("s", "Laptop"), "IsInternal": Variant("b", True),
                     "MaxBrightness": Variant("i", self.maximum), "Brightness": Variant("i", self.raw)}]
        else:
            self.assertEqual((message.path, message.interface, message.member, message.signature),
                             (PATH + "/display0", DISPLAY, "SetBrightness", "iu"))
            self.assertEqual(message.body[1], 1)
            self.raw = message.body[0]
            body = []
        return Mock(message_type=MessageType.METHOD_RETURN, body=body)

    async def test_reads_current_hardware_scale(self):
        result = await brightness_request()
        self.assertEqual(result["displays"][0]["value"], 50)
        self.assertEqual(result["displays"][0]["name"], "Laptop")
        self.bus.disconnect.assert_called_once()

    async def test_writes_selected_display_and_reads_back_hardware_rounding(self):
        self.maximum = 7
        self.raw = 3
        result = await brightness_request("display0", 50)
        self.assertEqual(self.raw, 4)
        self.assertEqual(result["displays"][0]["value"], 57)
        self.bus.disconnect.assert_called_once()

    async def test_both_slider_endpoints_are_valid(self):
        for value, raw in ((0, 0), (100, 800)):
            await brightness_request("display0", value)
            self.assertEqual(self.raw, raw)

    async def test_invalid_values_never_connect_or_write(self):
        for value in (-1, 101, None, "50", True, 50.5):
            with self.assertRaises(ValueError):
                await brightness_request("display0", value)
        self.bus.connect.assert_not_called()

    async def test_disconnected_or_arbitrary_target_never_changes_another_screen(self):
        with self.assertRaisesRegex(ValueError, "nicht mehr verfügbar"):
            await brightness_request("display999", 80)
        self.assertEqual(self.raw, 400)
        self.bus.disconnect.assert_called_once()

    async def test_unsupported_range_is_not_exposed_as_a_working_slider(self):
        self.maximum = 0
        self.assertEqual(await brightness_request(), {"displays": []})

    async def test_missing_service_is_explained_and_connection_closed(self):
        self.bus.call.side_effect = None
        self.bus.call.return_value = Mock(message_type=MessageType.ERROR,
            error_name="org.freedesktop.DBus.Error.ServiceUnknown")
        with self.assertRaisesRegex(ValueError, "KDE-Energieverwaltung"):
            await brightness_request()
        self.bus.disconnect.assert_called_once()

    async def test_timeout_closes_connection(self):
        self.bus.call.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            await brightness_request()
        self.bus.disconnect.assert_called_once()


class BrightnessScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(800, 540)
        self.home.show()
        self.settings = SettingsDialog(self.home)
        self.settings.show()
        self.sheet = BrightnessSheet(self.settings, self.home.device_client)
        self.sheet.show()
        self.app.processEvents()

    def tearDown(self):
        self.sheet.timer.stop()
        self.sheet.busy = False
        self.sheet.reject()
        self.settings.close()
        self.home.device_client.stop()
        self.home.close()
        self.home.deleteLater()
        self.app.processEvents()

    def test_initial_read_does_not_write_and_controls_fit(self):
        self.assertEqual(self.sheet.slider.value(), 70)
        self.assertFalse(self.sheet.timer.isActive())
        self.assertLessEqual(self.sheet.width(), 800)
        self.assertLessEqual(self.sheet.height(), 540)
        for control in self.sheet.controls + [self.sheet.back]:
            self.assertTrue(self.sheet.rect().contains(control.geometry()))

    def test_keyboard_change_is_debounced_and_retained_in_preview(self):
        QTest.keyClick(self.sheet.slider, Qt.Key.Key_Right)
        QTest.keyClick(self.sheet.slider, Qt.Key.Key_Right)
        self.sheet.reject()
        self.assertFalse(self.sheet.closed)
        QTest.qWait(450)
        self.assertEqual(self.home.device_client.preview_brightness, 72)
        self.assertEqual(self.sheet.level.text(), "Helligkeit: 72 %")
        self.assertTrue(self.sheet.back.isEnabled())
        self.sheet.load()
        self.app.processEvents()
        self.assertEqual(self.sheet.slider.value(), 72)

    def test_drag_waits_for_release_and_sends_only_last_value(self):
        captured = []
        with patch.object(self.sheet.client, "request", side_effect=lambda *args: captured.append(args)):
            self.sheet.slider.setSliderDown(True)
            self.sheet.slider.setValue(40)
            self.sheet.slider.setValue(30)
            QTest.qWait(450)
            self.assertEqual(captured, [])
            self.sheet.slider.setSliderDown(False)
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0][:2], ("brightness_set", {"id": "preview", "value": 30}))
            self.sheet.reject()
            self.assertFalse(self.sheet.closed)
            captured[0][2](None, "Bildschirm wurde getrennt.")
        self.assertIn("getrennt", self.sheet.message.text())
        self.assertFalse(self.sheet.slider.isEnabled())
        self.assertTrue(self.sheet.reload.isEnabled())
        self.assertTrue(self.sheet.back.isEnabled())

    def test_empty_list_and_service_failure_disable_slider_and_allow_retry(self):
        self.sheet.loaded({"displays": []}, None)
        self.assertFalse(self.sheet.slider.isEnabled())
        self.assertIn("Kein steuerbarer Bildschirm", self.sheet.message.text())
        self.sheet.loaded(None, "Energieverwaltung nicht verfügbar.")
        self.assertIn("Energieverwaltung", self.sheet.message.text())
        QTest.mouseClick(self.sheet.reload, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertTrue(self.sheet.slider.isEnabled())

    def test_screen_selection_does_not_send_a_write(self):
        self.sheet.loaded({"displays": [{"id": "one", "name": "Laptop", "value": 60},
                                         {"id": "two", "name": "Monitor", "value": 35}]}, None)
        with patch.object(self.sheet.client, "request") as request:
            rect = self.sheet.list.visualItemRect(self.sheet.list.item(1))
            QTest.mouseClick(self.sheet.list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            self.assertEqual(self.sheet.slider.value(), 35)
            QTest.qWait(450)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
