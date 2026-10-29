import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from maintenance import MaintenancePage, MaintenanceWindow, HELPER
from PySide6.QtCore import QProcess, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox


class MaintenanceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def page(self, section="remote"):
        page = MaintenancePage(preview=True, section=section)
        page.show()
        self.addCleanup(page.deleteLater)
        self.addCleanup(page.reject)
        self.app.processEvents()
        return page

    def test_preview_never_starts_privileged_operations(self):
        for section in ("remote", "recovery"):
            page = self.page(section)
            with patch.object(QProcess, "start") as start:
                QTest.mouseClick(page.action, Qt.MouseButton.LeftButton)
                start.assert_not_called()
                self.assertIn("Vorschau", page.message.text())

    def test_restore_cancel_is_default_and_never_calls_pkexec(self):
        page = self.page("recovery")
        page.preview = False
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel) as confirm, \
                patch.object(page.worker, "start") as start:
            page.begin()
            self.assertEqual(confirm.call_args.args[-1], QMessageBox.StandardButton.Cancel)
            start.assert_not_called()

    def test_restore_passes_backup_identity_and_blocks_escape(self):
        page = self.page("recovery")
        page.preview = False
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                patch.object(page.worker, "start") as start:
            page.begin()
            start.assert_called_once_with("pkexec", [HELPER, "restore", "c" * 64])
            self.assertFalse(page.back.isEnabled())
            page.reject()
            self.assertTrue(page.isVisible())
        page.preview = True
        page.completed(1, QProcess.ExitStatus.NormalExit)
        self.assertIn("fehlgeschlagen", page.message.text())

    def test_ssh_changes_require_privileged_fixed_helper(self):
        page = self.page()
        page.preview = False
        with patch.object(page.worker, "start") as start:
            page.begin()
            start.assert_called_once_with("pkexec", [HELPER, "disable-ssh"])
        page.preview = True
        page.completed(126, QProcess.ExitStatus.NormalExit)
        self.assertIn("abgebrochen", page.message.text())

    def test_missing_backup_and_live_media_disable_restore(self):
        page = self.page("recovery")
        page.show_status({"surface": {"available": False, "reason": "Keine Sicherung"}})
        self.assertFalse(page.action.isEnabled())
        page.show_status({"surface": {"available": True}, "live": True})
        self.assertFalse(page.action.isEnabled())

    def test_rescue_window_cannot_close_during_operation(self):
        window = MaintenanceWindow(preview=True)
        window.show()
        window.pages[0].working(True)
        window.reject()
        window.close()
        self.assertTrue(window.isVisible())
        window.pages[0].working(False)
        window.reject()
        self.assertFalse(window.isVisible())
        window.deleteLater()

    def test_missing_packages_can_be_installed_from_page(self):
        page = self.page()
        page.show_status({"ssh": {"installed": False, "state": "unknown"}, "internet": {"state": "missing"}})
        self.assertTrue(page.action.isEnabled())
        self.assertEqual(page.action_name, "install-remote")
        page.preview = False
        with patch.object(page.worker, "start") as start:
            page.begin()
            start.assert_called_once_with("pkexec", [HELPER, "install-remote"])
        page.preview = True
        page.completed(1, QProcess.ExitStatus.NormalExit)

    def test_login_requires_valid_url_and_never_runs_as_root(self):
        page = self.page()
        page.preview = False
        from PySide6.QtGui import QDesktopServices
        for url, expected in (("https://login.tailscale.com/a/test", True), ("file:///etc/passwd", False)):
            page.show_status({"ssh": {"state": "active"}, "internet": {"state": "NeedsLogin", "auth_url": url}})
            self.assertEqual(page.login.isEnabled(), expected)
            with patch.object(QDesktopServices, "openUrl", return_value=True) as browser:
                page.open_login()
                self.assertEqual(browser.called, expected)

    def test_internet_action_is_privileged_and_blocks_all_controls(self):
        page = self.page()
        page.show_status({"ssh": {"state": "active"}, "internet": {"state": "Stopped"}})
        page.preview = False
        with patch.object(page.worker, "start") as start:
            page.begin_internet()
            start.assert_called_once_with("pkexec", [HELPER, "connect-internet"])
            self.assertFalse(page.internet.isEnabled())
            self.assertFalse(page.login.isEnabled())
        page.preview = True
        page.completed(0, QProcess.ExitStatus.NormalExit)


if __name__ == "__main__":
    unittest.main()
