"""Read standard desktop notifications, leaving delivery and actions with Plasma.

Only Notify calls and replies from the notification server are monitored.
Replies without a matching Notify are discarded. Images, action tokens and
notification hints are never saved.
"""
import asyncio
from collections import OrderedDict
from html.parser import HTMLParser
import json
import uuid

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

SERVICE = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
DBUS = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"


class PlainBody(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("p", "div", "li"):
            self.parts.append("\n")


def plain_body(value):
    parser = PlainBody()
    parser.feed(value[:16384])
    parser.close()
    return "".join(parser.parts).strip()[:8192]


class NotificationCapture:
    def __init__(self, owner, emit, namespace=None):
        self.owner = owner
        self.emit = emit
        self.namespace = namespace or uuid.uuid4().hex
        self.pending = OrderedDict()

    def handle(self, message):
        if (message.message_type == MessageType.METHOD_CALL and message.interface == SERVICE
                and message.path == PATH and message.member == "Notify"
                and message.destination in (SERVICE, self.owner)
                and message.signature == "susssasa{sv}i"):
            source, _, _, title, body, _, _, _ = message.body
            self.pending[(message.sender, message.serial)] = {
                "event": "notification", "source": source[:256] or "Anwendung",
                "title": title[:256] or source[:256] or "Mitteilung", "body": plain_body(body),
            }
            while len(self.pending) > 256:
                self.pending.popitem(last=False)
        elif message.sender == self.owner and message.message_type in (MessageType.METHOD_RETURN, MessageType.ERROR):
            event = self.pending.pop((message.destination, message.reply_serial), None)
            if event and message.message_type == MessageType.METHOD_RETURN and message.signature == "u" and message.body[0]:
                event["key"] = f"{self.namespace}:{message.body[0]}"
                self.emit(event)
        # Monitors must never auto-reply to the messages they observe.
        return True


async def checked_call(bus, message):
    reply = await asyncio.wait_for(bus.call(message), 5)
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError("Notification monitoring unavailable")
    return reply


async def watch(emit):
    bus = await asyncio.wait_for(MessageBus().connect(), 5)
    try:
        reply = await checked_call(bus, Message(destination=DBUS, path=DBUS_PATH, interface=DBUS,
                                               member="GetNameOwner", signature="s", body=[SERVICE]))
        owner = reply.body[0]
        capture = NotificationCapture(owner, emit)
        rules = [f"type='method_call',interface='{SERVICE}',path='{PATH}',member='Notify'",
                 f"type='method_return',sender='{owner}'", f"type='error',sender='{owner}'",
                 f"type='signal',sender='{DBUS}',interface='{DBUS}',member='NameOwnerChanged',arg0='{SERVICE}'"]
        # Install before BecomeMonitor so the first Notify cannot trigger an automatic reply.
        def handle(message):
            if message.sender == DBUS and message.message_type in (MessageType.METHOD_RETURN, MessageType.ERROR):
                return False  # Deliver the BecomeMonitor result to its pending call.
            if (message.message_type == MessageType.SIGNAL and message.sender == DBUS
                    and message.interface == DBUS and message.member == "NameOwnerChanged"
                    and message.body[0] == SERVICE):
                bus.disconnect()  # Reconnect with the new server's unique name.
            return capture.handle(message)
        bus.add_message_handler(handle)
        await checked_call(bus, Message(destination=DBUS, path=DBUS_PATH,
                                       interface=DBUS + ".Monitoring", member="BecomeMonitor",
                                       signature="asu", body=[rules, 0]))
        emit({"event": "ready"})
        await bus.wait_for_disconnect()
    finally:
        bus.disconnect()


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(watch(emit))
    except Exception:
        emit({"event": "unavailable"})
