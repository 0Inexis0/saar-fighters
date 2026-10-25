"""Device contract tests without touching the host's network, audio or power."""
import asyncio
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from dbus_next import DBusError, Variant
from backend import Backend, NM, NM_PATH, UP, UP_PATH, plain
from hardware import security_mode, status_labels, wifi_password_valid
from devices import AudioSheet, BluetoothSheet, DeviceClient, WifiSheet
from main import CLUB_WEBSITE, Home, STYLE
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog


class PresentationTests(unittest.TestCase):
    def test_vm_never_invents_battery_or_radio(self):
        labels = status_labels({
            "network": {"state": 70, "type": "802-3-ethernet"},
            "bluetooth": {"available": False},
            "power": {"percentage": None, "plugged": None},
        })
        self.assertEqual(labels, ("Kabel verbunden", "Bluetooth: kein Adapter",
                                 "Netzteil: unbekannt", "Kein Akku erkannt"))

    def test_connected_and_charging_states(self):
        labels = status_labels({
            "network": {"state": 50, "type": "802-11-wireless", "connectivity": 1},
            "bluetooth": {"available": True, "powered": True,
                          "devices": [{"connected": True}, {"connected": False}]},
            "power": {"percentage": 41.6, "state": 1, "plugged": True},
        })
        self.assertEqual(labels, ("WLAN verbunden", "Bluetooth: 1 verbunden",
                                 "Netzteil verbunden", "Akku 42 % · lädt"))
        self.assertNotIn("Internet", labels[0])  # local link is not internet access

    def test_failures_are_unknown_not_disconnected(self):
        for value in status_labels({key: {"error": True} for key in ("network", "bluetooth", "power")}):
            self.assertIn("unbekannt", value)

    def test_security_flags_and_password_boundaries(self):
        for flags, wpa, rsn, mode in ((0, 0, 0, "open"), (1, 0, 0, "unsupported"),
                                     (1, 256, 0, "wpa-psk"), (1, 0, 1024, "sae"),
                                     (1, 0, 512, "enterprise"), (1, 0, 2048, "owe")):
            self.assertEqual(security_mode(flags, wpa, rsn), mode)
        self.assertFalse(wifi_password_valid("wpa-psk", "short"))
        self.assertTrue(wifi_password_valid("wpa-psk", "12345678"))
        self.assertTrue(wifi_password_valid("wpa-psk", "a" * 64))
        self.assertFalse(wifi_password_valid("wpa-psk", "z" * 64))
        self.assertFalse(wifi_password_valid("enterprise", "12345678"))


class BackendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.backend = Backend(Mock())

    async def test_brightness_routes_reads_and_selected_display_changes(self):
        with patch("backend.brightness_request", new_callable=AsyncMock) as request:
            await self.backend.perform("brightness", {})
            request.assert_awaited_with()
            await self.backend.perform("brightness_set", {"id": "display0", "value": 45})
            request.assert_awaited_with("display0", 45)
            request.reset_mock()
            for args in ({"value": 45}, {"id": "", "value": 45}):
                with self.assertRaises(ValueError):
                    await self.backend.perform("brightness_set", args)
            request.assert_not_awaited()

    async def test_media_controls_route_only_supported_actions_to_selected_player(self):
        player = "org.mpris.MediaPlayer2.spotify"
        with patch("backend.media_request", new_callable=AsyncMock) as request:
            for action in ("playpause", "previous", "next"):
                await self.backend.perform(f"media_{action}", {"player": player})
                request.assert_awaited_with(player, action)
            request.reset_mock()
            for operation, args in (("media_next", {}), ("media_previous", {"player": "other"}),
                                    ("media_quit", {"player": player})):
                with self.assertRaises(ValueError):
                    await self.backend.perform(operation, args)
            request.assert_not_awaited()

    async def test_desktop_mute_toggles_current_output_without_changing_volume(self):
        self.backend.pactl = AsyncMock(return_value="")
        await self.backend.perform("audio_toggle", {})
        self.backend.pactl.assert_awaited_once_with("set-sink-mute", "@DEFAULT_SINK@", "toggle")

    async def test_extended_media_controls_preserve_track_and_values(self):
        player = "org.mpris.MediaPlayer2.spotify"
        with patch("backend.media_request", new_callable=AsyncMock) as request:
            await self.backend.perform("media_seek", {"player": player, "position": 41.5, "track_id": "/track/one"})
            request.assert_awaited_with(player, "seek", position=41.5, track_id="/track/one")
            for action, value in (("volume", 50), ("shuffle", True), ("repeat", "Track")):
                await self.backend.perform("media_" + action, {"player": player, "value": value})
                request.assert_awaited_with(player, action, value=value)

    async def test_absent_physical_power_is_unknown(self):
        self.backend.call = AsyncMock(return_value=[[]])
        self.assertEqual(await self.backend.power(), {"percentage": None, "state": 0, "plugged": None})

    async def test_mouse_battery_is_not_laptop_battery(self):
        self.backend.call = AsyncMock(return_value=[["/mouse"]])
        self.backend.props = AsyncMock(return_value={
            "Type": 2, "PowerSupply": False, "IsPresent": True, "Percentage": 90})
        self.assertIsNone((await self.backend.power())["percentage"])

    async def test_upower_aggregate_and_charger(self):
        self.backend.call = AsyncMock(side_effect=[[["/battery", "/ac"]], ["/display"]])
        self.backend.props = AsyncMock(side_effect=[
            {"Type": 2, "PowerSupply": True, "IsPresent": True},
            {"Type": 1, "Online": True},
            {"IsPresent": True, "Percentage": 68, "State": 1},
            {"OnBattery": False},
        ])
        self.assertEqual(await self.backend.power(), {"percentage": 68, "state": 1, "plugged": True})

    def wifi_fixture(self, saved=""):
        self.backend.wifi = AsyncMock(return_value={"networks": [{
            "path": "/ap", "device": "/wlan", "name": "Vereinsheim ä",
            "mode": "wpa-psk", "connected": False, "saved": saved,
        }]})

    async def test_saved_wifi_reused_and_activation_waited_for(self):
        self.wifi_fixture("/saved")
        self.backend.call = AsyncMock(return_value=["/active"])
        self.backend.props = AsyncMock(side_effect=[{"State": 1}, {"State": 2}])
        with patch("backend.asyncio.sleep", new_callable=AsyncMock) as sleep:
            self.assertEqual(await self.backend.wifi_connect({"path": "/ap"}), {"message": "WLAN verbunden."})
            sleep.assert_awaited_once_with(1)
        self.backend.call.assert_awaited_once_with(NM, NM_PATH, NM, "ActivateConnection", "ooo",
                                                  ["/saved", "/wlan", "/ap"])

    async def test_new_wifi_uses_bus_secret_and_current_user_without_tty(self):
        self.wifi_fixture()
        self.backend.call = AsyncMock(return_value=["/saved", "/active"])
        self.backend.props = AsyncMock(side_effect=[{"Ssid": list("Vereinsheim ä".encode())}, {"State": 2}])
        with patch("backend.pwd.getpwuid", return_value=Mock(pw_name="saar")):
            await self.backend.wifi_connect({"path": "/ap", "password": "testpassword"})
        args = self.backend.call.call_args.args
        self.assertEqual(args[3:5], ("AddAndActivateConnection", "a{sa{sv}}oo"))
        settings = plain(args[5][0])
        self.assertEqual(settings["connection"]["permissions"], ["user:saar:"])
        self.assertEqual(settings["802-11-wireless-security"]["psk"], "testpassword")
        self.assertEqual(settings["802-11-wireless"]["ssid"], "Vereinsheim ä".encode())

    async def test_invalid_wifi_cannot_reach_mutation(self):
        self.wifi_fixture()
        self.backend.call = AsyncMock()
        for args in ({"path": "/arbitrary", "password": "12345678"},
                     {"path": "/ap", "password": "short"}):
            with self.assertRaises(ValueError):
                await self.backend.wifi_connect(args)
        self.backend.call.assert_not_called()

    async def test_status_partial_failure_preserves_other_devices(self):
        self.backend.network = AsyncMock(side_effect=RuntimeError())
        self.backend.bluetooth = AsyncMock(return_value={"available": False})
        self.backend.power = AsyncMock(return_value={"percentage": 50})
        result = await self.backend.status()
        self.assertEqual(result["network"], {"error": True})
        self.assertEqual(result["power"]["percentage"], 50)

    async def test_unsolicited_bluetooth_pairing_rejected(self):
        with self.assertRaises(DBusError):
            await self.backend.agent.question("confirm", "/unknown", "123456")

    async def test_pairing_requires_explicit_confirmation(self):
        self.backend.pairing_devices.add("/box")
        with patch("backend.emit") as output:
            task = asyncio.create_task(self.backend.agent.question("confirm", "/box", "123456"))
            await asyncio.sleep(0)
            event = output.call_args.args[0]
            self.assertFalse(task.done())
            await self.backend.perform("pairing_reply", {"token": event["token"], "accepted": False})
            with self.assertRaises(DBusError):
                await task
            self.assertFalse(self.backend.agent.pending)

    async def test_audio_stereo_and_bounds(self):
        self.backend.pactl = AsyncMock(side_effect=[
            '[{"index":4,"name":"box","description":"Boxen","mute":false,'
            '"volume":{"left":{"value_percent":"40%"},"right":{"value_percent":"60%"}}}]',
            "box\n",
        ])
        self.assertEqual((await self.backend.audio())["outputs"][0]["volume"], 50)
        self.backend.pactl = AsyncMock()
        await self.backend.perform("audio_volume", {"value": 200})
        self.backend.pactl.assert_awaited_once_with("set-sink-volume", "@DEFAULT_SINK@", "100%")

    async def test_bluetooth_power_cycle_can_start_new_discovery(self):
        self.backend.bluetooth = AsyncMock(return_value={
            "available": True, "adapters": [{"path": "/adapter", "Powered": True}]})
        self.backend.set_prop = AsyncMock()
        self.backend.call = AsyncMock()
        self.backend.discovery_owned.add("/adapter")
        await self.backend.perform("bt_power", {"enabled": False})
        self.assertFalse(self.backend.discovery_owned)
        await self.backend.perform("bt_scan", {"enabled": True})
        self.assertEqual(self.backend.call.call_args.args[3], "StartDiscovery")


class DeviceScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(1024, 600)
        self.home.show()
        self.app.processEvents()
        self.sheets = []

    def tearDown(self):
        for sheet in self.sheets:
            sheet.busy = False
            sheet.reject()
            sheet.deleteLater()
        self.home.device_client.stop()
        self.home.close()
        self.home.deleteLater()
        self.app.processEvents()

    def sheet(self, kind):
        sheet = kind(self.home, self.home.device_client)
        self.sheets.append(sheet)
        sheet.show()
        self.app.processEvents()
        return sheet

    def test_all_screens_fit_and_use_same_style(self):
        for kind in (WifiSheet, BluetoothSheet, AudioSheet):
            sheet = self.sheet(kind)
            self.assertEqual(sheet.objectName(), "deviceSheet")
            self.assertLessEqual(sheet.height(), 600)
            self.assertLessEqual(sheet.width(), 1024)
            for control in sheet.controls:
                if control.isVisible():
                    self.assertTrue(sheet.rect().contains(control.geometry()))
            sheet.reject()

    def test_missing_adapters_disable_actions(self):
        sheet = self.sheet(WifiSheet)
        sheet.loaded({"available": False, "enabled": True, "hardware_enabled": True, "networks": []}, None)
        self.assertIn("Kein WLAN", sheet.message.text())
        self.assertFalse(sheet.toggle.isEnabled())
        self.assertFalse(sheet.connect.isEnabled())
        bt = self.sheet(BluetoothSheet)
        bt.loaded({"available": False, "powered": False, "devices": []}, None)
        self.assertFalse(bt.connect.isEnabled())

    def test_password_hidden_and_invalid_password_not_sent(self):
        sheet = self.sheet(WifiSheet)
        sheet.list.setCurrentRow(1)
        sheet.password.setText("short")
        with patch.object(sheet.client, "request") as request:
            QTest.mouseClick(sheet.connect, Qt.MouseButton.LeftButton)
            request.assert_not_called()
        self.assertIn("Passwort", sheet.message.text())
        self.assertEqual(sheet.password.echoMode(), sheet.password.EchoMode.Password)

    def test_failed_toggle_keeps_error_visible(self):
        sheet = self.sheet(WifiSheet)
        with patch.object(sheet.client, "request", side_effect=lambda op, args, cb: cb(None, "Freigabe fehlt.")), \
             patch.object(sheet.client, "refresh_status"):
            sheet.toggle.click()
        self.assertEqual(sheet.message.text(), "Freigabe fehlt.")

    def test_rejected_pairing_returns_false(self):
        sheet = self.sheet(BluetoothSheet)
        sheet.pairing_event({"event": "pairing", "kind": "confirm", "token": "token", "code": "123456"})
        with patch.object(sheet.client, "request") as request:
            sheet.question.reject()
            self.assertEqual(request.call_args.args[0], "pairing_reply")
            self.assertFalse(request.call_args.args[1]["accepted"])

    def test_scan_cannot_be_abandoned_before_start_reply(self):
        sheet = self.sheet(BluetoothSheet)
        callbacks = []
        with patch.object(sheet.client, "request", side_effect=lambda op, args, cb: callbacks.append(cb)):
            sheet.search()
        sheet.reject()
        self.assertFalse(sheet.closed)
        callbacks[0]({}, None)
        self.assertFalse(sheet.busy)
        self.assertTrue(sheet.search_timer.isActive())
        with patch.object(sheet.client, "request") as request:
            sheet.reject()
            self.assertEqual(request.call_args.args[:2], ("bt_scan", {"enabled": False}))

    def test_website_uses_official_url(self):
        self.assertEqual(self.home.command_for("club"), ["firefox", "--new-window", CLUB_WEBSITE])
        self.assertEqual(CLUB_WEBSITE, "https://www.saarfighters-as.de/")

    def test_late_reply_after_close_is_ignored(self):
        sheet = self.sheet(AudioSheet)
        captured = []
        with patch.object(sheet.client, "request", side_effect=lambda op, args, cb: captured.append(cb)):
            sheet.load()
        sheet.reject()
        with patch.object(sheet, "loaded") as loaded:
            captured[0]({"outputs": []}, None)
            loaded.assert_not_called()


if __name__ == "__main__":
    unittest.main()
