"""Regression checks for app isolation, failed launches and helper cleanup."""
import asyncio
import os
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import application_runner as runner
from backend import Backend
from devices import DeviceClient
from main import Home, UpdateDialog
from maintenance import MaintenancePage
from media_content import parse_lrc
import rocket


class ApplicationRunnerTests(unittest.TestCase):
    def test_apps_use_separate_session_services_with_literal_arguments(self):
        command = ["brave", "https://example.org/?x=$HOME&other=a b"]
        with patch.object(runner.sys, "platform", "linux"), patch.dict(
                os.environ, {"WAYLAND_DISPLAY": "wayland-9", "UNRELATED_SECRET": "do-not-forward"}):
            result = runner.application_command(command, "web")
        self.assertEqual(result[0], "systemd-run")
        self.assertIn("--wait", result)
        self.assertIn("--expand-environment=no", result)
        self.assertIn("--property=ExitType=cgroup", result)
        self.assertIn("--property=PartOf=graphical-session.target", result)
        self.assertNotIn("--property=PartOf=saar-home.service", result)
        self.assertIn("--setenv=WAYLAND_DISPLAY=wayland-9", result)
        self.assertFalse(any("do-not-forward" in arg for arg in result))
        self.assertEqual(result[-2:], command)

    def test_supervisor_drains_large_output_and_records_only_categories(self):
        script = "import sys; sys.stdout.write('x'*200000); sys.stderr.write('malloc '+('private-url '*20000)); sys.exit(7)"
        with patch.object(runner, "record") as record:
            code = runner.supervise("web", [sys.executable, "-c", script])
        self.assertEqual(code, 7)
        self.assertEqual(record.call_args_list, [
            unittest.mock.call("web", "start"),
            unittest.mock.call("web", "error", category="memory"),
            unittest.mock.call("web", "exit", code=7)])

    @unittest.skipUnless(os.name == "posix", "POSIX signals required")
    def test_supervisor_reports_signal_death_as_failure(self):
        with patch.object(runner, "record") as record:
            code = runner.supervise("spotify", [sys.executable, "-c",
                "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"])
        self.assertEqual(code, 128 + signal.SIGTERM)
        record.assert_called_with("spotify", "exit", code=-signal.SIGTERM)

    def test_missing_executable_is_reported(self):
        with patch.object(runner, "record") as record:
            self.assertEqual(runner.supervise("files", ["/missing/saar-test-app"]), 127)
        record.assert_called_once_with("files", "exit", code=127)

    def test_game_server_survives_launcher_and_waits_for_health_after_submission(self):
        child = Mock()
        child.poll.return_value = 0
        with patch.object(rocket.sys, "platform", "linux"), \
                patch.object(rocket, "server_ready", side_effect=[False, False, True]), \
                patch.object(rocket.subprocess, "Popen", return_value=child) as spawn, \
                patch.object(rocket.time, "sleep"):
            rocket.ensure_server()
        command = spawn.call_args.args[0]
        self.assertEqual(command[0], "systemd-run")
        self.assertNotIn("--wait", command)
        self.assertEqual(command[-1], "--serve")

    def test_oversized_lyrics_offset_does_not_abort_rendering(self):
        for offset in ("9" * 5000, "9" * 400, "-" + "9" * 5000):
            self.assertEqual(parse_lrc(f"[offset:{offset}]\n[00:02]Music"), [(2, "Music")])


class ProcessUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_failed_start_releases_rocket_guard_and_allows_retry(self):
        home = Home(preview=True)
        try:
            with patch("main.application_command", side_effect=lambda command, _: command), \
                    patch("main.shutil.which", return_value="/missing/saar-test-app"), \
                    patch("main.record_health"):
                for _ in range(3):
                    home.start_application(["/missing/saar-test-app"], "rocket")
                    for _ in range(100):
                        if not home.processes:
                            break
                        QTest.qWait(10)
                    self.assertEqual(home.processes, [])
        finally:
            home.close()
            home.deleteLater()
            self.app.processEvents()

    def test_worker_stderr_is_discarded_even_during_repeated_device_failure(self):
        client = DeviceClient(preview=True)
        try:
            client.process.start(sys.executable, ["-c", "import sys; sys.stderr.write('failure'*200000)"])
            self.assertTrue(client.process.waitForFinished(5000))
            self.assertEqual(client.process.exitCode(), 0)
            self.assertEqual(bytes(client.process.readAllStandardError()), b"")
        finally:
            client.stop()
            client.deleteLater()

    def test_long_update_and_maintenance_logs_keep_only_recent_lines(self):
        home = Home(preview=True)
        try:
            for dialog in (UpdateDialog(home, preview=True), MaintenancePage(home, preview=True)):
                dialog.output.setPlainText("\n".join(f"line {i}" for i in range(3000)))
                self.assertEqual(dialog.output.document().blockCount(), 2000)
                self.assertTrue(dialog.output.toPlainText().startswith("line 1000\n"))
                self.assertTrue(dialog.output.toPlainText().endswith("line 2999"))
                dialog.deleteLater()
        finally:
            home.close()
            home.deleteLater()
            self.app.processEvents()


class AudioCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_kills_and_drains_helper_before_propagating(self):
        child = Mock()
        child.communicate = AsyncMock(side_effect=[asyncio.CancelledError(), (b"", b"")])
        with patch("backend.asyncio.create_subprocess_exec", AsyncMock(return_value=child)):
            with self.assertRaises(asyncio.CancelledError):
                await Backend(Mock()).pactl("info")
        child.kill.assert_called_once()
        self.assertEqual(child.communicate.await_count, 2)

    async def test_helper_exit_race_preserves_timeout_and_reaps_pipes(self):
        child = Mock()
        child.kill.side_effect = ProcessLookupError()
        child.communicate = AsyncMock(side_effect=[TimeoutError(), (b"", b"")])
        with patch("backend.asyncio.create_subprocess_exec", AsyncMock(return_value=child)):
            with self.assertRaises(TimeoutError):
                await Backend(Mock()).pactl("info")
        self.assertEqual(child.communicate.await_count, 2)

    async def test_real_cancelled_audio_helper_is_reaped(self):
        original = asyncio.create_subprocess_exec
        children = []

        async def start(*args, **kwargs):
            child = await original(sys.executable, "-c", "import time; time.sleep(30)", **kwargs)
            children.append(child)
            return child

        with patch("backend.asyncio.create_subprocess_exec", start):
            task = asyncio.create_task(Backend(Mock()).pactl("info"))
            while not children:
                await asyncio.sleep(.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        self.assertIsNotNone(children[0].returncode)


if __name__ == "__main__":
    unittest.main()
