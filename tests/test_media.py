import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from dbus_next import Variant
from media import choose_player, player_state, media_request


class MediaTests(unittest.IsolatedAsyncioTestCase):
    def test_playing_browser_wins_over_paused_spotify(self):
        spotify = {"available": True, "playing": False, "player": "org.mpris.MediaPlayer2.spotify"}
        browser = {"available": True, "playing": True, "player": "org.mpris.MediaPlayer2.firefox"}
        self.assertEqual(choose_player([spotify, browser]), browser)
        self.assertFalse(choose_player([])["available"])

    def test_capabilities_are_respected(self):
        props = {"PlaybackStatus": Variant("s", "Playing"), "CanControl": Variant("b", True),
                 "CanPause": Variant("b", False), "CanPlay": Variant("b", True)}
        self.assertFalse(player_state("player", props)["available"])
        props["PlaybackStatus"] = Variant("s", "Paused")
        self.assertTrue(player_state("player", props)["available"])

    def test_metadata_and_skip_capabilities(self):
        props = {"PlaybackStatus": Variant("s", "Playing"), "CanControl": Variant("b", True),
                 "CanPause": Variant("b", True), "CanGoPrevious": Variant("b", False),
                 "CanGoNext": Variant("b", True), "Metadata": Variant("a{sv}", {
                     "xesam:title": Variant("s", "Mein Song"),
                     "xesam:artist": Variant("as", ["Erster Interpret", "Zweiter Interpret"])})}
        state = player_state("org.mpris.MediaPlayer2.spotify", props)
        self.assertEqual(state["title"], "Mein Song")
        self.assertEqual(state["artist"], "Erster Interpret, Zweiter Interpret")
        self.assertEqual(state["player_name"], "Spotify")
        self.assertEqual(state["playback_status"], "Playing")
        self.assertTrue(state["can_next"])
        self.assertFalse(state["can_previous"])
        props["CanControl"] = Variant("b", False)
        self.assertFalse(player_state("player", props)["can_next"])
        missing = player_state("player", {})
        self.assertEqual((missing["title"], missing["artist"]), ("", ""))

    async def test_skip_uses_selected_player_and_checks_its_capability(self):
        target = "org.mpris.MediaPlayer2.spotify"
        for action, capability, method in (("next", "CanGoNext", "Next"),
                                           ("previous", "CanGoPrevious", "Previous")):
            for allowed in (True, False):
                with self.subTest(action=action, allowed=allowed):
                    bus = Mock()
                    bus.connect = AsyncMock(return_value=bus)
                    props = {"CanControl": Variant("b", True), capability: Variant("b", allowed)}
                    with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
                        call.side_effect = [[[target]], [props], []]
                        if allowed:
                            await media_request(target, action)
                            self.assertEqual(call.call_args.args, (bus, target, "/org/mpris/MediaPlayer2",
                                             "org.mpris.MediaPlayer2.Player", method))
                        else:
                            with self.assertRaises(ValueError):
                                await media_request(target, action)
                            self.assertEqual(call.call_count, 2)
                    bus.disconnect.assert_called_once()

    async def test_unknown_action_rejected_before_connecting(self):
        with patch("media.MessageBus") as bus:
            with self.assertRaises(ValueError):
                await media_request("org.mpris.MediaPlayer2.spotify", "Quit")
            bus.assert_not_called()

    async def test_targets_only_selected_player_and_disconnects(self):
        bus = Mock()
        bus.connect = AsyncMock(return_value=bus)
        target = "org.mpris.MediaPlayer2.spotify"
        props = {"PlaybackStatus": Variant("s", "Playing"), "CanControl": Variant("b", True),
                 "CanPause": Variant("b", True)}
        with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
            call.side_effect = [[[target, "org.mpris.MediaPlayer2.firefox"]], [props], []]
            await media_request(target)
            self.assertEqual(call.call_args.args[1], target)
            self.assertEqual(call.call_args.args[4], "Pause")
        bus.disconnect.assert_called_once()

    async def test_closed_player_does_not_toggle_another(self):
        bus = Mock()
        bus.connect = AsyncMock(return_value=bus)
        with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
            call.return_value = [["org.mpris.MediaPlayer2.firefox"]]
            with self.assertRaises(ValueError):
                await media_request("org.mpris.MediaPlayer2.spotify")
            self.assertEqual(call.call_count, 1)
        bus.disconnect.assert_called_once()
