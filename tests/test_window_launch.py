"""Run the actual KWin script in Qt's JavaScript engine with window doubles."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import unittest
from PySide6.QtQml import QJSEngine
from PySide6.QtWidgets import QApplication


class WindowLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = QJSEngine()
        self.engine.evaluate("""
            var added;
            function windowDouble(id) {
                return {resourceClass: id, normalWindow: true, maximizable: true,
                    calls: 0, setMaximize: function(v, h) { if (v && h) this.calls++; }};
            }
            var existing = windowDouble('firefox');
            var workspace = {windowAdded: {connect: function(callback) { added = callback; }},
                windowList: function() { return [existing]; }};
        """)
        script = Path(__file__).resolve().parents[1] / "system/maximize-apps.js"
        result = self.engine.evaluate(script.read_text(), str(script))
        self.assertFalse(result.isError(), result.toString())

    def test_existing_and_new_main_windows_maximize(self):
        self.assertEqual(self.engine.evaluate("existing.calls").toInt(), 1)
        for app_id in ('firefox', 'org.mozilla.firefox', 'Spotify', 'com.spotify.Client',
                       'dolphin', 'org.kde.dolphin.desktop'):
            with self.subTest(app_id=app_id):
                result = self.engine.evaluate(
                    f"var w = windowDouble('{app_id}'); added(w); w.calls;")
                self.assertEqual(result.toInt(), 1)

    def test_dialogs_other_apps_and_explicit_fullscreen_are_untouched(self):
        for change in ("w.dialog = true", "w.transient = true", "w.normalWindow = false",
                       "w.maximizable = false", "w.fullScreen = true",
                       "w.resourceClass = 'unrelated-app'"):
            with self.subTest(change=change):
                result = self.engine.evaluate(
                    f"var w = windowDouble('firefox'); {change}; added(w); w.calls;")
                self.assertEqual(result.toInt(), 0)

    def test_wayland_desktop_id_is_supported(self):
        result = self.engine.evaluate("""
            var w = windowDouble(''); w.desktopFileName = 'com.spotify.Client';
            added(w); w.calls;
        """)
        self.assertEqual(result.toInt(), 1)
