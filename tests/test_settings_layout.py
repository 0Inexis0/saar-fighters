"""Native Olive Soft layout and controller regression checks."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from main import Home, SettingsDialog, STYLE
from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox


class SoftSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)
        if sys.platform == "win32":
            for name in ("segoeui.ttf", "segoeuib.ttf"):
                QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name))

    def setUp(self):
        self.home = Home(preview=True)
        self.home.resize(1280, 800)
        self.home.show()
        self.dialog = SettingsDialog(self.home)
        self.dialog.show()
        QTest.qWait(50)

    def tearDown(self):
        self.dialog.close()
        self.home.device_client.stop()
        self.home.slideshow.stop()
        self.home.close()
        self.dialog.deleteLater()
        self.home.deleteLater()
        self.app.processEvents()

    def select(self, key):
        self.dialog.select_section(key)
        QTest.qWait(50)
        return self.dialog.page

    def test_all_categories_fit_and_keep_navigation_at_two_sizes(self):
        expected = ["wifi", "bluetooth", "sound", "brightness", "energy", "system",
                    "updates", "remote", "recovery", "logs"]
        self.assertEqual(list(self.dialog.nav_buttons), expected)
        for width, height in ((1040, 760), (768, 516)):
            self.dialog.resize(width, height)
            for key in expected:
                with self.subTest(size=(width, height), category=key):
                    page = self.select(key)
                    self.assertEqual(self.dialog.content.horizontalScrollBar().maximum(), 0)
                    self.assertTrue(page.property("oliveSoft"))
                    self.assertTrue(self.dialog.nav_buttons[key].isChecked())
                    target = ROOT / "build/olive-soft-qa"
                    target.mkdir(parents=True, exist_ok=True)
                    self.assertTrue(self.dialog.grab().save(str(target / f"{key}-{width}.png")))

    def test_audio_selection_and_pending_volume_still_block_navigation(self):
        page = self.select("sound")
        item = page.list.item(1)
        check = page.list.itemWidget(item).findChild(QCheckBox)
        QTest.mouseClick(check, Qt.MouseButton.LeftButton)
        self.assertIn("2", page.checked_ids())
        page.choose.click()
        QTest.qWait(100)
        self.assertIn("2", page.client.preview_audio_ids)
        slider = page.output_sliders[0]
        slider.setValue(37)
        self.assertFalse(self.dialog.nav_buttons["wifi"].isEnabled())
        self.dialog.select_section("wifi")
        self.assertEqual(self.dialog.current_section, "sound")
        QTest.qWait(450)
        self.assertTrue(self.dialog.nav_buttons["wifi"].isEnabled())
        self.assertEqual(page.output_sliders[0].value(), 37)
        self.assertEqual(page.list.count(), 3)

    def test_wifi_password_and_brightness_bindings_survive_grouping(self):
        page = self.select("wifi")
        page.list.setCurrentRow(1)
        self.assertTrue(page.password.isVisible())
        page.password.setText("short")
        page.connect.click()
        self.assertIn("Passwort", page.message.text())
        page.list.setCurrentRow(0)
        self.assertTrue(page.password.isHidden())
        page = self.select("brightness")
        page.slider.setValue(43)
        self.assertFalse(self.dialog.back_button.isEnabled())
        QTest.qWait(450)
        self.assertEqual(page.client.preview_brightness, 43)
        self.assertEqual(page.slider.value(), 43)
        self.assertTrue(self.dialog.back_button.isEnabled())

    def test_cached_update_page_keeps_output_and_preview_is_inert(self):
        page = self.select("updates")
        with patch.object(QProcess, "start") as start:
            page.start.click()
            start.assert_not_called()
        page.output.setPlainText("Prüfausgabe")
        page.output.show()
        self.select("wifi")
        self.assertIs(self.select("updates"), page)
        self.assertEqual(page.output.toPlainText(), "Prüfausgabe")
        self.assertTrue(page.output.isVisible())

    def test_maintenance_busy_state_and_system_readback(self):
        page = self.select("recovery")
        page.working(True)
        self.dialog.reject()
        self.assertTrue(self.dialog.isVisible())
        self.assertFalse(self.dialog.nav_buttons["wifi"].isEnabled())
        page.working(False)
        self.assertTrue(self.dialog.nav_buttons["wifi"].isEnabled())
        page = self.select("system")
        self.assertIn("2.0", page.soft_info["memory"].text())
        self.assertEqual(page.soft_info["architecture"].text(), "x86_64")


if __name__ == "__main__":
    unittest.main()
