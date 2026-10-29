import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.append(str(ROOT / "system"))
from configure_display import configure
from energy_profile import apply
from notifications import NotificationCenter
from system_status import snapshot
from system_settings import EnergySheet, open_module
from main import Home, SettingsDialog, STYLE
from PySide6.QtCore import QProcess, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase


class ProfileTests(unittest.TestCase):
    def test_laptop_survives_login_and_preserves_lid_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "powerdevilrc"
            path.write_text("[Battery][SuspendAndShutdown]\nLidAction=2\n", encoding="utf-8")
            lock = Path(folder) / "kscreenlockerrc"
            lock.write_text("[Daemon]\nAutolock=true\n")
            apply("laptop", folder)
            self.assertEqual(lock.read_text(), "[Daemon]\nAutolock=true\n")
            result = path.read_text()
            self.assertIn("AutoSuspendIdleTimeoutSec=900", result)
            self.assertIn("TurnOffDisplayIdleTimeoutSec=300", result)
            self.assertIn("LidAction=2", result)
            self.assertFalse(configure(folder))
            self.assertEqual(result, path.read_text())
            apply("club", folder)
            self.assertIn("TurnOffDisplayWhenIdle=false", path.read_text())

    def test_custom_profile_preserves_manual_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "powerdevilrc"
            path.write_text("[AC][Display]\nTurnOffDisplayIdleTimeoutSec=777\n")
            apply("custom", folder)
            self.assertFalse(configure(folder))
            self.assertIn("777", path.read_text())
            with self.assertRaises(ValueError):
                apply("invalid", folder)


class NotificationTests(unittest.TestCase):
    def test_edge_trigger_history_read_state_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.json"
            center = NotificationCenter(path=path)
            status = {"power": {"percentage": 10, "plugged": False}}
            center.devices(status)
            center.devices(status)
            self.assertEqual(center.unread, 1)
            center.mark_read()
            self.assertEqual(NotificationCenter(path=path).unread, 0)
            center.devices({"power": {"percentage": 30, "plugged": True}})
            center.devices(status)
            self.assertEqual(len(center.items), 2)
            center.clear()
            center.devices(status)
            self.assertEqual(center.items, [])

    def test_preview_and_history_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.json"
            center = NotificationCenter(preview=True, path=path)
            for i in range(105):
                center.add("Test", str(i))
            self.assertEqual(len(center.items), 100)
            self.assertFalse(path.exists())

    def test_system_facts_handle_missing_memory_and_read_real_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIsNone(snapshot(root)["memory_used"])
            (root / "proc").mkdir()
            (root / "proc/meminfo").write_text("MemTotal: 4000 kB\nMemAvailable: 1500 kB\n")
            self.assertEqual(snapshot(root)["memory_used"], 2500 * 1024)


class SettingsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if sys.platform == "win32":
            for name in ("segoeui.ttf", "segoeuib.ttf"):
                QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name))
        cls.app.setStyleSheet(STYLE)

    def test_visible_choices_keyboard_backend_mapping_and_busy_state(self):
        home = Home(preview=True)
        home.resize(800, 540)
        dialog = SettingsDialog(home)
        dialog.show()
        QTest.qWait(100)
        try:
            dialog.select_section("energy")
            page = dialog.page
            choice = page.profile
            choice.group.button(0).setFocus()
            QTest.keyClick(choice.group.button(0), Qt.Key.Key_Down)
            self.assertEqual(choice.currentData(), "balanced")
            self.assertEqual(page.message.text(), "")
            self.assertTrue(page.message.isHidden())
            self.assertEqual(sum(b.isChecked() for b in choice.group.buttons()), 1)
            page.client.preview = False
            with patch.object(page.process, "start") as start:
                page.apply()
                self.assertEqual(start.call_args.args, ("powerprofilesctl", ["set", "balanced"]))
                self.assertFalse(choice.isEnabled())
                self.assertFalse(dialog.back_button.isEnabled())
            page.timeout.stop()
            page.working(False)
            page.client.preview = True
            dialog.select_section("logs")
            page = dialog.page
            for index in range(3):
                QTest.mouseClick(page.source.group.button(index), Qt.MouseButton.LeftButton)
                self.assertEqual(page.source.currentIndex(), index)
                self.assertIn("Beispieldaten", page.output.toPlainText())
            page.source.setCurrentIndex(1)
            page.client.preview = False
            with patch.object(page.process, "start") as start:
                page.load()
                self.assertIn("--user", start.call_args.args[1])
            page.timeout.stop()
            page.working(False)
            page.client.preview = True
        finally:
            home.device_client.preview = True
            dialog.close()
            home.close()
            dialog.deleteLater()
            home.deleteLater()

    def test_pages_fit_and_preview_never_changes_host(self):
        home = Home(preview=True)
        home.resize(800, 540)
        home.show()
        dialog = SettingsDialog(home)
        dialog.show()
        QTest.qWait(100)
        try:
            self.assertNotIn("notifications", dialog.nav_buttons)
            for section in ("brightness", "energy", "system"):
                dialog.select_section(section)
                QTest.qWait(100)
                self.assertEqual(dialog.current_section, section)
                self.assertEqual(dialog.content.horizontalScrollBar().maximum(), 0, section)
                with patch.object(QProcess, "start") as start, patch.object(QProcess, "startDetached") as detached:
                    if section == "energy":
                        dialog.page.apply()
                        open_module(dialog.page, "energy")
                    if section == "brightness":
                        open_module(dialog.page, "display")
                    start.assert_not_called()
                    detached.assert_not_called()
                target = ROOT / "build/system-settings-qa"
                target.mkdir(parents=True, exist_ok=True)
                dialog.grab().save(str(target / (section + ".png")))
        finally:
            dialog.close()
            home.close()
            dialog.deleteLater()
            home.deleteLater()

    def test_all_settings_hide_idle_notices_but_show_errors(self):
        home = Home(preview=True)
        home.resize(800, 540)
        dialog = SettingsDialog(home)
        dialog.show()
        QTest.qWait(100)
        try:
            for section in dialog.nav_buttons:
                dialog.select_section(section)
                QTest.qWait(50)
                notice = getattr(dialog.page, "message", getattr(dialog.page, "state", None))
                self.assertTrue(notice.isHidden(), section)
                notice.setText("Verbindung fehlgeschlagen.")
                self.assertFalse(notice.isHidden(), section)
                notice.clear()
                self.assertTrue(notice.isHidden(), section)
                self.assertEqual(dialog.content.horizontalScrollBar().maximum(), 0, section)
        finally:
            dialog.close()
            home.slideshow.stop()
            home.close()
            dialog.deleteLater()
            home.deleteLater()

    def test_linux_profiles_availability_readback_and_failures(self):
        home = Home(preview=True)
        dialog = SettingsDialog(home, section="energy")
        page = dialog.page
        try:
            page.client.preview = False
            page.phase = "list"
            with patch.object(page.process, "readAllStandardOutput", return_value=b"  power-saver:\n* balanced:\n"), patch.object(page.process, "readAllStandardError", return_value=b""), patch.object(page.process, "start") as start:
                page.completed(0, QProcess.ExitStatus.NormalExit)
                self.assertEqual(start.call_args.args, ("powerprofilesctl", ["get"]))
            page.timeout.stop()
            page.show_active("balanced")
            self.assertFalse(page.profile.group.button(2).isEnabled())
            self.assertEqual(page.profile.currentData(), "balanced")
            with patch.object(page.process, "start") as start:
                page.profile.setCurrentIndex(0)
                self.assertEqual(start.call_args.args, ("powerprofilesctl", ["set", "power-saver"]))
            page.timeout.stop()
            with patch.object(page.process, "readAllStandardOutput", return_value=b""), patch.object(page.process, "readAllStandardError", return_value=b"Permission denied"):
                page.completed(1, QProcess.ExitStatus.NormalExit)
            self.assertEqual(page.profile.currentData(), "balanced")
            self.assertIn("nicht geändert", page.message.text())
            page.phase = "verify"
            page.pending_profile = "power-saver"
            with patch.object(page.process, "readAllStandardOutput", return_value=b"power-saver\n"), patch.object(page.process, "readAllStandardError", return_value=b""):
                page.completed(0, QProcess.ExitStatus.NormalExit)
            self.assertEqual(page.active, "power-saver")
            page.failed(QProcess.ProcessError.FailedToStart)
            self.assertFalse(page.profile.isEnabled())
            self.assertEqual(page.profile.group.checkedId(), -1)
            page.available = {"balanced", "power-saver"}
            page.show_active("balanced")
            self.assertTrue(page.profile.isEnabled())
            self.assertFalse(page.profile.group.button(2).isEnabled())
        finally:
            page.client.preview = True
            page.timeout.stop()
            page.working(False)
            dialog.close()
            home.close()
            dialog.deleteLater()
            home.deleteLater()
