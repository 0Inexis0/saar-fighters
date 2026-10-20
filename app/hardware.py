"""Pure presentation/validation rules, shared by the UI and device worker."""


def security_mode(flags, wpa, rsn):
    modes = wpa | rsn
    if modes & 0x100:
        return "wpa-psk"
    if modes & 0x400:
        return "sae"
    if modes & 0x200:
        return "enterprise"
    if modes & (0x800 | 0x1000):
        return "owe"
    return "unsupported" if flags & 1 else "open"


def status_labels(status):
    net = status.get("network", {})
    bt = status.get("bluetooth", {})
    power = status.get("power", {})
    if net.get("error"):
        network = "Netzwerk: unbekannt"
    elif net.get("state", 0) >= 50:
        network = ("WLAN verbunden" if net.get("type") == "802-11-wireless"
                   else "Kabel verbunden" if net.get("type") == "802-3-ethernet"
                   else "Netzwerk verbunden")
    elif net.get("state") == 40:
        network = "Netzwerk verbindet …"
    else:
        network = "Nicht verbunden"
    if bt.get("error"):
        bluetooth = "Bluetooth: unbekannt"
    elif not bt.get("available"):
        bluetooth = "Bluetooth: kein Adapter"
    elif not bt.get("powered"):
        bluetooth = "Bluetooth aus"
    else:
        count = sum(bool(d.get("connected")) for d in bt.get("devices", []))
        bluetooth = f"Bluetooth: {count} verbunden" if count else "Bluetooth: nicht verbunden"
    if power.get("error"):
        charger, battery = "Netzteil: unbekannt", "Akku: unbekannt"
    else:
        plugged = power.get("plugged")
        charger = ("Netzteil verbunden" if plugged is True else
                   "Netzteil getrennt" if plugged is False else "Netzteil: unbekannt")
        pct = power.get("percentage")
        if pct is None:
            battery = "Kein Akku erkannt"
        else:
            state = {1: "lädt", 2: "entlädt", 4: "voll", 5: "Laden pausiert",
                     6: "Entladen pausiert"}.get(power.get("state"), "")
            battery = f"Akku {round(pct)} %" + (f" · {state}" if state else "")
    return network, bluetooth, charger, battery


def wifi_password_valid(mode, password):
    if mode == "wpa-psk":
        return 8 <= len(password) <= 63 or (
            len(password) == 64 and all(c in "0123456789abcdefABCDEF" for c in password))
    if mode == "sae":
        return 1 <= len(password) <= 63
    return mode in ("open", "owe")


def friendly_error(error, operation=""):
    name = getattr(error, "type", "")
    if isinstance(error, TimeoutError):
        return "Das hat zu lange gedauert. Bitte das Gerät prüfen und erneut versuchen."
    if "Authentication" in name or "Secrets" in name:
        return "Anmeldung fehlgeschlagen. Bitte Passwort oder Kopplungscode prüfen."
    if any(word in name for word in ("NotAuthorized", "AccessDenied", "PermissionDenied")):
        return "Die Freigabe fehlt. Bitte die Vereinsadministration fragen."
    if "NotReady" in name:
        return "Der Funkadapter ist nicht bereit. Bitte einschalten und erneut versuchen."
    if "Canceled" in name or "Rejected" in name:
        return "Die Verbindung wurde abgebrochen."
    if "NotAvailable" in name or "UnknownObject" in name:
        return "Das Gerät ist nicht mehr erreichbar. Bitte erneut suchen."
    if isinstance(error, ValueError):
        return str(error)
    return "Das hat nicht geklappt. Bitte Verbindung und Gerät prüfen und erneut versuchen."
