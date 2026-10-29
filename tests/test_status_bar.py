"""Status toolbar and notification routing integration checks."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from main import Home, SettingsDialog, STYLE
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class StatusBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if sys.platform == "win32":
            for name in ("segoeui.ttf", "segoeuib.ttf"):
                QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(800, 540)
        self.home.show()
        self.app.processEvents()

    def tearDown(self):
        self.home.close()
        self.home.deleteLater()
        self.app.processEvents()

    def test_feedback_routes_to_bell_and_read_clear_updates_badge(self):
        self.home.set_feedback("Eine Anwendung fehlt.")
        self.assertFalse(self.home.feedback.isVisible())
        self.assertEqual(self.home.notifications.items[-1]["body"], "Eine Anwendung fehlt.")
        self.assertEqual(self.home.notification_badge.text(), "1")
        self.assertTrue(self.home.notification_badge.isVisible())
        self.home.set_feedback("")
        self.assertEqual(self.home.notifications.unread, 1)
        self.home.notifications.mark_read()
        self.assertFalse(self.home.notification_badge.isVisible())
        self.home.notifications.add("Test", "Neu")
        self.home.notifications.clear()
        self.assertFalse(self.home.notification_badge.isVisible())

    def test_toolbar_fits_and_controls_open_matching_sections(self):
        for size in ((800, 540), (1366, 768)):
            self.home.resize(*size)
            self.app.processEvents()
            for button in (*self.home.status_values, self.home.notification_button):
                self.assertTrue(self.home.status_header.rect().contains(button.geometry()))
                self.assertEqual(button.text(), "")
                self.assertFalse(button.icon().isNull())
        for button, section in zip((*self.home.status_values, self.home.notification_button),
                                   ("wifi", "bluetooth", "energy", "energy", "notifications")):
            seen = []
            def inspect_dialog():
                dialog = self.app.activeModalWidget()
                seen.append(dialog.current_section)
                dialog.reject()
            QTimer.singleShot(250, inspect_dialog)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            self.assertEqual(seen, [section])

    def test_device_details_remain_available_without_text_boxes(self):
        self.home.update_status({"network": {"state": 70, "connectivity": 4, "name": "Vereinsnetz"},
                                 "bluetooth": {"available": True, "powered": False},
                                 "power": {"percentage": 12, "plugged": False}})
        self.assertIn("Vereinsnetz", self.home.network.toolTip())
        self.assertIn("Bluetooth aus", self.home.status_values[1].toolTip())
        self.assertEqual(self.home.battery_percentage.text(), "12 %")
        self.assertEqual(self.home.notifications.unread, 1)
        self.home.update_status({"power": {"error": "Unavailable"}})
        self.assertEqual(self.home.battery_percentage.text(), "")
