"""Audio routing and native UI checks without changing the host's sound."""
import copy
import json
import os
import shlex
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from audio import AudioRouter, MEMBERS, PREFIX
from devices import AudioSheet
from main import Home, STYLE
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def sink(index, name, **extra):
    return {"index": index, "name": name, "description": name, "mute": False,
            "volume": {"left": {"value_percent": "40%"}, "right": {"value_percent": "60%"}},
            **extra}


class SoundServer:
    def __init__(self):
        self.sinks = [sink(1, "box"), sink(2, "hdmi", mute=True), sink(3, "usb")]
        self.default = "box"
        self.streams = [{"index": 10, "client": 5, "owner_module": 5, "sink": 1},
                        {"index": 11, "client": 6, "owner_module": 5, "sink": 2},
                        {"index": 12, "client": None, "owner_module": 77, "sink": 1}]
        self.calls = []
        self.fail = None
        self.serial = 100

    async def __call__(self, *args):
        self.calls.append(args)
        if self.fail and self.fail(args):
            raise ValueError("Audio nicht verfügbar.")
        command = args[0]
        if command == "-f":
            return json.dumps(self.sinks if args[-1] == "sinks" else self.streams)
        if command == "get-default-sink":
            return self.default + "\n"
        if command == "load-module":
            options = dict(arg.split("=", 1) for arg in shlex.split(" ".join(args[2:])))
            properties = dict(arg.split("=", 1) for arg in options["sink_properties"].split())
            self.serial += 1
            self.sinks.append(sink(self.serial, options["sink_name"], owner_module=self.serial,
                                   properties=properties))
            for i, name in enumerate(options["slaves"].split(",")):
                target = next(s for s in self.sinks if s["name"] == name)
                self.streams.append({"index": self.serial * 10 + i, "client": None,
                                     "owner_module": self.serial, "sink": target["index"]})
            return str(self.serial)
        if command == "set-default-sink":
            assert any(s["name"] == args[1] for s in self.sinks)
            self.default = args[1]
        elif command == "move-sink-input":
            stream = next(s for s in self.streams if str(s["index"]) == args[1])
            assert stream["client"] is not None, "Never move forwarding streams"
            target = next(s for s in self.sinks if args[2] in (s["name"], str(s["index"])))
            stream["sink"] = target["index"]
        elif command in ("set-sink-mute", "set-sink-volume"):
            target = next(s for s in self.sinks if s["name"] == args[1])
            if command == "set-sink-mute":
                target["mute"] = args[2] == "1"
            else:
                target["volume"] = {"mono": {"value_percent": args[2]}}
        elif command == "unload-module":
            removed = [s["index"] for s in self.sinks if str(s.get("owner_module")) == args[1]]
            assert not any(s["client"] is not None and s["sink"] in removed for s in self.streams)
            self.sinks = [s for s in self.sinks if s["index"] not in removed]
            self.streams = [s for s in self.streams if str(s["owner_module"]) != args[1]]
        else:
            raise AssertionError(args)
        return ""


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.server = SoundServer()
        self.router = AudioRouter(self.server)

    async def test_bluetooth_switches_on_arrival_but_respects_manual_selection(self):
        await self.router.auto_bluetooth()
        self.server.sinks.append(sink(4, "bluez_output.box"))
        await self.router.auto_bluetooth()
        self.assertEqual(self.server.default, "bluez_output.box")
        await self.router.select(["2"])
        await self.router.auto_bluetooth()
        self.assertEqual(self.server.default, "hdmi")
        self.server.sinks = [s for s in self.server.sinks if s["index"] != 4]
        await self.router.auto_bluetooth()
        self.server.sinks.append(sink(4, "bluez_output.box"))
        await self.router.auto_bluetooth()
        self.assertEqual(self.server.default, "bluez_output.box")

    async def test_disabled_autoswitch_does_not_replay_old_arrivals(self):
        await self.router.auto_bluetooth()
        self.server.sinks.append(sink(4, "bluez_output.box"))
        await self.router.auto_bluetooth(False)
        await self.router.auto_bluetooth(True)
        self.assertEqual(self.server.default, "box")

    async def test_individual_volume_does_not_change_other_outputs_or_route(self):
        await self.router.select(["1", "2"])
        default = self.server.default
        await self.router.set_output_volume("hdmi", 23)
        state = await self.router.status()
        self.assertEqual([o["volume"] for o in state["outputs"]], [50, 23, 50])
        self.assertEqual(self.server.default, default)
        for name, value in (("missing", 40), ("box", -1), ("box", 101), ("box", True)):
            with self.assertRaises(ValueError):
                await self.router.set_output_volume(name, value)

    async def test_multiple_outputs_route_running_apps_and_expose_shared_controls(self):
        result = await self.router.select(["1", "2"])
        self.assertIn("2 Audioausgänge", result["message"])
        self.assertTrue(self.server.default.startswith(PREFIX))
        self.assertEqual([s["sink"] for s in self.server.streams[:3]], [101, 101, 1])
        self.assertFalse(self.server.sinks[1]["mute"])
        # A fresh worker reconstructs the selection from the live audio server.
        status = await AudioRouter(self.server).status()
        self.assertEqual([s["id"] for s in status["outputs"] if s["selected"]], ["1", "2"])
        self.assertEqual(len(status["outputs"]), 3)
        self.assertEqual(status["control"]["volume"], 50)

    async def test_switch_group_and_return_to_single_output_removes_only_owned_modules(self):
        await self.router.select(["1", "2"])
        await self.router.select(["2", "3"])
        self.assertEqual(len(self.server.sinks), 4)
        await self.router.select(["3"])
        self.assertEqual(self.server.default, "usb")
        self.assertEqual(len(self.server.sinks), 3)
        self.assertEqual([s["sink"] for s in self.server.streams], [3, 3, 1])
        status = await self.router.status()
        self.assertEqual([s["id"] for s in status["outputs"] if s["selected"]], ["3"])

    async def test_reapplying_same_selection_reuses_group(self):
        await self.router.select(["1", "2"])
        await self.router.select(["2", "1", "2"])
        self.assertEqual(sum(c[0] == "load-module" for c in self.server.calls), 1)

    async def test_missing_output_and_invalid_selection_never_change_server(self):
        before = copy.deepcopy(self.server.sinks)
        for ids in ([], None, "1", [None], ["9"], ["1", "9"]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                await self.router.select(ids)
        self.assertEqual(self.server.sinks, before)
        self.assertEqual(self.server.default, "box")
        self.assertFalse(any(c[0] in ("load-module", "set-default-sink") for c in self.server.calls))

    async def test_failed_creation_leaves_previous_route_intact(self):
        self.server.fail = lambda args: args[0] == "load-module"
        with self.assertRaises(ValueError):
            await self.router.select(["1", "2"])
        self.assertEqual(self.server.default, "box")
        self.assertEqual(len(self.server.sinks), 3)
        self.assertTrue(self.server.sinks[1]["mute"])

    async def test_failed_stream_move_restores_previous_route_mute_and_streams(self):
        before = copy.deepcopy(self.server.streams)
        self.server.fail = lambda args: args[0] == "move-sink-input" and args[1] == "11"
        with self.assertRaises(ValueError):
            await self.router.select(["1", "2"])
        self.assertEqual(self.server.default, "box")
        self.assertEqual(self.server.streams, before)
        self.assertEqual(len(self.server.sinks), 3)
        self.assertTrue(self.server.sinks[1]["mute"])

    async def test_failed_reconfiguration_keeps_existing_group(self):
        await self.router.select(["1", "2"])
        old = self.server.default
        self.server.fail = lambda args: args[0] == "set-default-sink" and args[1] != old
        with self.assertRaises(ValueError):
            await self.router.select(["1", "3"])
        self.assertEqual(self.server.default, old)
        self.assertEqual(len(self.server.sinks), 4)

    async def test_closed_player_during_switch_does_not_abort(self):
        def close(args):
            if args[0] == "move-sink-input" and args[1] == "11":
                self.server.streams = [s for s in self.server.streams if s["index"] != 11]
                return True
            return False
        self.server.fail = close
        await self.router.select(["1", "2"])
        self.assertTrue(self.server.default.startswith(PREFIX))

    async def test_existing_mute_is_preserved_on_new_group(self):
        self.server.sinks[0]["mute"] = True
        await self.router.select(["1", "2"])
        self.assertTrue((await self.router.status())["control"]["mute"])
        calls = self.server.calls
        last_move = max(i for i, call in enumerate(calls) if call[0] == "move-sink-input")
        unmute = next(i for i, call in enumerate(calls) if call == ("set-sink-mute", "box", "0"))
        self.assertGreater(unmute, last_move)

    async def test_leaving_group_preserves_master_mute_and_volume(self):
        await self.router.select(["1", "2"])
        await self.server("set-sink-mute", self.server.default, "1")
        await self.server("set-sink-volume", self.server.default, "23%")
        await self.router.select(["3"])
        control = (await self.router.status())["control"]
        self.assertTrue(control["mute"])
        self.assertEqual(control["volume"], 23)

    async def test_failed_exit_from_group_restores_individual_device_controls(self):
        await self.router.select(["1", "2"])
        await self.server("set-sink-mute", self.server.default, "1")
        await self.server("set-sink-volume", self.server.default, "23%")
        self.server.fail = lambda args: args[0] == "set-default-sink" and args[1] == "usb"
        with self.assertRaises(ValueError):
            await self.router.select(["3"])
        usb = next(s for s in (await self.router.status())["outputs"] if s["name"] == "usb")
        self.assertFalse(usb["mute"])
        self.assertEqual(usb["volume"], 50)

    async def test_cleanup_failure_is_reported_and_can_be_retried(self):
        await self.router.select(["1", "2"])
        self.server.fail = lambda args: args[0] == "unload-module"
        result = await self.router.select(["3"])
        self.assertIn("erneut übernehmen", result["message"])
        self.assertEqual(self.server.default, "usb")
        self.server.fail = None
        await self.router.select(["3"])
        self.assertEqual(len(self.server.sinks), 3)

    async def test_removed_member_is_not_listed_as_available(self):
        await self.router.select(["1", "2"])
        self.server.sinks = [s for s in self.server.sinks if s["index"] != 2]
        state = await self.router.status()
        self.assertEqual([s["id"] for s in state["outputs"] if s["selected"]], ["1"])
        await self.router.select(["1"])
        self.assertEqual(self.server.default, "box")


class AudioScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(1024, 600)
        self.home.show()
        self.sheet = AudioSheet(self.home, self.home.device_client)
        self.sheet.show()
        self.flush()

    def flush(self):
        for _ in range(5):
            self.app.processEvents()

    def tearDown(self):
        self.sheet.volume_timer.stop()
        self.sheet.busy = False
        self.sheet.reject()
        self.sheet.deleteLater()
        self.home.close()
        self.home.deleteLater()
        self.flush()

    def test_individual_slider_preserves_other_box_levels_and_pending_selection(self):
        self.sheet.list.item(1).setCheckState(Qt.CheckState.Checked)
        slider = self.sheet.output_sliders[1]
        slider.setValue(31)
        self.assertFalse(self.sheet.back.isEnabled())
        self.assertFalse(self.sheet.choose.isEnabled())
        slider.commit()
        self.flush()
        self.assertEqual(self.sheet.checked_ids(), ["1", "2"])
        self.assertEqual([s.value() for s in self.sheet.output_sliders], [55, 31, 55])
        self.assertTrue(self.sheet.back.isEnabled())

    def test_choose_multiple_outputs_and_restore_on_reopen(self):
        self.sheet.list.item(1).setCheckState(Qt.CheckState.Checked)
        self.sheet.choose.click()
        self.flush()
        self.assertEqual(self.sheet.checked_ids(), ["1", "2"])
        self.assertIn("Wird verwendet", self.sheet.list.item(1).text())
        self.sheet.load()
        self.flush()
        self.assertEqual(self.sheet.checked_ids(), ["1", "2"])

    def test_empty_selection_is_disabled_and_shared_mute_uses_master(self):
        self.sheet.list.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(self.sheet.choose.isEnabled())
        self.home.quick_status("audio", {"outputs": [{"default": False, "selected": True}],
                                         "control": {"mute": True}}, None)
        self.assertTrue(self.home.mute_button.isEnabled())
        self.assertEqual(self.home.mute_button.text(), "Ton einschalten")

    def test_volume_keeps_unapplied_selection_and_blocks_switch_until_saved(self):
        self.sheet.list.item(1).setCheckState(Qt.CheckState.Checked)
        self.sheet.slider.setValue(37)
        self.assertFalse(self.sheet.choose.isEnabled())
        self.assertFalse(self.sheet.back.isEnabled())
        self.sheet.apply_volume()
        self.flush()
        self.assertEqual(self.sheet.slider.value(), 37)
        self.assertEqual(self.sheet.checked_ids(), ["1", "2"])
        self.assertEqual(self.home.device_client.preview_audio_ids, ["1"])
        self.assertTrue(self.sheet.choose.isEnabled())

    def test_checkbox_can_be_toggled_using_keyboard(self):
        self.sheet.list.setCurrentRow(1)
        self.sheet.list.setFocus()
        QTest.keyClick(self.sheet.list, Qt.Key.Key_Space)
        self.assertEqual(self.sheet.checked_ids(), ["1", "2"])

    def test_missing_devices_keep_reload_available(self):
        self.sheet.loaded({"outputs": [], "control": None}, None)
        self.assertFalse(self.sheet.choose.isEnabled())
        self.assertFalse(self.sheet.slider.isEnabled())
        self.assertTrue(self.sheet.reload.isEnabled())

    def test_failed_selection_keeps_checks_and_error_for_retry(self):
        self.sheet.list.item(1).setCheckState(Qt.CheckState.Checked)
        original = self.sheet.client.request
        def reply(operation, args=None, callback=None):
            if operation == "audio_outputs":
                callback(None, "Box nicht mehr verbunden.")
            else:
                original(operation, args, callback)
        with patch.object(self.sheet.client, "request", side_effect=reply):
            self.sheet.choose.click()
            self.flush()
        self.assertEqual(self.sheet.checked_ids(), ["1", "2"])
        self.assertEqual(self.sheet.message.text(), "Box nicht mehr verbunden.")
        self.assertTrue(self.sheet.choose.isEnabled())

    def test_layout_fits_small_screen(self):
        self.assertLessEqual(self.sheet.height(), 600)
        for control in self.sheet.controls:
            self.assertTrue(self.sheet.rect().contains(control.geometry()))
        self.assertGreaterEqual(self.sheet.list.viewport().height(), 3 * 64)


if __name__ == "__main__":
    unittest.main()
