"""Status toolbar and notification routing integration checks."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from main import Home, SettingsDialog, NotificationsDialog, STYLE
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
        for button, section in zip(self.home.status_values,
                                   ("wifi", "bluetooth", "energy", "energy")):
            seen = []
            def inspect_dialog():
                dialog = self.app.activeModalWidget()
                seen.append(dialog.current_section)
                dialog.reject()
            QTimer.singleShot(250, inspect_dialog)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            self.assertEqual(seen, [section])

    def test_bell_opens_separate_window_and_preserves_apps_view(self):
        self.home.show_apps()
        seen = []
        def inspect_dialog():
            dialog = self.app.activeModalWidget()
            seen.append(type(dialog))
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QTimer.singleShot(250, inspect_dialog)
        QTest.mouseClick(self.home.notification_button, Qt.MouseButton.LeftButton)
        self.assertEqual(seen, [NotificationsDialog])
        self.assertTrue(self.home.apps_page.isVisible())

    def test_notification_window_live_updates_read_clear_and_small_screen(self):
        dialog = NotificationsDialog(self.home)
        dialog.show()
        try:
            self.app.processEvents()
            self.assertFalse(dialog.clear_button.isEnabled())
            self.home.notifications.add("Akku niedrig", "Bitte das Netzteil anschließen. " * 15)
            self.home.notifications.add("Systemupdate", "Das System ist aktuell.")
            self.app.processEvents()
            self.assertEqual(len(dialog.cards), 2)
            self.assertEqual(dialog.summary.text(), "2 ungelesen")
            self.assertEqual(dialog.scroll.horizontalScrollBar().maximum(), 0)
            self.assertLessEqual(dialog.height(), self.home.height())
            for button in (dialog.read_button, dialog.clear_button, dialog.close_button):
                self.assertTrue(dialog.rect().contains(button.geometry()))
            QTest.mouseClick(dialog.read_button, Qt.MouseButton.LeftButton)
            self.assertFalse(self.home.notification_badge.isVisible())
            self.assertEqual(dialog.summary.text(), "Alles gelesen")
            self.assertFalse(dialog.read_button.isEnabled())
            self.assertTrue(all(not card.property("unread") for card in dialog.cards))
            QTest.mouseClick(dialog.clear_button, Qt.MouseButton.LeftButton)
            self.assertEqual(len(dialog.cards), 0)
            self.assertFalse(dialog.clear_button.isEnabled())
            QTest.mouseClick(dialog.close_button, Qt.MouseButton.LeftButton)
            self.assertFalse(dialog.isVisible())
        finally:
            dialog.close()
            dialog.deleteLater()

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
