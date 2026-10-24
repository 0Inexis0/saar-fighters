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
