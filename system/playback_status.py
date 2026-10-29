#!/usr/bin/env python3
"""Read playback progress without track names, artwork, account data, or URLs."""
import asyncio
import json
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus


async def status():
    bus = await asyncio.wait_for(MessageBus().connect(), 3)
    async def call(destination, path, interface, member, signature="", body=None):
        reply = await asyncio.wait_for(bus.call(Message(destination=destination, path=path,
            interface=interface, member=member, signature=signature, body=body or [])), 2)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError("Player unavailable")
        return reply.body
    try:
        names = (await call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                            "org.freedesktop.DBus", "ListNames"))[0]
        result = []
        for name in names:
            kind = next((label for prefix, label in (("org.mpris.MediaPlayer2.spotify", "Spotify"),
                ("org.mpris.MediaPlayer2.firefox", "Firefox"), ("org.mpris.MediaPlayer2.vlc", "VLC"))
                + (("org.mpris.MediaPlayer2.chromium", "Brave/Chromium"), ("org.mpris.MediaPlayer2.brave", "Brave"))
                if name == prefix or name.startswith(prefix + ".")), None)
            if not kind:
                continue
            row = {"player": kind}
            for prop in ("PlaybackStatus", "Position"):
                try:
                    value = (await call(name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties",
                        "Get", "ss", ["org.mpris.MediaPlayer2.Player", prop]))[0].value
                    if prop == "Position" and isinstance(value, int):
                        row["position_seconds"] = round(value / 1000000, 1)
                    elif prop == "PlaybackStatus" and value in {"Playing", "Paused", "Stopped"}:
                        row["state"] = value
                except (RuntimeError, asyncio.TimeoutError):
                    row["error"] = "unavailable"
            result.append(row)
        return result
    finally:
        bus.disconnect()


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(asyncio.wait_for(status(), 12))))
    except Exception:
        print(json.dumps({"error": "playback status unavailable"}))
