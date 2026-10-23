# Saar-Fighters OS 0.2.0 – Prüfung am 23. Oktober 2026

## Artefakt

- Datei: `saar-fighters-os-0.2.0-2026.10.23-x86_64.iso`
- Größe: 3.202.646.016 Bytes (2,98 GiB).
- SHA256: `87e5d78d83881b3e15abd5663bbbc9e1c645419ee77f1fff72d339403584b911`
- Lokal: `build/releases/0.2.0/`, mit `SHA256SUMS` und Paketlisten.
- Gebaut mit Archiso 91-1 in `saar-iso-builder`, ohne Host-Laufwerke zu verändern.
- Enthält die Olive-/Flecktarn-Oberfläche, Fluent-Icons, Taskleiste unten mit
  einem Startseiten-Eintrag, öffentlichen Updater und Spotify samt Offline-Runtime.
- Spotify: `1.2.95.453.g0eeebbed`, Freedesktop-Runtime: `25.08.19`.
- Prüfsumme nach Übertragung von der Build-VM auf den Host identisch.

## Einzeiler für installiertes Arch

Der veröffentlichte Einzeiler wurde in `saar-arch-setup-test` tatsächlich
heruntergeladen und ausgeführt. Die VM war eine separate Kopie einer
installierten Arch-Basis mit vorhandenen Desktop-Paketen. Vorher wurden nur in
dieser Kopie die alte Vereinsinstallation und ihre Benutzer entfernt und ein
fremder Testbenutzer mit einer Kontroll-Datei eingerichtet.

- Die Eingabe `EINRICHTEN` wurde bestätigt und ein neues, nur für den Test
  verwendetes Wartungspasswort über die interaktive Passwortabfrage gesetzt.
- Paketaktualisierung, Benutzeranlage, Desktop-Konfiguration und Spotify
  erfolgreich; Prozess endet mit Status 0.
- Nach Neustart automatische Anmeldung und aktuelle Vereinsoberfläche.
- Die Kontroll-Datei des vorhandenen Benutzers blieb unverändert.
- Tatsächliche sudo-Authentifizierung als `wartung` erfolgreich.
- Öffentlicher Update-Abruf mit `--check` ohne GitHub-Zugang erfolgreich.
- Konfigurationssicherung unter `/var/lib/saar-setup-backups/` angelegt.

## ISO-Installation

Neue VMs `saar-020-uefi` und `saar-020-bios` mit getrennten leeren 40-GiB-
Ziellaufwerken und je einem zweiten Laufwerk mit Kontrollmuster. Netzwerk
während Installation und erstem Start getrennt. Die bisherigen Test-VMs und
deren Laufwerke wurden nicht überschrieben.

Der echte Qt-Installer wurde über seine Bedienelemente automatisiert: keine
Laufwerksvorauswahl, gezielte Auswahl von `SAAR_INSTALL_TARGET`, zweimalige
Passworteingabe, Lösch-Checkbox und separate destruktive Bestätigung.
Das Paketkopieren, Partitionieren und Bootloader-Einrichten erfolgte durch den
unveränderten privilegierten Installer. Anschließend wurde die ISO ausgeworfen
und das installierte System gestartet.

Die Abschlussprüfung erfolgt mit `scripts/check-installed.py`: Dateisystem,
Firmware, entfernte Live-Freigaben, Autologin, deutsche Sprache, Spotify,
öffentlicher Updater, Git, moderne Icons, Benutzerrechte und echtes
Wartungspasswort. Die UID des Vereinsbenutzers wird dynamisch ermittelt.

## Ergebnisse

- BIOS: ohne ISO vom installierten Laufwerk gestartet, **20/20 Checks bestanden**.
- UEFI: ohne ISO vom installierten Laufwerk gestartet, **20/20 Checks bestanden**.
- Beide Kontrolllaufwerke: `qemu-img compare` meldet „Images are identical“.
- UEFI-Installer: Abschlussstatus `done=true`, Fortschritt 100 Prozent.
- 53 Python-/Qt-Tests bestanden; Shell-Syntax und `git diff --check` fehlerfrei.
- Der Einzeiler wurde aus dem öffentlichen Update-Repository ohne Zugangsdaten
  geladen. Getesteter Entwicklungsstand: `c9bf204`.

![Installierte Oberfläche von ISO 0.2.0](desktop.png)

## Grenzen

Die Tests ersetzen keinen Start von einem physischen USB-Stick und keinen Test
von WLAN, Bluetooth, Grafik und Audio auf dem Vereinslaptop. Secure Boot muss
ausgeschaltet sein. Der ISO-Installer löscht ausschließlich das ausdrücklich
bestätigte Ziellaufwerk vollständig; Dual-Boot und Verschlüsselung sind nicht
enthalten. Der Arch-Einzeiler formatiert keine Laufwerke, verändert aber bewusst
Anmeldemanager, Systemsprachumgebung und Netzwerkverwaltung.
