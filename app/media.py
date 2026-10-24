"""MPRIS control over the logged-in user's session bus, without extra tools."""
import asyncio
from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

PLAYER = "org.mpris.MediaPlayer2.Player"
PATH = "/org/mpris/MediaPlayer2"


async def call(bus, destination, path, interface, member, signature="", body=None):
    reply = await asyncio.wait_for(bus.call(Message(
        destination=destination, path=path, interface=interface, member=member,
        signature=signature, body=body or [])), 3)
    if reply.message_type == MessageType.ERROR:
        raise ValueError("Musiksteuerung nicht erreichbar. Bitte den Player erneut öffnen.")
    return reply.body


def player_state(name, props):
    props = {key: value.value for key, value in props.items()}
    playing = props.get("PlaybackStatus") == "Playing"
    return {"player": name, "playing": playing,
            "available": bool(props.get("CanControl") and
                              props.get("CanPause" if playing else "CanPlay"))}


def choose_player(players):
    eligible = [p for p in players if p["available"]]
    return min(eligible, key=lambda p: (not p["playing"], "spotify" not in p["player"].lower(),
                                       p["player"]), default={"available": False})


async def media_request(target=None):
    bus = await asyncio.wait_for(MessageBus().connect(), 3)
    try:
        names = (await call(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus",
                            "org.freedesktop.DBus", "ListNames"))[0]
        names = [name for name in names if name.startswith("org.mpris.MediaPlayer2.")]

        async def inspect(name):
            props = (await call(bus, name, PATH, "org.freedesktop.DBus.Properties",
                                "GetAll", "s", [PLAYER]))[0]
            return player_state(name, props)

        if target is not None:
            if target not in names:
                raise ValueError("Der Player wurde geschlossen. Bitte Musik oder ein Video öffnen.")
            state = await inspect(target)
            if not state["available"]:
                raise ValueError("Dieser Player lässt sich gerade nicht steuern.")
            await call(bus, target, PATH, PLAYER, "Pause" if state["playing"] else "Play")
            return {}
        results = await asyncio.gather(*(inspect(name) for name in names), return_exceptions=True)
        return choose_player([p for p in results if isinstance(p, dict)])
    finally:
        bus.disconnect()
