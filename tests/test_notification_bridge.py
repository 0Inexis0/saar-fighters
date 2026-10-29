"""Notification protocol, shared history and isolated Linux session-bus checks."""
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method
from notification_watch import NotificationCapture, plain_body, watch, SERVICE, PATH
from notifications import NotificationCenter
from notification_bridge import NotificationBridge
from PySide6.QtWidgets import QApplication, QWidget


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.capture = NotificationCapture(":1.10", self.events.append, "test")

    def notify(self, serial=1, replaces=0, title="Download fertig"):
        return Message(destination=SERVICE, sender=":1.20", serial=serial, path=PATH,
                       interface=SERVICE, member="Notify", signature="susssasa{sv}i",
                       body=["Firefox", replaces, "", title, "<b>Datei</b><br/>fertig &amp; bereit",
                             [], {"transient": Variant("b", True)}, -1])

    def reply(self, serial=1, identifier=42):
        return Message(message_type=MessageType.METHOD_RETURN, sender=":1.10", destination=":1.20",
                       reply_serial=serial, signature="u", body=[identifier])

    def test_transient_notification_and_replacement_have_same_key_and_plain_text(self):
        self.assertTrue(self.capture.handle(self.notify()))
        self.assertFalse(self.events)
        self.capture.handle(self.reply())
        self.assertEqual(self.events[0]["body"], "Datei\nfertig & bereit")
        self.assertEqual(self.events[0]["source"], "Firefox")
        self.capture.handle(self.notify(2, 42, "Download aktualisiert"))
        self.capture.handle(self.reply(2))
        self.assertEqual(self.events[0]["key"], self.events[1]["key"])
        self.assertNotIn("hints", self.events[0])

    def test_unrelated_calls_wrong_server_and_error_do_not_enter_history(self):
        unrelated = self.notify()
        unrelated.interface = "org.example.Private"
        self.capture.handle(unrelated)
        self.capture.handle(self.reply())
        self.assertFalse(self.events)
        self.capture.handle(self.notify())
        wrong = self.reply()
        wrong.sender = ":1.99"
        self.capture.handle(wrong)
        self.assertFalse(self.events)
        self.capture.handle(Message(message_type=MessageType.ERROR, sender=":1.10", destination=":1.20",
                                    reply_serial=1, error_name="org.example.Failed"))
        self.assertFalse(self.capture.pending)
        self.assertFalse(self.events)

    def test_pending_and_body_are_bounded(self):
        for i in range(300):
            self.capture.handle(self.notify(i + 1))
        self.assertEqual(len(self.capture.pending), 256)
        self.assertEqual(len(plain_body("x" * 20000)), 8192)

    def test_history_replacements_read_state_clear_and_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            center = NotificationCenter(path=Path(folder) / "events.json")
            self.capture.emit = center.desktop_event
            self.capture.handle(self.notify())
            self.capture.handle(self.reply())
            center.mark_read()
            self.capture.handle(self.notify(2, 42))
            self.capture.handle(self.reply(2))
            self.assertEqual(center.unread, 0)  # Identical progress refresh is not new.
            self.capture.handle(self.notify(3, 42, "Fertig"))
            self.capture.handle(self.reply(3))
            self.assertEqual(len(center.items), 1)
            self.assertEqual(center.unread, 1)
            restored = NotificationCenter(path=center.path)
            self.assertEqual(restored.items[0]["source"], "Firefox")
            center.clear()
            self.assertFalse(center.desktop_items)
            self.assertEqual(NotificationCenter(path=center.path).items, [])

    def test_disconnect_is_visible_once_and_recovery_clears_warning(self):
        center = NotificationCenter(preview=True)
        center.desktop_event({"event": "unavailable"})
        center.desktop_event({"event": "unavailable"})
        self.assertEqual(len(center.items), 1)
        self.assertTrue(center.service_error)
        center.desktop_event({"event": "ready"})
        self.assertFalse(center.service_error)

    def test_preview_starts_no_listener_or_retry(self):
        app = QApplication.instance() or QApplication([])
        home = QWidget()
        center = NotificationCenter(preview=True)
        with patch("notification_bridge.QProcess.start") as start:
            bridge = NotificationBridge(center, home, preview=True)
            bridge.start()
            bridge.lost()
            start.assert_not_called()
            self.assertFalse(bridge.retry.isActive())
            self.assertFalse(center.items)
            bridge.stop()
        home.deleteLater()
        app.processEvents()


class TestServer(ServiceInterface):
    def __init__(self):
        super().__init__(SERVICE)

    @method()
    def Notify(self, app: 's', replaces: 'u', icon: 's', title: 's', body: 's',
               actions: 'as', hints: 'a{sv}', timeout: 'i') -> 'u':
        return replaces or 42


@unittest.skipUnless(sys.platform == "linux" and shutil.which("dbus-daemon"), "Needs Linux and dbus-daemon")
class SessionBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_bus_capture_keeps_notification_server_owner(self):
        daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        server = client = task = None
        try:
            address = (await asyncio.wait_for(asyncio.to_thread(daemon.stdout.readline), 5)).strip()
            with patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": address}):
                server = await MessageBus().connect()
                server.export(PATH, TestServer())
                await server.request_name(SERVICE)
                client = await MessageBus().connect()
                events = []
                task = asyncio.create_task(watch(events.append))
                async def wait_for(predicate):
                    async with asyncio.timeout(5):
                        while not predicate():
                            await asyncio.sleep(.01)
                await wait_for(lambda: any(e["event"] == "ready" for e in events))
                for replaces in (0, 42):
                    reply = await client.call(Message(destination=SERVICE, path=PATH, interface=SERVICE,
                        member="Notify", signature="susssasa{sv}i",
                        body=["Test App", replaces, "", "Test", "Hallo", [], {}, -1]))
                    self.assertEqual(reply.body, [42])
                await wait_for(lambda: len([e for e in events if e["event"] == "notification"]) == 2)
                notices = [e for e in events if e["event"] == "notification"]
                self.assertEqual(notices[0]["key"], notices[1]["key"])
                owner = await client.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus", member="GetNameOwner", signature="s", body=[SERVICE]))
                self.assertEqual(owner.body, [server.unique_name])
                await server.release_name(SERVICE)
                await asyncio.wait_for(task, 5)
        finally:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            for bus in (client, server):
                if bus:
                    bus.disconnect()
            daemon.terminate()
            await asyncio.to_thread(daemon.wait, 5)
            daemon.stdout.close()
