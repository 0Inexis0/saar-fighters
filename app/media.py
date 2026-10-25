"""MPRIS control over the logged-in user's session bus, without extra tools."""
import asyncio
import math
from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

PLAYER = "org.mpris.MediaPlayer2.Player"
PATH = "/org/mpris/MediaPlayer2"
NO_TRACK = PATH + "/TrackList/NoTrack"
ACTIONS = ("playpause", "previous", "next", "seek", "volume", "shuffle", "repeat")


def number(value, default=0):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else default


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
    text = lambda key: metadata.get(key) if isinstance(metadata.get(key), str) else ""
    track_id = text("mpris:trackid")
    duration = max(0, number(metadata.get("mpris:length"))) / 1_000_000
    control = bool(props.get("CanControl"))
    player_name = name.removeprefix("org.mpris.MediaPlayer2.").split(".")[0]
    return {"player": name, "playing": playing,
            "player_name": player_name.capitalize(),
            "playback_status": props.get("PlaybackStatus", "Stopped"),
            "title": title if isinstance(title, str) else "",
            "album": text("xesam:album"), "art_url": text("mpris:artUrl"),
            "track_id": track_id, "duration": duration,
            "position": max(0, number(props["Position"])) / 1_000_000 if "Position" in props else None,
            "rate": max(0, number(props.get("Rate"), 1)),
            "lyrics": text("xesam:asText"),
            "volume": max(0, min(100, round(number(props.get("Volume")) * 100))),
            "shuffle": bool(props.get("Shuffle")), "repeat": props.get("LoopStatus", "None"),
            "can_seek": bool(control and props.get("CanSeek") and track_id and track_id != NO_TRACK and duration > 0),
            "can_volume": control and "Volume" in props,
            "can_shuffle": control and "Shuffle" in props,
            "can_repeat": control and "LoopStatus" in props,
            "artist": ", ".join(artist for artist in artists if isinstance(artist, str))
                      if isinstance(artists, list) else "",
            "can_previous": bool(props.get("CanControl") and props.get("CanGoPrevious")),
            "can_next": bool(props.get("CanControl") and props.get("CanGoNext")),
            "available": bool(props.get("CanControl") and
                              props.get("CanPause" if playing else "CanPlay"))}


def choose_player(players):
    eligible = [p for p in players if p["available"] or p.get("can_previous") or p.get("can_next")
                or p.get("playing") or p.get("title")]
    return min(eligible, key=lambda p: (not p["playing"], "spotify" not in p["player"].lower(),
                                       p["player"]), default={"available": False})


async def media_request(target=None, action="playpause", **args):
    if action not in ACTIONS:
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
            capability = "available" if action == "playpause" else "can_" + action
            if not state[capability]:
                raise ValueError("Dieser Player lässt sich gerade nicht steuern.")
            if action == "seek":
                position = number(args.get("position"), -1)
                if args.get("track_id") != state["track_id"] or not 0 <= position <= state["duration"]:
                    raise ValueError("Der Titel hat gewechselt. Bitte die Wiedergabeposition erneut wählen.")
                await call(bus, target, PATH, PLAYER, "SetPosition", "ox",
                           [state["track_id"], int(position * 1_000_000)])
                return {}
            if action in ("volume", "shuffle", "repeat"):
                value = args.get("value")
                if action == "volume":
                    if not 0 <= number(value, -1) <= 100:
                        raise ValueError("Die Lautstärke muss zwischen 0 und 100 liegen.")
                    prop, variant = "Volume", Variant("d", float(value) / 100)
                elif action == "shuffle":
                    if not isinstance(value, bool):
                        raise ValueError("Ungültige Zufallswiedergabe.")
                    prop, variant = "Shuffle", Variant("b", value)
                else:
                    if value not in ("None", "Track", "Playlist"):
                        raise ValueError("Ungültiger Wiederholungsmodus.")
                    prop, variant = "LoopStatus", Variant("s", value)
                await call(bus, target, PATH, "org.freedesktop.DBus.Properties", "Set", "ssv",
                           [PLAYER, prop, variant])
                return {}
            method = {"playpause": "Pause" if state["playing"] else "Play",
                      "previous": "Previous", "next": "Next"}[action]
            await call(bus, target, PATH, PLAYER, method)
            return {}
        results = await asyncio.gather(*(inspect(name) for name in names), return_exceptions=True)
        return choose_player([p for p in results if isinstance(p, dict)])
    finally:
        bus.disconnect()
