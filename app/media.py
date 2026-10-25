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
    metadata = props.get("Metadata", {})
    metadata = {key: value.value for key, value in metadata.items()}
    title = metadata.get("xesam:title", "")
    artists = metadata.get("xesam:artist", [])
    player_name = name.removeprefix("org.mpris.MediaPlayer2.").split(".")[0]
    return {"player": name, "playing": playing,
            "player_name": player_name.capitalize(),
            "playback_status": props.get("PlaybackStatus", "Stopped"),
            "title": title if isinstance(title, str) else "",
            "artist": ", ".join(artist for artist in artists if isinstance(artist, str))
                      if isinstance(artists, list) else "",
            "can_previous": bool(props.get("CanControl") and props.get("CanGoPrevious")),
            "can_next": bool(props.get("CanControl") and props.get("CanGoNext")),
            "available": bool(props.get("CanControl") and
                              props.get("CanPause" if playing else "CanPlay"))}


def choose_player(players):
    eligible = [p for p in players if p["available"] or p.get("can_previous") or p.get("can_next")]
    return min(eligible, key=lambda p: (not p["playing"], "spotify" not in p["player"].lower(),
                                       p["player"]), default={"available": False})


async def media_request(target=None, action="playpause"):
    if action not in ("playpause", "previous", "next"):
        raise ValueError("Diese Medienaktion ist nicht verfügbar.")
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
            capability = {"playpause": "available", "previous": "can_previous", "next": "can_next"}[action]
            if not state[capability]:
                raise ValueError("Dieser Player lässt sich gerade nicht steuern.")
            method = {"playpause": "Pause" if state["playing"] else "Play",
                      "previous": "Previous", "next": "Next"}[action]
            await call(bus, target, PATH, PLAYER, method)
            return {}
        results = await asyncio.gather(*(inspect(name) for name in names), return_exceptions=True)
        return choose_player([p for p in results if isinstance(p, dict)])
    finally:
        bus.disconnect()
