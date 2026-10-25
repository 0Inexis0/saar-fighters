"""Application discovery and real Qt interactions for the paginated library."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from applications import Application, SHORTCUTS, application_catalog, application_directories, discover_applications
from main import AppsDialog, Home, STYLE
from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.user = self.root / "user"
        self.system = self.root / "system"

    def entry(self, directory, name, fields):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[Desktop Entry]\nType=Application\nName=Default\nExec=example %U\n" + fields,
                        encoding="utf-8")
        return path

    def test_german_names_flatpak_icons_and_nested_desktop_ids(self):
        path = self.entry(self.system, "tools/editor.desktop",
                          "Name[de]=Editor\nName[de_DE]=Texteditor\nGenericName[de]=Text bearbeiten\n"
                          "Icon=org.example.Editor\nExec=/usr/bin/flatpak run org.example.Editor %U\n")
        apps = discover_applications([self.system])
        self.assertEqual(len(apps), 1)
        self.assertEqual((apps[0].id, apps[0].title, apps[0].description),
                         ("tools-editor.desktop", "Texteditor", "Text bearbeiten"))
        self.assertEqual(apps[0].desktop_file, path)
        self.assertEqual(apps[0].icon, "org.example.Editor")

    def test_user_overrides_and_hidden_entries_mask_system_copies(self):
        self.entry(self.system, "edit.desktop", "Name=System Editor\n")
        self.entry(self.user, "edit.desktop", "Name=Personal Editor\n")
        self.entry(self.system, "hidden.desktop", "Name=Hidden System App\n")
        self.entry(self.user, "hidden.desktop", "Hidden=true\n")
        apps = discover_applications([self.user, self.system, self.system])
        self.assertEqual([app.title for app in apps], ["Personal Editor"])

    def test_filters_internal_wrong_desktop_missing_and_malformed_entries(self):
        for name, fields in {
            "hidden": "Hidden=true", "internal": "NoDisplay=true",
            "gnome": "OnlyShowIn=GNOME;", "excluded": "NotShowIn=KDE;",
            "missing": "TryExec=saar-test-command-that-does-not-exist",
            "link": "Type=Link", "unnamed": "Name=", "empty": "Exec=",
        }.items():
            self.entry(self.system, name + ".desktop", fields + "\n")
        self.entry(self.system, "de.saarfighters.Home.desktop", "")
        self.entry(self.system, "kde.desktop", "OnlyShowIn=KDE;\nName=KDE App\n")
        self.entry(self.system, "dbus.desktop", "Exec=\nDBusActivatable=true\nName=DBus App\n")
        (self.system / "broken.desktop").write_text("not an ini file", encoding="utf-8")
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}):
            apps = discover_applications([self.system])
        self.assertEqual({app.title for app in apps}, {"KDE App", "DBus App"})

    def test_shortcuts_remain_and_installed_apps_are_not_duplicated(self):
        spotify = self.entry(self.system, "spotify.desktop", "Name=Spotify\n")
        self.entry(self.system, "firefox.desktop", "Name=Firefox\n")
        self.entry(self.system, "org.kde.dolphin.desktop", "Name=Dolphin\n")
        self.entry(self.system, "vlc.desktop", "Name=VLC\n")
        apps = application_catalog([self.system])
        self.assertEqual(len(apps), len(SHORTCUTS) + 1)
        self.assertTrue({app.id for app in SHORTCUTS}.issubset({app.id for app in apps}))
        installed = next(app for app in apps if app.id == "spotify")
        self.assertEqual(installed.desktop_file, spotify)
        self.assertFalse(installed.action)
        self.assertEqual([app.title for app in apps], sorted((app.title for app in apps), key=str.casefold))

    def test_directories_include_user_system_and_both_flatpak_exports(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.user),
                                    "XDG_DATA_DIRS": os.pathsep.join([str(self.system)] * 2)}):
            directories = application_directories()
        self.assertEqual(directories[:2], [self.user / "applications", self.system / "applications"])
        self.assertEqual(len(directories), len(set(directories)))
        self.assertIn(Path.home() / ".local/share/flatpak/exports/share/applications", directories)
        if os.name != "nt":
            self.assertIn(Path("/var/lib/flatpak/exports/share/applications"), directories)


class AppsDialogTests(unittest.TestCase):
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
        self.dialog = AppsDialog(self.home)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
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
        self.assertEqual(self.dialog.page_label.text(), "Seite 3 von 3")
        QTest.mouseClick(self.dialog.previous_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.dialog.page, 1)

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
        self.assertEqual(len(self.dialog.tiles), 8)
        self.assertFalse(self.dialog.empty_label.isVisible())

    def test_refresh_finds_newly_installed_app_and_preserves_search(self):
        self.dialog.search.setText("Neu installiert")
        self.catalog.return_value = [*self.entries, Application("new.desktop", "Neu installiert")]
        QTest.mouseClick(self.dialog.refresh_button, Qt.MouseButton.LeftButton)
        self.assertEqual(list(self.dialog.tiles), ["new.desktop"])
        self.assertEqual(self.dialog.search.text(), "Neu installiert")

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

    def test_native_launch_passes_desktop_uri_to_kde_and_returns_home(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "App with spaces.desktop"
            path.write_text("[Desktop Entry]\nType=Application\nName=Example\nExec=example %U\n", encoding="utf-8")
            self.catalog.return_value = [Application("native", "Native App", desktop_file=path)]
            self.dialog.reload_apps()
            self.home.preview = False
            with patch("main.shutil.which", return_value="kioclient"), patch.object(QProcess, "start") as start:
                QTest.mouseClick(self.dialog.tiles["native"], Qt.MouseButton.LeftButton)
                start.assert_called_once_with("kioclient", ["exec", path.as_uri()])
                self.assertFalse(self.dialog.isVisible())

    def test_removed_app_and_missing_launcher_keep_error_visible(self):
        self.home.preview = False
        self.dialog.open_app(Application("removed", "Removed", desktop_file=Path("missing.desktop")))
        self.assertIn("nicht mehr vorhanden", self.dialog.feedback.text())
        self.assertTrue(self.dialog.isVisible())
        with patch("main.shutil.which", return_value=None):
            self.dialog.open_app(SHORTCUTS[0])
        self.assertIn("fehlt", self.dialog.feedback.text())
        self.assertTrue(self.dialog.isVisible())

    def test_layout_fits_small_screens_and_long_app_names(self):
        self.catalog.return_value = [Application(f"long-{i}", "Sehr langer Anwendungsname " * 8,
                                               "Lange Beschreibung " * 12) for i in range(23)]
        self.dialog.reload_apps()
        for width, height in ((800, 540), (1024, 600), (1366, 768), (800, 540)):
            self.home.resize(width, height)
            self.dialog.resize(min(width - 32, 1200), min(height - 24, 720))
            self.app.processEvents()
            self.assertLessEqual(self.dialog.width(), width)
            self.assertLessEqual(self.dialog.height(), height)
            for tile in self.dialog.tiles.values():
                self.assertTrue(self.dialog.rect().contains(tile.geometry()))
                self.assertGreaterEqual(tile.width(), 140)
                for child in tile.findChildren(type(self.dialog.count_label)):
                    self.assertTrue(tile.rect().contains(child.geometry()))
            for button in (self.dialog.back_button, self.dialog.previous_button, self.dialog.next_button):
                self.assertTrue(self.dialog.rect().contains(button.geometry()))

    def test_home_tile_opens_the_dialog_and_back_returns_to_home(self):
        self.dialog.close()
        observations = []
        def close_apps():
            modal = QApplication.activeModalWidget()
            observations.append(isinstance(modal, AppsDialog))
            if isinstance(modal, AppsDialog):
                QTest.mouseClick(modal.back_button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(20, close_apps)
        QTest.mouseClick(self.home.tiles["apps"], Qt.MouseButton.LeftButton)
        self.assertEqual(observations, [True])
        self.assertTrue(self.home.isVisible())


if __name__ == "__main__":
    unittest.main()
