"""Music artwork, asynchronous content, expanded controls and lyric following."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtCore import QBuffer, QIODevice, QPoint, Qt, QUrl
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import Home, STYLE
from media_content import ArtworkLoader, LyricsLoader, RemoteContent, lyrics_result, parse_lrc


STATE = {"player": "org.mpris.MediaPlayer2.spotify", "player_name": "Spotify",
         "title": "Testtitel", "artist": "Testinterpret", "album": "Testalbum", "track_id": "/track/1",
         "playing": False, "playback_status": "Paused", "available": True,
         "duration": 180, "position": 22, "volume": 54, "repeat": "None",
         "can_previous": True, "can_next": True, "can_seek": True, "can_volume": True,
         "can_shuffle": True, "can_repeat": True,
         "lyrics": "[00:00]Erste Beispielzeile\n[00:20]Zweite Beispielzeile\n[00:40]Dritte Beispielzeile"}


class LyricsTests(unittest.TestCase):
    def test_lrc_multiple_timestamps_offset_and_plain_text(self):
        self.assertEqual(parse_lrc("[ar:Test]\n[offset:-500]\n[00:02.50][01:03.125]<00:02.00>Ä & <Text>\n[00:00.20]"),
                         [(0, ""), (2, "Ä & <Text>"), (62.625, "Ä & <Text>")])
        self.assertEqual(parse_lrc(None), [])
        self.assertEqual(parse_lrc("[00:99]Ungültig"), [])

    def test_instrumental_missing_and_untimed_lyrics(self):
        self.assertEqual(lyrics_result({"instrumental": True})["status"], "empty")
        self.assertEqual(lyrics_result({})["status"], "empty")
        self.assertEqual(lyrics_result([])["status"], "error")
        result = lyrics_result({"plainLyrics": "<b>Text</b>\n\nZweite Zeile"})
        self.assertFalse(result["synced"])
        self.assertEqual(result["lines"], [(None, "<b>Text</b>"), (None, "Zweite Zeile")])


class MusicUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(1024, 600)
        self.home.show()
        self.home.quick_timer.stop()
        self.home.quick_status("media", dict(STATE), None)
        self.app.processEvents()

    def tearDown(self):
        if self.home.music_dialog:
            self.home.music_dialog.reject()
        self.home.device_client.stop()
        self.home.slideshow.stop()
        self.home.close()
        self.home.deleteLater()
        self.app.processEvents()

    def open(self):
        QTest.mouseClick(self.home.music_tile.expand_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        return self.home.music_dialog

    def test_whole_tile_image_opens_and_escape_returns(self):
        tile = self.home.music_tile
        self.assertEqual(tile.artwork.geometry(), tile.rect())
        self.assertTrue(tile.artwork.fill_tile)
        QTest.mouseClick(tile, Qt.MouseButton.LeftButton, pos=QPoint(tile.width() // 2, 55))
        self.app.processEvents()
        dialog = self.home.music_dialog
        self.assertTrue(dialog.isVisible())
        self.assertTrue(dialog.isFullScreen())
        self.assertEqual(dialog.geometry(), dialog.screen().geometry())
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertIsNone(self.home.music_dialog)
        self.assertTrue(self.home.isVisible())

    def test_collapse_and_reopen_never_changes_playback(self):
        with patch.object(self.home.device_client, "request") as request:
            first = self.open()
            self.home.show_music()
            self.assertIs(self.home.music_dialog, first)
            QTest.mouseClick(first.close_button, Qt.MouseButton.LeftButton)
            second = self.open()
            self.assertIsNot(first, second)
            request.assert_not_called()

    def test_tile_transport_does_not_expand(self):
        self.home.music_tile.buttons["playpause"].click()
        self.assertIsNone(self.home.music_dialog)

    def test_small_player_has_large_controls_even_on_small_screen(self):
        self.home.resize(800, 540)
        self.app.processEvents()
        tile = self.home.music_tile
        self.assertGreaterEqual(tile.expand_button.width(), 44)
        for name, button in tile.buttons.items():
            self.assertGreaterEqual(button.width(), 64 if name == "playpause" else 56)
            self.assertGreaterEqual(button.height(), 56)
            self.assertGreaterEqual(button.iconSize().width(), 32)
            self.assertTrue(tile.rect().contains(button.geometry()))
        self.assertLess(tile.buttons["previous"].geometry().right(), tile.buttons["playpause"].geometry().left())
        self.assertLess(tile.buttons["playpause"].geometry().right(), tile.buttons["next"].geometry().left())

    def test_dialog_fits_laptop_sizes_and_long_metadata(self):
        for width, height in ((800, 540), (1024, 600), (1366, 768)):
            self.home.resize(width, height)
            self.home.quick_status("media", dict(STATE, title="Sehr langer Titel " * 30, artist="Interpret " * 40), None)
            dialog = self.open()
            self.assertTrue(dialog.isFullScreen())
            # Exercise compact layouts independently of the test display's size.
            dialog.showNormal()
            dialog.resize(width, height)
            self.app.processEvents()
            self.assertLessEqual(dialog.width(), width)
            self.assertLessEqual(dialog.height(), height)
            for widget in (*dialog.buttons.values(), dialog.volume, dialog.position, dialog.close_button, dialog.lyrics):
                self.assertTrue(dialog.rect().contains(widget.mapTo(dialog, widget.rect().topLeft())))
                self.assertTrue(dialog.rect().contains(widget.mapTo(dialog, widget.rect().bottomRight())))
            self.assertEqual(dialog.lyrics.horizontalScrollBar().maximum(), 0)
            self.assertEqual(dialog.title.toolTip(), "Sehr langer Titel " * 30)
            dialog.reject()
            self.app.processEvents()

    def test_current_line_follows_position_and_paused_time_stays_put(self):
        dialog = self.open()
        self.assertEqual(dialog.active_line, 1)
        dialog.sample_time -= 10
        dialog.tick()
        self.assertEqual(dialog.current_position(), 22)
        self.home.quick_status("media", dict(STATE, position=42), None)
        self.assertEqual(dialog.active_line, 2)
        dialog.pause_follow()
        self.assertTrue(dialog.follow_button.isVisible())
        dialog.resume_follow()
        self.assertFalse(dialog.follow_button.isVisible())
        self.home.quick_status("media", dict(STATE, playing=True, position=0), None)
        dialog.sample_time -= 21
        dialog.tick()
        self.assertEqual(dialog.active_line, 1)

    def test_buttons_sliders_and_lyric_click_send_displayed_player_actions(self):
        dialog = self.open()
        with patch.object(self.home, "quick_action") as action:
            for name in ("previous", "playpause", "next"):
                dialog.buttons[name].click()
                action.assert_called_with("media", name)
            dialog.buttons["shuffle"].click()
            action.assert_called_with("media", "shuffle", value=True)
            dialog.buttons["repeat"].click()
            action.assert_called_with("media", "repeat", value="Playlist")
            dialog.capture_seek()
            dialog.position.setValue(500)
            dialog.position.commit()
            action.assert_called_with("media", "seek", position=90, track_id="/track/1", player=STATE["player"])
            dialog.capture_volume()
            dialog.volume.setValue(30)
            dialog.volume.commit()
            action.assert_called_with("media", "volume", value=30, player=STATE["player"])
            dialog.seek_line(dialog.lyrics.item(2))
            action.assert_called_with("media", "seek", position=40, track_id="/track/1")

    def test_keyboard_slider_commits_and_pending_seek_drops_on_track_change(self):
        dialog = self.open()
        with patch.object(self.home, "quick_action") as action:
            QTest.keyClick(dialog.volume, Qt.Key.Key_Right)
            QTest.qWait(400)
            action.assert_called_with("media", "volume", value=55, player=STATE["player"])
            action.reset_mock()
            QTest.keyClick(dialog.position, Qt.Key.Key_Right)
            self.home.quick_status("media", dict(STATE, track_id="/track/2", title="Anderer Titel", lyrics=""), None)
            QTest.qWait(400)
            action.assert_not_called()
            self.assertEqual(dialog.lyrics.count(), 0)

    def test_closed_player_disables_controls_clears_art_and_lyrics(self):
        dialog = self.open()
        self.home.quick_status("media", {}, None)
        self.assertTrue(all(not b.isEnabled() for b in dialog.buttons.values()))
        self.assertFalse(dialog.position.isEnabled())
        self.assertFalse(dialog.volume.isEnabled())
        self.assertEqual(dialog.lyrics.count(), 0)
        self.assertTrue(dialog.artwork.image.isNull())

    def test_capabilities_and_request_busy_and_error_visible_in_dialog(self):
        dialog = self.open()
        self.home.quick_status("media", dict(STATE, can_seek=False, can_volume=False,
                                             can_shuffle=False, can_repeat=False), None)
        self.assertFalse(dialog.position.isEnabled())
        self.assertFalse(dialog.volume.isEnabled())
        self.assertFalse(dialog.buttons["shuffle"].isEnabled())
        self.home.preview = False
        try:
            with patch.object(self.home.device_client, "request") as request:
                dialog.buttons["next"].click()
                self.assertTrue(all(not b.isEnabled() for b in dialog.buttons.values()))
                self.assertEqual(request.call_args.args[:2], ("media_next", {"player": STATE["player"]}))
                request.call_args.args[2](None, "Player wurde geschlossen")
                self.assertIn("Player wurde geschlossen", dialog.message.text())
                self.assertTrue(dialog.message.isVisible())
        finally:
            self.home.preview = True

    def test_artwork_file_loading_and_missing_replacement_clears_old_cover(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "cover.png"
            image = QImage(120, 80, QImage.Format.Format_RGB32)
            image.fill(QColor("#d33a71"))
            image.save(str(file))
            state = dict(STATE, art_url=QUrl.fromLocalFile(str(file)).toString())
            self.home.quick_status("media", state, None)
            dialog = self.open()
            self.assertFalse(dialog.artwork.image.isNull())
            self.assertEqual(self.home.music_tile.artwork.image.toImage().pixelColor(0, 0).name(), "#d33a71")
            self.home.quick_status("media", dict(STATE, art_url="file:///missing-cover.png"), None)
            self.assertTrue(self.home.music_tile.artwork.image.isNull())
            self.assertTrue(dialog.artwork.image.isNull())

    def test_lyrics_api_encodes_metadata_caches_and_offers_retry(self):
        loader = LyricsLoader()
        results = []
        loader.changed.connect(results.append)
        with patch.object(loader, "fetch") as fetch:
            state = dict(STATE, title="A & B?", lyrics="")
            loader.load(state)
            self.assertIn("track_name=A%20%26%20B?", fetch.call_args.args[0].toEncoded().data().decode())
            loader.received(json.dumps({"syncedLyrics": "[00:01]Testzeile"}).encode(), 200)
            loader.load(dict(state, title="B"))
            fetch.reset_mock()
            loader.load(state)
            fetch.assert_not_called()
            self.assertEqual(results[-1]["lines"], [(1, "Testzeile")])
            loader.load(state, force=True)
            fetch.assert_called_once()
            loader.received(b"", None)
            self.assertEqual(results[-1]["status"], "error")
        loader.deleteLater()


class RemoteContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/slow":
                    time.sleep(.2)
                self.send_response(200)
                self.end_headers()
                try:
                    self.wfile.write(b"x" * 4096 if self.path == "/large" else self.path.encode())
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def wait_for(self, values):
        for _ in range(60):
            if values:
                return
            QTest.qWait(20)
        self.fail("The local content request never finished")

    def test_replacement_discards_late_reply(self):
        loader = RemoteContent()
        old, new = [], []
        loader.fetch(self.url + "/slow", lambda data, status: old.append(data))
        QTest.qWait(30)
        loader.fetch(self.url + "/new", lambda data, status: new.append(data))
        self.wait_for(new)
        QTest.qWait(250)
        self.assertEqual(old, [])
        self.assertEqual(new, [b"/new"])
        loader.deleteLater()

    def test_oversized_download_is_rejected(self):
        loader = RemoteContent(limit=128)
        values = []
        loader.fetch(self.url + "/large", lambda data, status: values.append(data))
        self.wait_for(values)
        self.assertEqual(values, [b""])
        loader.deleteLater()


if __name__ == "__main__":
    unittest.main()
