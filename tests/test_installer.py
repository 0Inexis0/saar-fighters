"""Installer boundaries: all hardware and privileged commands are simulated here."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from installer.core import candidates, validate_request
from installer import backend
from installer.ui import Installer
from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox


def disk(**changes):
    data = {"name": "/dev/vda", "type": "disk", "size": 40 * 1024 ** 3, "model": "Testdisk",
            "serial": "TEST001", "wwn": "", "maj:min": "252:0", "ro": False, "mountpoints": [None]}
    data.update(changes)
    return data


class DiskSafetyTests(unittest.TestCase):
    def test_unmounted_disk_can_be_selected(self):
        self.assertEqual(candidates({"blockdevices": [disk()]})[0]["path"], "/dev/vda")

    def test_live_usb_mounted_partitions_swap_and_lvm_are_excluded(self):
        for child in ({"type": "part", "mountpoints": ["/run/archiso/bootmnt"]},
                      {"type": "part", "mountpoints": ["/home"]},
                      {"type": "part", "mountpoints": ["[SWAP]"]},
                      {"type": "part", "children": [{"type": "lvm", "mountpoints": [None]}]}):
            self.assertEqual(candidates({"blockdevices": [disk(children=[child])]}), [])

    def test_readonly_small_and_non_disks_are_excluded(self):
        for change in ({"ro": True}, {"size": 2_000_000_000}, {"type": "loop"},
                       {"type": "rom"}, {"mountpoints": ["/run/archiso/bootmnt"]}):
            self.assertEqual(candidates({"blockdevices": [disk(**change)]}), [])

    def request(self):
        target = candidates({"blockdevices": [disk()]})[0]
        return target, {"disk": target["path"], "identity": target["identity"],
                        "confirm_erase": target["identity"], "admin_password": "test-only-password"}

    def test_matching_disk_and_confirmation_required(self):
        target, request = self.request()
        self.assertEqual(validate_request(request, [target]), target)
        for changes in ({"disk": "/dev/sda"}, {"identity": "changed"}, {"confirm_erase": ""},
                        {"admin_password": "short"}, {"admin_password": "1234567890\nroot:x"}):
            with self.assertRaises(ValueError):
                validate_request({**request, **changes}, [target])

    def test_replaced_device_at_same_path_is_rejected(self):
        _, request = self.request()
        replacement = candidates({"blockdevices": [disk(serial="ANOTHER") ]})
        with self.assertRaises(ValueError):
            validate_request(request, replacement)

    def test_helper_cannot_install_outside_live_media(self):
        with patch.object(backend.os, "geteuid", return_value=0), \
             patch.object(Path, "is_file", return_value=False), patch.object(backend, "run") as run:
            with self.assertRaises(ValueError):
                backend.install({})
            run.assert_not_called()

    def test_unprivileged_helper_cannot_install(self):
        with patch.object(backend.os, "geteuid", return_value=1000), patch.object(backend, "run") as run:
            with self.assertRaises(ValueError):
                backend.install({})
            run.assert_not_called()

    def test_partition_lock_released_before_device_detection(self):
        events = []
        with patch.object(backend.fcntl, "flock", side_effect=lambda fd, mode: events.append(("lock", mode))), \
             patch.object(backend, "run", side_effect=lambda *args: events.append(args)):
            backend.partition_device("/dev/example", 99)
        unlock = events.index(("lock", backend.fcntl.LOCK_UN))
        self.assertLess(unlock, events.index(("partprobe", "/dev/example")))
        self.assertLess(unlock, events.index(("udevadm", "settle", "--timeout=30")))


class InstallerUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Installer(preview=True)
        self.window.resize(1024, 600)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.running = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def prepare(self):
        self.window.list.setCurrentRow(0)
        self.window.password.setText("test-only-password")
        self.window.repeat.setText("test-only-password")
        self.window.erase.setChecked(True)

    def test_requires_disk_password_match_and_erase_confirmation(self):
        self.assertIsNone(self.window.list.currentItem())
        self.assertFalse(self.window.install.isEnabled())
        self.prepare()
        self.assertTrue(self.window.install.isEnabled())
        self.window.repeat.setText("different-password")
        self.assertFalse(self.window.install.isEnabled())
        self.window.repeat.setText("test-only-password")
        self.window.erase.setChecked(False)
        self.assertFalse(self.window.install.isEnabled())

    def test_final_confirmation_defaults_to_cancel(self):
        self.prepare()
        def cancel():
            dialog = QApplication.activeModalWidget()
            self.assertEqual(dialog.buttonRole(dialog.defaultButton()), QMessageBox.ButtonRole.RejectRole)
            dialog.reject()
        QTimer.singleShot(10, cancel)
        with patch.object(QProcess, "start") as start:
            self.window.begin()
            start.assert_not_called()

    def test_no_early_success_and_no_closing_during_install(self):
        self.window.running = True
        self.window.close()
        self.assertTrue(self.window.isVisible())
        self.window.finished(0, QProcess.ExitStatus.NormalExit)
        self.assertFalse(self.window.done)
        self.assertFalse(self.window.reboot.isVisible())

    def test_small_laptop_geometry(self):
        self.assertEqual((self.window.width(), self.window.height()), (1024, 600))
        self.assertTrue(self.window.rect().contains(self.window.install.mapTo(self.window, self.window.install.rect().bottomRight())))


if __name__ == "__main__":
    unittest.main()
