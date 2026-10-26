"""Dashboard navigation and the fixed club app selection."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from applications import Application, SHORTCUTS, application_catalog
from main import Home, STYLE
from PySide6.QtCore import QProcess, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class CatalogTests(unittest.TestCase):
    def test_only_the_six_original_apps_are_included(self):
        with patch.dict(os.environ, {"XDG_DATA_DIRS": "/usr/share:/var/lib/flatpak/exports/share"}):
            apps = application_catalog()
        self.assertEqual([app.id for app in apps],
                         ["rocket", "spotify", "web", "youtube", "files", "club"])
        self.assertEqual(apps, list(SHORTCUTS))


class AppsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.entries = [Application(f"app-{i}.desktop", f"Anwendung {i:02}", "Installierte Anwendung")
                        for i in range(23)]
        self.catalog = patch("main.application_catalog", return_value=self.entries).start()
        self.addCleanup(patch.stopall)
        self.home = Home(preview=True)
        self.home.resize(1024, 600)
        self.home.show()
        self.home.show_apps()
        self.dialog = self.home.apps_page
        self.app.processEvents()

    def tearDown(self):
        self.home.preview = True
        self.home.close()
        self.home.deleteLater()
        self.app.processEvents()

    def test_every_app_is_reachable_once_across_multiple_pages(self):
        reached = []
        self.assertFalse(self.dialog.previous_button.isEnabled())
        while True:
            reached.extend(self.dialog.tiles)
            if not self.dialog.next_button.isEnabled():
                break
            QTest.mouseClick(self.dialog.next_button, Qt.MouseButton.LeftButton)
            self.app.processEvents()
        self.assertEqual(reached, [app.id for app in self.entries])
        self.assertEqual(self.dialog.page_label.text(), "Seite 4 von 4")
        QTest.mouseClick(self.dialog.previous_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.dialog.page, 2)

    def test_search_spans_all_pages_and_recovers_from_no_results(self):
        self.dialog.change_page(2)
        QTest.keyClicks(self.dialog.search, "Anwendung 22")
        self.assertEqual(list(self.dialog.tiles), ["app-22.desktop"])
        self.assertEqual(self.dialog.page, 0)
        self.assertFalse(self.dialog.next_button.isEnabled())
        self.dialog.search.setText("Nicht vorhandene App")
        self.assertFalse(self.dialog.tiles)
        self.assertTrue(self.dialog.empty_label.isVisible())
        self.assertEqual(self.dialog.page_label.text(), "Keine Treffer")
        self.dialog.search.clear()
        self.app.processEvents()
        self.assertEqual(len(self.dialog.tiles), 6)
        self.assertFalse(self.dialog.empty_label.isVisible())

    def test_all_shortcuts_work_in_preview_without_starting_any_process(self):
        self.catalog.return_value = list(SHORTCUTS)
        self.dialog.reload_apps()
        self.app.processEvents()
        with patch.object(QProcess, "start") as start:
            for entry in SHORTCUTS:
                QTest.mouseClick(self.dialog.tiles[entry.id], Qt.MouseButton.LeftButton)
                self.assertEqual(self.home.last_action, entry.action)
                self.assertIn(entry.title, self.dialog.feedback.text())
                self.assertTrue(self.dialog.isVisible())
            start.assert_not_called()

    def test_app_launch_returns_to_dashboard_and_failure_stays_on_apps(self):
        self.home.preview = False
        with patch("main.shutil.which", return_value="firefox"), patch.object(QProcess, "start") as start:
            self.dialog.open_app(SHORTCUTS[2])
            start.assert_called_once_with("firefox", ["--new-window", "https://start.duckduckgo.com"])
            self.assertIs(self.home.pages.currentWidget(), self.home.dashboard)
        self.home.show_apps()
        with patch("main.shutil.which", return_value=None):
            self.dialog.open_app(SHORTCUTS[0])
        self.assertIn("fehlt", self.dialog.feedback.text())
        self.assertIs(self.home.pages.currentWidget(), self.dialog)

    def test_layout_fits_small_screens_and_long_app_names(self):
        self.catalog.return_value = [Application(f"long-{i}", "Sehr langer Anwendungsname " * 8,
                                               "Lange Beschreibung " * 12) for i in range(23)]
        self.dialog.reload_apps()
        for width, height in ((800, 540), (1024, 600), (1366, 768), (800, 540)):
            self.home.resize(width, height)
            self.app.processEvents()
            self.assertEqual(self.dialog.geometry(), self.home.page_area.rect())
            self.assertTrue(self.home.status_header.isVisible())
            self.assertTrue(all(value.isVisible() for value in self.home.status_values))
            self.assertGreater(self.home.page_area.geometry().top(), self.home.status_header.geometry().bottom())
            self.assertFalse(self.dialog.isWindow())
            for tile in self.dialog.tiles.values():
                self.assertTrue(self.dialog.rect().contains(tile.geometry()))
                self.assertGreaterEqual(tile.width(), 140)
                for child in tile.findChildren(type(self.dialog.count_label)):
                    self.assertTrue(tile.rect().contains(child.geometry()))
            for button in (self.dialog.back_button, self.dialog.previous_button, self.dialog.next_button):
                self.assertTrue(self.dialog.rect().contains(button.geometry()))

    def test_apps_replace_dashboard_content_and_keep_status_without_another_window(self):
        self.home.show_dashboard()
        windows = set(QApplication.topLevelWidgets())
        QTest.mouseClick(self.home.tiles["apps"], Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertIs(self.home.pages.currentWidget(), self.dialog)
        self.assertEqual(self.dialog.geometry(), self.home.page_area.rect())
        self.assertTrue(self.home.status_header.isVisible())
        self.assertTrue(all(value.isVisible() for value in self.home.status_values))
        self.assertFalse(self.home.dashboard.isVisible())
        self.assertIsNone(QApplication.activeModalWidget())
        self.assertEqual(set(QApplication.topLevelWidgets()), windows)
        QTest.mouseClick(self.dialog.back_button, Qt.MouseButton.LeftButton)
        self.assertTrue(self.home.dashboard.isVisible())
        self.assertFalse(self.dialog.isVisible())
        self.home.show_apps()
        QTest.keyClick(self.dialog.search, Qt.Key.Key_Escape)
        self.assertTrue(self.home.dashboard.isVisible())

    def test_six_apps_fit_one_page_without_unneeded_page_controls(self):
        self.catalog.return_value = application_catalog()
        self.dialog.reload_apps()
        self.app.processEvents()
        self.assertEqual(len(self.dialog.tiles), 6)
        self.assertFalse(self.dialog.navigation.isVisible())


if __name__ == "__main__":
    unittest.main()
