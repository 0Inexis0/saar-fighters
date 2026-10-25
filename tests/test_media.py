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

    def extended_props(self):
        return {"CanControl": Variant("b", True), "CanSeek": Variant("b", True),
                "Volume": Variant("d", .65), "Shuffle": Variant("b", False),
                "LoopStatus": Variant("s", "None"), "Position": Variant("x", 12_500_000),
                "Metadata": Variant("a{sv}", {"mpris:trackid": Variant("o", "/track/one"),
                    "mpris:length": Variant("x", 180_000_000), "mpris:artUrl": Variant("s", "https://example.org/cover.png"),
                    "xesam:album": Variant("s", "Album"), "xesam:asText": Variant("s", "Songtext")})}

    def test_artwork_timing_and_optional_capabilities(self):
        state = player_state("org.mpris.MediaPlayer2.spotify", self.extended_props())
        self.assertEqual((state["duration"], state["position"], state["volume"]), (180, 12.5, 65))
        self.assertEqual((state["album"], state["lyrics"], state["art_url"]),
                         ("Album", "Songtext", "https://example.org/cover.png"))
        self.assertTrue(all(state[key] for key in ("can_seek", "can_volume", "can_shuffle", "can_repeat")))
        missing = player_state("player", {"CanControl": Variant("b", True)})
        self.assertIsNone(missing["position"])
        self.assertFalse(any(missing[key] for key in ("can_seek", "can_volume", "can_shuffle", "can_repeat")))

    async def test_absolute_seek_uses_track_id_and_microseconds(self):
        target = "org.mpris.MediaPlayer2.spotify"
        bus = Mock()
        bus.connect = AsyncMock(return_value=bus)
        with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
            call.side_effect = [[[target]], [self.extended_props()], []]
            await media_request(target, "seek", position=42.25, track_id="/track/one")
            self.assertEqual(call.call_args.args[-3:], ("SetPosition", "ox", ["/track/one", 42_250_000]))
        bus.disconnect.assert_called_once()

    async def test_stale_seek_and_invalid_values_never_mutate_player(self):
        target = "org.mpris.MediaPlayer2.spotify"
        cases = [("seek", {"position": 40, "track_id": "/track/old"}),
                 ("seek", {"position": 181, "track_id": "/track/one"}),
                 ("seek", {"position": float("nan"), "track_id": "/track/one"}),
                 ("volume", {"value": -1}), ("volume", {"value": 101}),
                 ("volume", {"value": True}), ("volume", {"value": float("inf")}),
                 ("shuffle", {"value": "true"}), ("repeat", {"value": "anything"})]
        for action, args in cases:
            with self.subTest(action=action, args=args):
                bus = Mock()
                bus.connect = AsyncMock(return_value=bus)
                with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
                    call.side_effect = [[[target]], [self.extended_props()]]
                    with self.assertRaises(ValueError):
                        await media_request(target, action, **args)
                    self.assertEqual(call.call_count, 2)
                bus.disconnect.assert_called_once()

    async def test_volume_shuffle_repeat_write_correct_typed_properties(self):
        target = "org.mpris.MediaPlayer2.firefox"
        for action, value, prop, signature, result in (("volume", 40, "Volume", "d", .4),
                   ("shuffle", True, "Shuffle", "b", True), ("repeat", "Track", "LoopStatus", "s", "Track")):
            with self.subTest(action=action):
                bus = Mock()
                bus.connect = AsyncMock(return_value=bus)
                with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
                    call.side_effect = [[[target]], [self.extended_props()], []]
                    await media_request(target, action, value=value)
                    self.assertEqual(call.call_args.args[1:6], (target, "/org/mpris/MediaPlayer2",
                                     "org.freedesktop.DBus.Properties", "Set", "ssv"))
                    body = call.call_args.args[-1]
                    self.assertEqual(body[:2], ["org.mpris.MediaPlayer2.Player", prop])
                    self.assertEqual((body[2].signature, body[2].value), (signature, result))

    async def test_optional_controls_require_player_support(self):
        target = "org.mpris.MediaPlayer2.firefox"
        for action in ("seek", "volume", "shuffle", "repeat"):
            with self.subTest(action=action):
                bus = Mock()
                bus.connect = AsyncMock(return_value=bus)
                with patch("media.MessageBus", return_value=bus), patch("media.call", new_callable=AsyncMock) as call:
                    call.side_effect = [[[target]], [{"CanControl": Variant("b", True)}]]
                    with self.assertRaises(ValueError):
                        await media_request(target, action, value=50)
                    self.assertEqual(call.call_count, 2)
