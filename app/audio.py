"""Shared playback outputs using PulseAudio's PipeWire-compatible combine sink."""
import asyncio
import json
import re
import uuid


PREFIX = "saar_fighters_combined_"
MEMBERS = "saar_fighters.outputs"


def combined(sink):
    return sink["name"].startswith(PREFIX) and MEMBERS in sink.get("properties", {})


def output_info(sink, default):
    volumes = [float(v["value_percent"].strip("%")) for v in sink.get("volume", {}).values()]
    return {"id": str(sink["index"]), "name": sink["name"],
            "description": sink.get("description", sink["name"]),
            "default": sink["name"] == default, "mute": sink.get("mute", False),
            "volume": round(sum(volumes) / len(volumes)) if volumes else 0}


class AudioRouter:
    def __init__(self, pactl):
        self.pactl = pactl

    async def state(self):
        sinks = json.loads(await self.pactl("-f", "json", "list", "sinks"))
        default = (await self.pactl("get-default-sink")).strip()
        return sinks, default

    async def status(self):
        sinks, default = await self.state()
        active = next((s for s in sinks if s["name"] == default), None)
        selected = (active["properties"][MEMBERS].split(",") if active and combined(active)
                    else [default])
        outputs = [{**output_info(s, default), "selected": s["name"] in selected}
                   for s in sinks if not combined(s)]
        return {"outputs": outputs, "control": output_info(active, default) if active else None}

    async def select(self, ids):
        if (not isinstance(ids, list) or not ids or len(ids) > 64
                or any(not isinstance(value, str) or not value for value in ids)):
            raise ValueError("Bitte mindestens einen Audioausgang auswählen.")
        ids = list(dict.fromkeys(ids))
        sinks, default = await self.state()
        available = {str(s["index"]): s for s in sinks if not combined(s)}
        if any(value not in available for value in ids):
            raise ValueError("Ein ausgewählter Audioausgang ist nicht mehr verfügbar. Bitte erneut laden.")
        selected = [available[value] for value in ids]
        names = [s["name"] for s in selected]
        # Module arguments have their own parser even without a shell.
        if len(names) > 1 and any(not re.fullmatch(r"[A-Za-z0-9_.-]+", name) for name in names):
            raise ValueError("Diese Audioausgänge lassen sich nicht gemeinsam verwenden.")
        owned = [s for s in sinks if combined(s)]
        current = next((s for s in sinks if s["name"] == default), None)
        same = current and combined(current) and set(current["properties"][MEMBERS].split(",")) == set(names)
        target = default if same else names[0]
        streams = json.loads(await self.pactl("-f", "json", "list", "sink-inputs"))
        # Combine-sink forwarding streams must never be moved into themselves.
        modules = {str(s["owner_module"]) for s in owned if s.get("owner_module") is not None}
        streams = [s for s in streams if s.get("client") is not None
                   and str(s.get("owner_module")) not in modules]
        created = None
        moved = []
        unmuted = []
        previous_control = None
        default_changed = False
        try:
            if len(names) > 1 and not same:
                target = PREFIX + uuid.uuid4().hex
                created = (await self.pactl(
                    "load-module", "module-combine-sink", f"sink_name={target}",
                    "slaves=" + ",".join(names),
                    # pactl joins argv into a module-argument string, so preserve
                    # quotes around the property list for that second parser.
                    f'sink_properties="device.description=Saar-Fighters {MEMBERS}={",".join(names)}"')).strip()
                # Preserve the current master level and mute state when creating a group.
                if current:
                    control = output_info(current, default)
                    await self.pactl("set-sink-volume", target, f'{min(100, control["volume"])}%')
                    await self.pactl("set-sink-mute", target, "1" if control["mute"] else "0")
            if len(names) == 1 and current and combined(current):
                previous_control = output_info(selected[0], default)
                control = output_info(current, default)
                await self.pactl("set-sink-mute", target, "1" if control["mute"] else "0")
                await self.pactl("set-sink-volume", target, f'{min(100, control["volume"])}%')
            await self.pactl("set-default-sink", target)
            default_changed = True
            for stream in streams:
                try:
                    await self.pactl("move-sink-input", str(stream["index"]), target)
                    moved.append(stream)
                except ValueError:
                    remaining = json.loads(await self.pactl("-f", "json", "list", "sink-inputs"))
                    if any(s["index"] == stream["index"] for s in remaining):
                        raise
                    # An application may stop playback while the dialog applies.
            # Move apps first so a previously muted single output cannot briefly
            # play before its new muted group takes control.
            if len(names) > 1:
                for sink in selected:
                    if sink.get("mute"):
                        await self.pactl("set-sink-mute", sink["name"], "0")
                        unmuted.append(sink["name"])
        except (Exception, asyncio.CancelledError):
            # Keep the old group until the new route is fully established.
            if default_changed:
                await self.try_command("set-default-sink", default)
            for stream in moved:
                await self.try_command("move-sink-input", str(stream["index"]), str(stream["sink"]))
            for name in unmuted:
                await self.try_command("set-sink-mute", name, "1")
            if previous_control:
                await self.try_command("set-sink-mute", target, "1" if previous_control["mute"] else "0")
                await self.try_command("set-sink-volume", target, f'{previous_control["volume"]}%')
            if created:
                await self.try_command("unload-module", created)
            raise
        cleanup_failed = False
        for sink in owned:
            if sink["name"] != target and sink.get("owner_module") is not None:
                if not await self.try_command("unload-module", str(sink["owner_module"])):
                    cleanup_failed = True
        message = (f"{len(names)} Audioausgänge werden gemeinsam verwendet." if len(names) > 1
                   else "Audioausgang übernommen.")
        if cleanup_failed:
            message += " Eine alte Audiogruppe konnte noch nicht entfernt werden. Bitte erneut übernehmen."
        return {"message": message}

    async def try_command(self, *args):
        try:
            await self.pactl(*args)
            return True
        except Exception:
            return False
