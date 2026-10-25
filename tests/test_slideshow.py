import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtWidgets import QApplication, QWidget, QDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from slideshow import IdleSlideshow, Slideshow
from idle_watch import TIMEOUT_MS

FOLDER = Path(__file__).resolve().parents[1] / "app/assets/slideshow"


class SlideshowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.home = QWidget()
        self.controller = IdleSlideshow(self.home, FOLDER, preview=True)

    def tearDown(self):
        self.controller.stop()
        self.home.deleteLater()
        self.app.processEvents()

    def test_idle_then_resume_and_disconnect(self):
        self.assertEqual(TIMEOUT_MS, 300_000)
        self.controller.handle_event("ready")
        self.assertFalse(self.controller.view.isVisible())
        self.controller.handle_event("idled")
        self.assertTrue(self.controller.view.isVisible())
        self.assertTrue(self.controller.view.timer.isActive())
        self.controller.handle_event("resumed")
        self.assertFalse(self.controller.view.isVisible())
        self.assertFalse(self.controller.view.timer.isActive())
        self.controller.handle_event("idled")
        self.controller.lost()
        self.assertFalse(self.controller.view.isVisible())

    def test_shuffle_contains_all_three_and_never_repeats_adjacent(self):
        view = self.controller.view
        self.assertEqual(len(view.slides), 3)
        result = []
        for _ in range(12):
            self.assertTrue(view.next_slide())
            self.assertFalse(view.picture.isNull())
            result.append(view.current)
        self.assertTrue(all(a != b for a, b in zip(result, result[1:])))
        for i in range(0, 12, 3):
            self.assertEqual(set(result[i:i + 3]), {0, 1, 2})

    def test_keyboard_dismisses_and_does_not_close_home(self):
        self.home.show()
        self.controller.handle_event("idled")
        QTest.keyClick(self.controller.view, Qt.Key.Key_Escape)
        self.assertFalse(self.controller.view.isVisible())
        self.assertTrue(self.home.isVisible())

    def test_modal_dialog_is_not_covered(self):
        dialog = QDialog(self.home)
        dialog.setModal(True)
        dialog.show()
        self.app.processEvents()
        self.controller.handle_event("idled")
        self.assertFalse(self.controller.view.isVisible())
        dialog.close()

    def test_broken_images_fail_closed(self):
        view = self.controller.view
        view.slides = [{"file": "missing.jpg", "credit": ""}]
        view.start()
        self.assertFalse(view.isVisible())

    def test_running_rocket_round_is_not_covered(self):
        with patch("slideshow.game_active", return_value=True):
            self.controller.handle_event("idled")
            self.assertFalse(self.controller.view.isVisible())
        with patch("slideshow.game_active", return_value=False):
            self.controller.handle_event("idled")
            self.assertTrue(self.controller.view.isVisible())
