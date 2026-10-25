"""Screen brightness through PowerDevil on the user's Plasma session bus.

Protocol: KDE/powerdevil daemon/dbus/org.kde.ScreenBrightness*.xml.
Only displays advertised by the service can be changed; no root helper needed.
"""
import asyncio

from dbus_next import DBusError, Message, MessageType
from dbus_next.aio import MessageBus

SERVICE = "org.kde.ScreenBrightness"
PATH = "/org/kde/ScreenBrightness"
DISPLAY = SERVICE + ".Display"
PROPS = "org.freedesktop.DBus.Properties"


async def call(bus, path, interface, member, signature="", body=None):
    reply = await asyncio.wait_for(bus.call(Message(
        destination=SERVICE, path=path, interface=interface, member=member,
        signature=signature, body=body or [])), 5)
    if reply.message_type == MessageType.ERROR:
        raise DBusError(reply.error_name, "Brightness request failed")
    return reply.body


async def displays(bus):
    names = (await call(bus, PATH, PROPS, "Get", "ss", [SERVICE, "DisplaysDBusNames"]))[0].value
    result = []
    for name in names:
        props = (await call(bus, f"{PATH}/{name}", PROPS, "GetAll", "s", [DISPLAY]))[0]
        maximum = props["MaxBrightness"].value
        if maximum <= 0:
            continue
        result.append({"id": name, "name": props["Label"].value or "Bildschirm",
                       "internal": props["IsInternal"].value, "maximum": maximum,
                       "value": max(0, min(100, round(props["Brightness"].value * 100 / maximum)))})
    return sorted(result, key=lambda item: not item["internal"])


async def brightness_request(target=None, value=None):
    if target is not None and (type(value) is not int or not 0 <= value <= 100):
        raise ValueError("Bitte eine Helligkeit zwischen 0 und 100 Prozent wählen.")
    bus = await asyncio.wait_for(MessageBus().connect(), 5)
    try:
        screens = await displays(bus)
        if target is not None:
            screen = next((item for item in screens if item["id"] == target), None)
            if screen is None:
                raise ValueError("Dieser Bildschirm ist nicht mehr verfügbar. Bitte erneut laden.")
            raw = round(value * screen["maximum"] / 100)
            await call(bus, f"{PATH}/{target}", DISPLAY, "SetBrightness", "iu", [raw, 1])
            screens = await displays(bus)
        return {"displays": screens}
    except DBusError as error:
        if error.type in ("org.freedesktop.DBus.Error.ServiceUnknown",
                          "org.freedesktop.DBus.Error.NameHasNoOwner",
                          "org.freedesktop.DBus.Error.UnknownInterface"):
            raise ValueError("Die Bildschirmsteuerung ist nicht verfügbar. Bitte die KDE-Energieverwaltung prüfen.") from error
        if error.type == "org.freedesktop.DBus.Error.UnknownObject":
            raise ValueError("Dieser Bildschirm ist nicht mehr verfügbar. Bitte erneut laden.") from error
        raise
    finally:
        bus.disconnect()
