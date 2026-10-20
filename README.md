# Saar-Fighters OS

Eine einfache Vereinsoberfläche für **Saar-Fighters AV**, auf Arch Linux.
Große Schaltflächen statt eines vollgepackten Desktops. Dunkles Waldgrün,
Salbeigrün und warme Orange-Akzente; der skalierbare Gelände-Hintergrund
ist Bestandteil des Projekts. Die Wortmarke ist ein Platzhalter für das
offizielle Vereinslogo.

![Saar-Fighters Startseite in der Test-VM](docs/desktop.png)

**Status: VM-Prototyp, noch kein Installationsmedium für den Vereinslaptop.**
Die normale Vereinsnutzung benötigt kein Terminal. Die Wartung der
Arch-Basis übernimmt eine zuständige Person.

## Bedienung

- Spotify: native Flatpak-App, wenn installiert; sonst Spotify im Browser.
- Internet: Firefox.
- Dateien: Dolphin, unter anderem für Musik und USB-Sticks.
- WLAN, Lautstärke und Bluetooth: die passenden KDE-Einstellungen.
- Updates: sichtbarer Fortschritt, Administratorfreigabe und ehrliche
  Erfolgs-/Fehlermeldung. Aktualisiert das komplette Arch-System und
  systemweit installierte Flatpaks.
- Neustart und Ausschalten: erst nach Bestätigung; Abbrechen ist vorausgewählt.
- **Startseite** in der oberen Leiste bringt die Vereinsoberfläche wieder
  nach vorne. Laufende Apps bleiben über die Leiste erreichbar.

Der Vereinsbenutzer `saar` meldet sich automatisch an und hat keine
sudo-Rechte. Das separate Konto `wartung` dient zur Administration.
Sein zufällig erzeugtes VM-Passwort liegt nur lokal in
`build/vm/credentials.txt`, nicht im Repository.

## Architektur

Die Oberfläche ist eine native Qt/PySide6-Anwendung. KDE Plasma/Wayland
übernimmt Fensterverwaltung, Audio, Netzwerk und Geräte. Ein kleines
Plasma-Widget öffnet die Startseite. Ein Benutzerdienst startet sie beim
Anmelden und startet sie nach einem Absturz erneut. Ein lokaler Socket
verhindert doppelte Instanzen.

Alle Systemaktionen verwenden feste Programme und Argumentlisten. Nur
der Update-Helfer läuft mit Adminrechten; die Oberfläche selbst bleibt
unprivilegiert. Während eines Updates blockiert ein systemd-Inhibitor
normales Herunterfahren und Suspend. Netzwerkprobleme, Paketkonflikte
und abgebrochene Freigaben werden als Fehler behandelt.

## Lokal ansehen

Benötigt Python, PySide6 und QtSvg (unter Arch: `pyside6 qt6-svg`).
Die Vorschau verändert keine Systemeinstellungen und öffnet keine Apps.

```bash
python app/main.py --preview
QT_QPA_PLATFORM=offscreen python app/main.py --screenshot build/home.png --size 1280x800
python -m unittest discover -s tests -v
```

## Eine neue Test-VM erstellen

Host: KVM/QEMU, libvirt im Benutzermodus, GNOME Boxes, `genisoimage`,
Python/PyYAML und OpenSSL. Eine offizielle Arch-Cloud-QCOW2-Datei und
deren unabhängig geprüfte SHA256-Prüfsumme bereitstellen.

```bash
python scripts/create-vm.py --base /pfad/Arch-Linux-cloudimg.qcow2 --sha256 PRUEFSUMME
virsh -c qemu:///session define build/vm/domain.xml
virsh -c qemu:///session start saar-fighters-os
```

Die VM hat 4 vCPUs, 4 GiB RAM, eine 40-GiB-Sparse-Disk und VirtIO-Grafik.
3D-Beschleunigung ist zunächst ausgeschaltet. Vorhandene VMs werden
nicht verändert. Der Ersteller verweigert das Überschreiben einer
vorhandenen Entwicklungs-VM.

Cloud-init installiert die Basis. Bei fehlendem NTP kann die erste
Initialisierung kurz auf Zeitsynchronisation warten. Spätere Starts
warten nicht auf NTP; der Zeitdienst bleibt im Hintergrund aktiv. Die Host-Zeit lässt sich
über den Gast-Agenten übernehmen:

```bash
virsh -c qemu:///session qemu-agent-command saar-fighters-os '{"execute":"guest-set-time"}'
python scripts/guest.py 'tail -n 10 /var/log/saar-bootstrap.log'
```

Nach `SAAR_BASE_READY`:

```bash
python scripts/deploy-vm.py
python scripts/guest.py 'flatpak install --system --noninteractive flathub com.spotify.Client'
python scripts/guest.py 'systemctl reboot'
```

In Boxen **Saar-Fighters OS** öffnen. Wenn Boxen geschlossen wird, kann
die VM gespeichert/pausiert werden. Zum Fortsetzen wieder öffnen.

## Änderungen ausrollen

```bash
python scripts/deploy-vm.py
python scripts/guest.py 'runuser -u saar -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user daemon-reload; runuser -u saar -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user restart saar-home'
```

Das Plasma-Layout wird beim ersten Login einmalig erstellt. Für eine
bewusste erneute Anwendung den Marker
`/home/saar/.local/state/saar-layout-v1` entfernen und neu anmelden.

Der Installer ist absichtlich auf VMs beschränkt. Er schreibt ausschließlich
in den Gast; er partitioniert keine Festplatten. Eine spätere Installation
auf dem Vereinslaptop benötigt einen eigenen, geprüften Ablauf.

## Wartung und Grenzen

- Arch ist ein Rolling Release. Updates vor Vereinsterminen prüfen und ein
  aktuelles VM-/Datenträger-Backup bereithalten. Die Schaltfläche ersetzt
  weder Backups noch die Prüfung von Arch-Meldungen bei größeren Änderungen.
- Der Update-Knopf aktualisiert Pakete und Flatpaks. Änderungen an dieser
  eigenen Oberfläche werden derzeit mit dem Deployment-Skript ausgerollt.
- Keine automatische Update- oder Neustartpflicht während der Musiknutzung.
- Das Vereinskonto ist eine Bedienungserleichterung, kein manipulationssicherer
  öffentlicher Kiosk. Über die gestarteten Apps ist normale Computernutzung möglich.
- Spotify muss einmal mit einem geeigneten Konto angemeldet werden.
  Zugangsdaten und Tokens gehören niemals ins Repository.
- VM-Tests ersetzen keine Prüfung des realen WLAN-/Bluetooth-Chips,
  der Boxen, der Akkulaufzeit oder der Leistung des Vereinslaptops.
- Akku-Energiesparen bleibt dem KDE-Standard überlassen. Im Netzbetrieb ist
  automatischer Suspend für das Vereinsprofil deaktiviert.
- Für Produktion: Hardwaretest, Logo, gewünschte Startprogramme,
  Datensicherung und Wiederherstellungsmedium vervollständigen.

## Quellen

- [Arch-Cloud-Images](https://wiki.archlinux.org/title/Arch_Linux_on_a_VPS)
- [Cloud-init](https://wiki.archlinux.org/title/Cloud-init)
- [KDE Plasma Scripting](https://develop.kde.org/docs/plasma/scripting/api/)
- [Spotify unter Linux](https://www.spotify.com/de/download/linux/)

Siehe [docs/validation.md](docs/validation.md) für den tatsächlich geprüften Stand.
