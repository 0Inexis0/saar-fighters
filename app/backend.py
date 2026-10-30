#!/usr/bin/env python3
"""Unprivileged device worker. JSON on stdin/stdout; secrets never enter argv/logs.

Keeps a single system-bus connection alive for discovery and BlueZ pairing.
Independent requests run concurrently so a pairing question never blocks input.
"""
import asyncio
import json
import os
import pwd
from pathlib import Path
import sys
import uuid

from dbus_next import BusType, DBusError, Message, MessageType, Variant
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method

from hardware import friendly_error, security_mode, wifi_password_valid
from media import media_request
from brightness import brightness_request
from audio import AudioRouter

NM = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
BLUEZ = "org.bluez"
UP = "org.freedesktop.UPower"
UP_PATH = "/org/freedesktop/UPower"
PROPS = "org.freedesktop.DBus.Properties"


def plain(value):
    if isinstance(value, Variant):
        return plain(value.value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


class PairingAgent(ServiceInterface):
    def __init__(self, backend):
        super().__init__("org.bluez.Agent1")
        self.backend = backend
        self.pending = {}

    async def question(self, kind, device, code=""):
        if device not in self.backend.pairing_devices:
            raise DBusError("org.bluez.Error.Rejected", "Pairing was not initiated here")
        token = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[token] = future
        emit({"event": "pairing", "token": token, "kind": kind, "device": device, "code": code})
        try:
            answer = await asyncio.wait_for(future, 90)
            if not answer.get("accepted"):
                raise DBusError("org.bluez.Error.Rejected", "Canceled")
            return answer.get("value", "")
        finally:
            self.pending.pop(token, None)
            emit({"event": "pairing_closed", "token": token})

    @method()
    async def RequestConfirmation(self, device: 'o', passkey: 'u'):
        await self.question("confirm", device, f"{passkey:06d}")

    @method()
    async def RequestPinCode(self, device: 'o') -> 's':
        value = await self.question("pin", device)
        if not 1 <= len(value) <= 16:
            raise DBusError("org.bluez.Error.Rejected", "Invalid PIN")
        return value

    @method()
    async def RequestPasskey(self, device: 'o') -> 'u':
        value = await self.question("passkey", device)
        if not value.isascii() or not value.isdigit() or len(value) > 6:
            raise DBusError("org.bluez.Error.Rejected", "Invalid passkey")
        return int(value)

    @method()
    async def RequestAuthorization(self, device: 'o'):
        await self.question("authorize", device)

    @method()
    async def AuthorizeService(self, device: 'o', service: 's'):
        if device not in self.backend.pairing_devices:
            raise DBusError("org.bluez.Error.Rejected", "Unsolicited service")

    @method()
    def DisplayPasskey(self, device: 'o', passkey: 'u', entered: 'q'):
        if device in self.backend.pairing_devices:
            emit({"event": "pairing", "kind": "display", "device": device,
                  "code": f"{passkey:06d}", "entered": entered})

    @method()
    def DisplayPinCode(self, device: 'o', pincode: 's'):
        if device in self.backend.pairing_devices:
            emit({"event": "pairing", "kind": "display", "device": device, "code": pincode})

    @method()
    def Cancel(self):
        for token, future in list(self.pending.items()):
            if not future.done():
                future.set_result({"accepted": False})
        emit({"event": "pairing_closed"})

    @method()
    def Release(self):
        self.Cancel()
        self.backend.agent_registered = False


class Backend:
    def __init__(self, bus):
        self.bus = bus
        self.audio_router = AudioRouter(lambda *args: self.pactl(*args))
        self.audio_preferences = Path.home() / ".config/saar-fighters/audio.json"
        try:
            self.auto_audio = json.loads(self.audio_preferences.read_text()).get("auto_bluetooth", True) is True
        except (OSError, ValueError, AttributeError):
            self.auto_audio = True
        self.agent = PairingAgent(self)
        self.agent_registered = False
        self.pairing_devices = set()
        self.discovery_owned = set()
        self.locks = {key: asyncio.Lock() for key in ("wifi", "bt", "audio", "media", "brightness")}

    async def call(self, service, path, interface, member, signature="", body=None, timeout=12):
        reply = await asyncio.wait_for(self.bus.call(Message(
            destination=service, path=path, interface=interface, member=member,
            signature=signature, body=body or [])), timeout)
        if reply.message_type == MessageType.ERROR:
            raise DBusError(reply.error_name, "Device request failed")
        return reply.body

    async def props(self, service, path, interface):
        return plain((await self.call(service, path, PROPS, "GetAll", "s", [interface]))[0])

    async def set_prop(self, service, path, interface, key, value):
        await self.call(service, path, PROPS, "Set", "ssv", [interface, key, value])

    async def network(self):
        props = await self.props(NM, NM_PATH, NM)
        name = ""
        active = props.get("PrimaryConnection", "/")
        if active != "/":
            name = (await self.props(NM, active, NM + ".Connection.Active")).get("Id", "")
        return {"state": props.get("State", 0), "name": name,
                "type": props.get("PrimaryConnectionType", ""),
                "wireless": props.get("WirelessEnabled", False),
                "connectivity": props.get("Connectivity", 0)}

    async def wireless_devices(self):
        result = []
        paths = (await self.call(NM, NM_PATH, NM, "GetDevices"))[0]
        for path in paths:
            props = await self.props(NM, path, NM + ".Device")
            if props.get("DeviceType") == 2:
                result.append((path, props))
        return result

    async def wifi(self, scan=False):
        general = await self.props(NM, NM_PATH, NM)
        devices = await self.wireless_devices()
        if scan and general.get("WirelessEnabled"):
            for path, _ in devices:
                try:
                    await self.call(NM, path, NM + ".Device.Wireless", "RequestScan", "a{sv}", [{}])
                except DBusError as exc:
                    if not exc.type.endswith(("NotAllowed", "ScanningTooOften")):
                        raise
            if devices:
                await asyncio.sleep(2)
        networks = {}
        for path, props in devices:
            wifi = await self.props(NM, path, NM + ".Device.Wireless")
            saved = {}
            for connection in props.get("AvailableConnections", []):
                settings = plain((await self.call(NM, connection, NM + ".Settings.Connection", "GetSettings"))[0])
                ssid = settings.get("802-11-wireless", {}).get("ssid")
                if ssid is not None:
                    saved[bytes(ssid)] = connection
            for ap_path in wifi.get("AccessPoints", []):
                try:
                    ap = await self.props(NM, ap_path, NM + ".AccessPoint")
                except DBusError:
                    continue  # Access point disappeared during scanning.
                ssid_bytes = bytes(ap.get("Ssid", []))
                ssid = ssid_bytes.decode("utf-8", errors="replace")
                if not ssid:
                    continue
                mode = security_mode(ap.get("Flags", 0), ap.get("WpaFlags", 0), ap.get("RsnFlags", 0))
                entry = {"path": ap_path, "device": path, "name": ssid, "mode": mode,
                         "strength": ap.get("Strength", 0),
                         "connected": ap_path == wifi.get("ActiveAccessPoint"),
                         "saved": saved.get(ssid_bytes, "")}
                key = (ssid, mode)
                old = networks.get(key)
                if not old or (entry["connected"], entry["strength"]) > (old["connected"], old["strength"]):
                    networks[key] = entry
        return {"available": bool(devices), "enabled": general.get("WirelessEnabled", False),
                "hardware_enabled": general.get("WirelessHardwareEnabled", False),
                "networks": sorted(networks.values(), key=lambda n: (not n["connected"], -n["strength"], n["name"]))}

    async def wifi_connect(self, args):
        # Re-read the scan; never trust a path/security mode supplied by the UI.
        current = await self.wifi()
        selected = next((n for n in current["networks"] if n["path"] == args.get("path")), None)
        if not selected:
            raise ValueError("Das WLAN ist nicht mehr sichtbar. Bitte erneut suchen.")
        ap_path, device = selected["path"], selected["device"]
        password = args.get("password", "")
        if selected["connected"]:
            return {"message": "Dieses WLAN ist bereits verbunden."}
        if selected["saved"] and not password:
            active = (await self.call(NM, NM_PATH, NM, "ActivateConnection", "ooo",
                                     [selected["saved"], device, ap_path]))[0]
        else:
            mode = selected["mode"]
            if mode in ("enterprise", "unsupported"):
                raise ValueError("Dieses WLAN benötigt eine besondere Einrichtung durch die Vereinsadministration.")
            if not wifi_password_valid(mode, password):
                raise ValueError("Bitte ein gültiges WLAN-Passwort eingeben (bei WPA2 mindestens 8 Zeichen).")
            ap = await self.props(NM, ap_path, NM + ".AccessPoint")
            settings = {
                "connection": {"id": Variant("s", selected["name"]),
                               "type": Variant("s", "802-11-wireless"),
                               "uuid": Variant("s", str(uuid.uuid4())),
                               "permissions": Variant("as", [f"user:{pwd.getpwuid(os.getuid()).pw_name}:"])},
                "802-11-wireless": {"ssid": Variant("ay", bytes(ap["Ssid"])),
                                   "mode": Variant("s", "infrastructure")},
                "ipv4": {"method": Variant("s", "auto")},
                "ipv6": {"method": Variant("s", "auto")},
            }
            if mode != "open":
                settings["802-11-wireless-security"] = {"key-mgmt": Variant("s", mode)}
                if mode != "owe":
                    settings["802-11-wireless-security"]["psk"] = Variant("s", password)
            _, active = await self.call(NM, NM_PATH, NM, "AddAndActivateConnection", "a{sa{sv}}oo",
                                        [settings, device, ap_path])
        # Activation returns before authentication/DHCP completes.
        for _ in range(70):
            state = (await self.props(NM, active, NM + ".Connection.Active")).get("State")
            if state == 2:
                return {"message": "WLAN verbunden."}
            if state in (3, 4):
                raise ValueError("WLAN-Verbindung fehlgeschlagen. Bitte Passwort und Empfang prüfen.")
            await asyncio.sleep(1)
        raise TimeoutError()

    async def bluetooth(self):
        # BlueZ intentionally does not start when the kernel has no Bluetooth class.
        if not Path("/sys/class/bluetooth").exists():
            return {"available": False, "powered": False, "adapters": [], "devices": []}
        objects = plain((await self.call(BLUEZ, "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"))[0])
        adapters, devices = [], []
        for path, interfaces in objects.items():
            if BLUEZ + ".Adapter1" in interfaces:
                adapters.append({"path": path, **interfaces[BLUEZ + ".Adapter1"]})
            if BLUEZ + ".Device1" in interfaces:
                p = interfaces[BLUEZ + ".Device1"]
                devices.append({"path": path, "name": p.get("Alias") or p.get("Name") or p.get("Address"),
                                "connected": p.get("Connected", False), "paired": p.get("Paired", False),
                                "address": p.get("Address", "")})
        return {"available": bool(adapters), "powered": any(a.get("Powered") for a in adapters),
                "adapters": adapters,
                "devices": sorted(devices, key=lambda d: (not d["connected"], not d["paired"], d["name"]))}

    async def bt_connect(self, args):
        current = await self.bluetooth()
        device = next((d for d in current["devices"] if d["path"] == args.get("path")), None)
        if not device:
            raise ValueError("Gerät nicht mehr gefunden. Bitte erneut suchen.")
        path = device["path"]
        if not self.agent_registered:
            self.bus.export("/de/saarfighters/Agent", self.agent)
            await self.call(BLUEZ, "/org/bluez", BLUEZ + ".AgentManager1",
                            "RegisterAgent", "os", ["/de/saarfighters/Agent", "KeyboardDisplay"])
            self.agent_registered = True
        self.pairing_devices.add(path)
        try:
            if not device["paired"]:
                await self.call(BLUEZ, path, BLUEZ + ".Device1", "Pair", timeout=100)
            await self.call(BLUEZ, path, BLUEZ + ".Device1", "Connect", timeout=35)
            await self.set_prop(BLUEZ, path, BLUEZ + ".Device1", "Trusted", Variant("b", True))
            return {"message": "Bluetooth-Gerät verbunden."}
        except (TimeoutError, asyncio.CancelledError):
            try:
                await self.call(BLUEZ, path, BLUEZ + ".Device1", "CancelPairing")
            except DBusError:
                pass
            raise
        finally:
            self.pairing_devices.discard(path)
            self.agent.Cancel()

    async def power(self):
        devices = (await self.call(UP, UP_PATH, UP, "EnumerateDevices"))[0]
        battery = []
        chargers = []
        for path in devices:
            props = await self.props(UP, path, UP + ".Device")
            if props.get("Type") == 1:
                chargers.append(props.get("Online", False))
            if props.get("Type") == 2 and props.get("PowerSupply") and props.get("IsPresent"):
                battery.append(props)
        # UPower's display device aggregates multiple laptop batteries.
        if battery:
            display = (await self.call(UP, UP_PATH, UP, "GetDisplayDevice"))[0]
            aggregate = await self.props(UP, display, UP + ".Device")
            props = aggregate if aggregate.get("IsPresent") else battery[0]
            root = await self.props(UP, UP_PATH, UP)
            return {"percentage": props.get("Percentage"), "state": props.get("State"),
                    "plugged": any(chargers) if chargers else not root.get("OnBattery", True)}
        return {"percentage": None, "state": 0, "plugged": any(chargers) if chargers else None}

    async def pactl(self, *args):
        process = await asyncio.create_subprocess_exec("pactl", *args, stdout=asyncio.subprocess.PIPE,
                                                       stderr=asyncio.subprocess.PIPE,
                                                       env={**os.environ, "LC_ALL": "C"})
        try:
            out, _ = await asyncio.wait_for(process.communicate(), 8)
        except (TimeoutError, asyncio.CancelledError):
            # A request deadline or shutdown can cancel us before our own
            # timeout. Reap pactl in both cases so stalled helpers cannot pile up.
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.communicate()
            raise
        if process.returncode:
            raise ValueError("Audio ist gerade nicht verfügbar. Bitte die Boxen prüfen.")
        return out.decode()

    async def audio(self):
        return {**await self.audio_router.status(), "auto_bluetooth": self.auto_audio}

    async def status(self):
        values = await asyncio.gather(self.network(), self.bluetooth(), self.power(), return_exceptions=True)
        return {key: {"error": True} if isinstance(value, Exception) else value
                for key, value in zip(("network", "bluetooth", "power"), values)}

    async def perform(self, operation, args):
        if operation == "media_status":
            return await media_request()
        if operation == "status":
            return await self.status()
        if operation == "wifi":
            return await self.wifi(args.get("scan", False))
        if operation == "bluetooth":
            return await self.bluetooth()
        if operation == "pairing_reply":
            pending = self.agent.pending.get(args.get("token"))
            if pending and not pending.done():
                pending.set_result(args)
            return {}
        group = operation.split("_")[0]
        if group not in self.locks:
            raise ValueError("Diese Aktion ist nicht verfügbar.")
        async with self.locks[group]:
            if operation == "audio_autoswitch":
                enabled = args.get("enabled")
                if type(enabled) is not bool:
                    raise ValueError("Ungültiger Schalterzustand.")
                self.audio_preferences.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.audio_preferences.with_suffix(".tmp")
                temporary.write_text(json.dumps({"auto_bluetooth": enabled}))
                temporary.replace(self.audio_preferences)
                self.auto_audio = enabled
                return await self.audio()
            if operation == "audio_output_volume":
                return await self.audio_router.set_output_volume(args.get("name"), args.get("value"))
            if operation == "audio":
                return await self.audio()
            if operation == "brightness":
                return await brightness_request()
            if operation == "brightness_set":
                target = args.get("id")
                if not isinstance(target, str) or not target:
                    raise ValueError("Bitte einen Bildschirm auswählen.")
                return await brightness_request(target, args.get("value"))
            if operation in ("media_playpause", "media_previous", "media_next", "media_seek",
                             "media_volume", "media_shuffle", "media_repeat"):
                target = args.get("player")
                if not isinstance(target, str) or not target.startswith("org.mpris.MediaPlayer2."):
                    raise ValueError("Bitte zuerst Musik oder ein Video öffnen.")
                options = {key: args[key] for key in ("position", "track_id", "value") if key in args}
                return await media_request(target, operation.removeprefix("media_"), **options)
            if operation == "audio_toggle":
                await self.pactl("set-sink-mute", "@DEFAULT_SINK@", "toggle")
                return {}
            if operation == "wifi_connect":
                return await self.wifi_connect(args)
            if operation == "wifi_power":
                await self.set_prop(NM, NM_PATH, NM, "WirelessEnabled", Variant("b", bool(args["enabled"])))
            elif operation == "wifi_disconnect":
                for path, _ in await self.wireless_devices():
                    await self.call(NM, path, NM + ".Device", "Disconnect")
            elif operation in ("bt_scan", "bt_power"):
                info = await self.bluetooth()
                if not info["available"]:
                    raise ValueError("Kein Bluetooth-Adapter erkannt.")
                for adapter in info["adapters"]:
                    path = adapter["path"]
                    if operation == "bt_power":
                        await self.set_prop(BLUEZ, path, BLUEZ + ".Adapter1", "Powered", Variant("b", bool(args["enabled"])))
                        if not args["enabled"]:
                            self.discovery_owned.discard(path)
                    elif args.get("enabled") and adapter.get("Powered"):
                        if path not in self.discovery_owned:
                            await self.call(BLUEZ, path, BLUEZ + ".Adapter1", "StartDiscovery")
                            self.discovery_owned.add(path)
                    elif path in self.discovery_owned:
                        try:
                            await self.call(BLUEZ, path, BLUEZ + ".Adapter1", "StopDiscovery")
                        finally:
                            self.discovery_owned.discard(path)
            elif operation == "bt_connect":
                return await self.bt_connect(args)
            elif operation == "bt_disconnect":
                info = await self.bluetooth()
                if not any(d["path"] == args.get("path") for d in info["devices"]):
                    raise ValueError("Gerät nicht mehr gefunden.")
                await self.call(BLUEZ, args["path"], BLUEZ + ".Device1", "Disconnect")
            elif operation == "audio_volume":
                volume = max(0, min(100, int(args["value"])))
                await self.pactl("set-sink-volume", "@DEFAULT_SINK@", f"{volume}%")
            elif operation == "audio_mute":
                await self.pactl("set-sink-mute", "@DEFAULT_SINK@", "1" if args["muted"] else "0")
            elif operation in ("audio_output", "audio_outputs"):
                ids = [args.get("id")] if operation == "audio_output" else args.get("ids")
                return await AudioRouter(self.pactl).select(ids)
            else:
                raise ValueError("Diese Aktion ist nicht verfügbar.")
            return {"message": "Einstellung übernommen."}


async def serve():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    backend = Backend(bus)
    tasks = set()

    async def watch_audio():
        while True:
            try:
                async with backend.locks["audio"]:
                    await backend.audio_router.auto_bluetooth(backend.auto_audio)
            except Exception:
                print("Bluetooth-Audiowechsel derzeit nicht verfügbar.", file=sys.stderr, flush=True)
            await asyncio.sleep(3)

    watcher = asyncio.create_task(watch_audio())

    async def dispatch(request):
        try:
            # Pairing and Wi-Fi authentication have their own bounded waits.
            result = await asyncio.wait_for(backend.perform(request["op"], request.get("args", {})), 120)
            emit({"id": request["id"], "result": result})
        except Exception as exc:
            # Do not emit raw D-Bus exceptions, args or Wi-Fi passwords.
            emit({"id": request.get("id"), "error": friendly_error(exc, request.get("op", ""))})

    try:
        while line := await asyncio.to_thread(sys.stdin.readline):
            try:
                request = json.loads(line)
                if not isinstance(request, dict) or not isinstance(request.get("id"), int):
                    continue
            except (ValueError, TypeError):
                continue
            task = asyncio.create_task(dispatch(request))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        bus.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except Exception:
        # The UI handles worker loss; no traceback containing device data.
        sys.exit(1)
