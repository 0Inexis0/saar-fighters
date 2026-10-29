# Saar-Fighters OS

Eine einfache Vereinsoberfläche für **Saar-Fighters AS e.V.**, auf Arch Linux.
Große Schaltflächen statt eines vollgepackten Desktops. Matte Olive-, Khaki- und Erdtöne ohne Konturen oder Leuchteffekte;
der skalierbare Flecktarn-Hintergrund
ist Bestandteil des Projekts. Das Original-Logo stammt von der
[Vereinswebseite](https://www.saarfighters-as.de/) (siehe [Bildnachweis](assets.md)).

![Saar-Fighters Startseite in der Test-VM](desktop.png)

**Status: Installierbare Live-ISO 0.2.0 mit deutscher Oberfläche.**
Die normale Vereinsnutzung benötigt kein Terminal. Die Wartung der
Arch-Basis übernimmt eine zuständige Person.

## Auf dem Vereinslaptop installieren

Die ISO startet zunächst zum Ausprobieren. Der Knopf **„Auf diesem Rechner
installieren“** öffnet den eigenen deutschen Installer. Spotify und die
Vereinsoberfläche sind enthalten; die Installation funktioniert ohne Internet.
Das gewählte Ziellaufwerk wird vollständig gelöscht.

Benötigt werden ein x86_64-Rechner mit mindestens 4 GB RAM, ein Laufwerk ab
32 GB und ein USB-Stick ab 8 GB. Secure Boot ausschalten.
Siehe [Installationsanleitung](installation.md),
[ISO-Build](iso-build.md) und [ISO-Testprotokoll](iso-validation-0.2.0.md).
Die große ISO-Datei liegt außerhalb von Git im lokalen
Ordner `build/releases/0.2.0/`; dieses Repository enthält den Quellcode.

## Auf einem bereits installierten Arch einrichten

Im Terminal des vorgesehenen Vereinsrechners:

```bash
curl -fsSL https://raw.githubusercontent.com/0Inexis0/saar-fighters/main/system/setup-arch.sh | sudo bash
```

Benötigt installiertes Arch Linux x86_64, Internet, `curl` und sudo-Rechte.
Der Einzeiler fragt vor Änderungen nach `EINRICHTEN`, installiert die Pakete
inklusive Spotify und lässt dich ein eigenes Wartungspasswort setzen. Er
formatiert keine Laufwerke. SDDM, automatische Anmeldung als `saar`, deutsche
Systemsprache und NetworkManager werden für den nächsten Start eingerichtet.
Bestehende Benutzer und persönliche Dateien bleiben erhalten. Für ein normales
Arbeitsgerät diese Änderungen an Anmeldung und Netzwerk bewusst berücksichtigen.
Konfigurationssicherungen liegen unter `/var/lib/saar-setup-backups/`.
Vorhandene fremde Konten namens `saar`/`wartung` werden nicht übernommen.
Nach erfolgreicher Einrichtung selbst neu starten.

Für einen leeren Rechner stattdessen die ISO auf einen USB-Stick schreiben
und den grafischen Installer verwenden: [Installation](installation.md).

## Bedienung

- Die Kachel „Apps“ wechselt direkt auf eine Seite innerhalb des Dashboards.
  Sie nutzt die Dashboard-Fläche unter der dauerhaft sichtbaren Statusleiste
  ohne zusätzliches Fenster. Netzwerk, Bluetooth, Netzteil und Akku bleiben
  auch in der Apps-Ansicht sichtbar. Dort stehen genau
  die sechs ursprünglichen Verknüpfungen: Rocket Launch, Spotify, Internet,
  YouTube, Dateien und Vereinswebseite. Systemprogramme werden nicht ergänzt.
  Pro Seite passen sechs Kacheln; bei weiteren konfigurierten Verknüpfungen
  erscheinen Vor- und Zurück-Tasten. Die Suche gilt für alle Seiten.
  „Zurück zur Startseite“ oder Escape bringt die Startkacheln wieder zurück.

- Nach fünf Minuten ohne Eingabe startet auf dem Plasma-Wayland-Desktop eine
  bildschirmfüllende Airsoft-Diashow. Drei lokal gespeicherte Bilder wechseln
  alle zwölf Sekunden in zufälliger Reihenfolge, ohne direkte Wiederholung.
  Mausbewegung, Tastendruck oder Klick kehren zur bisherigen Anwendung zurück.
  Die Musik läuft weiter. Offene Einstellungs- und Bestätigungsdialoge werden
  nicht überdeckt. Die Diashow ist kein Sperrbildschirm.
  Die globale Erkennung verwendet `ext-idle-notify` von Wayland. Mit Version 2
  zählen reine Eingabepausen; bei Version 1 können Video-Apps den Start hemmen.
  In der Vorschau und unter X11 startet die Diashow nicht automatisch.

- Der Musikplayer rechts neben den Einstellungen zeigt Titel, Interpret,
  Player und Wiedergabestatus. Das Cover oder Video-Vorschaubild füllt die gesamte
  Kachel; Titel und Steuerung liegen auf einem dunklen Verlauf darüber. Ein Klick
  auf das Bild oder den Aufklappknopf öffnet den Player im Vollbild auf demselben
  Bildschirm. Die Steuerung in der kleinen Kachel bietet 56 Pixel große
  Vor-/Zurück-Tasten und eine 64 Pixel große Play-/Pause-Taste. „Einklappen“ oder
  Escape kehrt zurück, ohne die Wiedergabe zu unterbrechen.
  Der große Player zeigt Cover, Zeitleiste, Lautstärke, Zufallswiedergabe,
  Wiederholung und Lyrics. Play/Pause sowie vorheriger und nächster Titel
  steuern den angezeigten Medienplayer. Nicht unterstützte Aktionen sind deaktiviert.
  Laufende Wiedergabe hat Vorrang, bei Gleichstand Spotify. Ohne Player ist
  die Steuerung deaktiviert. Spotify und Browser mit MPRIS-Unterstützung werden erkannt.
  Spulen setzt eine gemeldete Titellänge und eine gültige Titelkennung voraus;
  ein Titelwechsel verwirft eine noch nicht abgesendete Positionsänderung.
  Die Lautstärke im großen Player steuert den angezeigten Player.
  Lyrics werden beim Öffnen zuerst aus den Metadaten gelesen, sonst über
  [LRCLIB](https://lrclib.net/docs) anhand von Titel, Interpret, Album und Laufzeit
  online gesucht. Diese Metadaten werden dabei an LRCLIB übermittelt. Zeitmarken
  heben die aktuelle Zeile hervor; ein Klick auf eine Zeile springt dorthin,
  sofern der Player Spulen unterstützt. Manuelles Scrollen pausiert das Folgen
  für acht Sekunden; „Aktuelle Zeile“ setzt es sofort fort. Ohne Zeitmarken wird
  der Text normal angezeigt. Ohne Treffer, Internet oder bei Instrumentalstücken
  erscheint ein Hinweis. Bei einem Ladefehler kann erneut geladen werden.
  Cover werden aus lokalen Dateien oder HTTP(S)-Adressen des Players geladen;
  fehlt ein Bild, erscheint ein Musiksymbol. Die Vorschau fragt keine Online-Lyrics ab.
- Stummschalten schaltet den aktuellen Audioausgang stumm; „Ton einschalten“
  hebt dies wieder auf. Der Status wird alle drei Sekunden aktualisiert.

- Spotify in der Apps-Übersicht: systemweit installierte Flatpak-App, sonst Spotify im Browser.
- Internet: Firefox.
- Rocket Launch: startet die mitgelieferte Airsoft-Spielkonsole in Firefox.
  Der lokale Python-Server startet bei Bedarf auf `127.0.0.1:18741`, ohne
  Terminal, Adminfreigabe, Node.js oder Internet. Ein belegter fremder Port
  wird als Fehler gemeldet; andere Prozesse werden nicht beendet.
  Ein zweites Spielfenster bleibt gesperrt, solange das erste geöffnet ist.
  Eine laufende Runde verhindert über ein lokales Lebenszeichen die Diashow.
  Nach einem verlorenen Lebenszeichen läuft dieser Schutz nach 90 Sekunden ab.
  Der Server bleibt für weitere Starts bis zum Sitzungsende verfügbar.
  „Spielleitung“ öffnet nach Eingabe eines Spielcodes die Einstellungen;
  das ist ein Bedienungsschutz, keine getrennte Administratoranmeldung.
  Die mitgelieferten Startwerte sind Startcode `8421`, Entschärfungscode `0000`,
  20 Sekunden Countdown und 50 Sekunden Flugzeit. Eigene Einstellungen unter
  `~/.config/saar-fighters/rocket-launch.json` überstehen OS-Updates.
  Die Countdown-Entschärfung benötigt zehn Sekunden und muss vor Ablauf fertig
  sein; die Flug-Entschärfung ist eine separat schaltbare sofortige Aktion.
  „Neue Runde / Abbrechen“ bricht eine aktive Runde erst nach Bestätigung ab.
  Neuladen und Schließen während der Runde lösen eine Browser-Rückfrage aus.
  Ein bestätigtes Neuladen oder ein Absturz setzt die Runde zurück.
  Spielregeln und Codes werden vor der nächsten Runde gespeichert; während
  einer Runde sind Änderungen gesperrt. Vollbild ist direkt oben erreichbar.
- YouTube: große Kachel, öffnet YouTube in Firefox.
- Dateien: Dolphin, unter anderem für Musik und USB-Sticks.
- Firefox (einschließlich YouTube und Vereinswebseite), Spotify und Dolphin
  starten maximiert. Die Taskleiste bleibt sichtbar; Dialoge behalten ihre
  normale Größe. Die Fenster lassen sich weiterhin verkleinern.
  Die Einrichtung greift beim Anmelden, auch nach Updates bestehender Rechner.
- Einstellungen: zentrale Kachel für WLAN, Bluetooth, Lautstärke, Bildschirm und Updates.
  Links bleibt die Seitenleiste sichtbar, rechts öffnet sich der gewählte Bereich
  direkt im selben Fenster. „Startseite“ führt zurück. Während Änderungen
  übernommen werden oder ein Update läuft, ist der Bereichswechsel gesperrt.
  WLAN auswählen und Passwort eingeben; Bluetooth suchen, koppeln und verbinden;
  Unter „Lautstärke & Boxen“ einen oder mehrere Audioausgänge ankreuzen und
  „Auswahl übernehmen“ drücken. Laufende Wiedergabe und neue Wiedergabe laufen
  dann über die ausgewählten Boxen gleichzeitig. Lautstärke und Stummschaltung
  steuern die aktive Auswahl gemeinsam, auch über die Stummtaste der Startseite.
  Für eine einzelne Box nur deren Häkchen stehen lassen und erneut übernehmen.
  „Erneut laden“ aktualisiert die Liste nach dem Verbinden weiterer Geräte.
  Die gemeinsame Ausgabe gilt für die aktuelle Audio-Sitzung; nach einem
  Neustart des Rechners oder Audiodienstes die Boxen erneut auswählen.
  Eigene Lautstärkeregler der Boxen bleiben wirksam. Je nach Verbindung,
  insbesondere bei Bluetooth, kann der Ton zeitlich versetzt ankommen.
  Unter „Bildschirm“ die Helligkeit von 0 bis 100 Prozent einstellen.
  Bei mehreren unterstützten Bildschirmen lässt sich jeder einzeln auswählen.
  Der Regler übernimmt Änderungen nach dem Loslassen, per Tastatur nach kurzer Pause.
  Die Steuerung verwendet KDE PowerDevil ohne Administratorfreigabe. Nicht
  unterstützte Bildschirme und Verbindungsfehler werden ausdrücklich angezeigt.
  „Erneut laden“ liest die aktuellen Werte ein, auch nach Änderungen über die
  Helligkeitstasten. Die Vorschau verändert nur Beispieldaten.
- Statusleiste: Netzwerkverbindung, verbundene Bluetooth-Geräte, Netzteil und
  Akku mit Prozentwert und Ladezustand. Fehlende Hardware und unbekannte Werte
  werden ausdrücklich angezeigt. Details erscheinen beim Darüberfahren.
- Vereinswebseite: große Kachel mit Vereinslogo zur offiziellen Seite.
- Oberfläche, Systemsprachumgebung, Qt-Dialoge und Firefox sind auf Deutsch
  eingestellt. Spotify übernimmt die deutsche Sprachumgebung.
- Updates: sichtbarer Fortschritt, Administratorfreigabe und ehrliche
  Erfolgs-/Fehlermeldung. Aktualisiert das komplette Arch-System und
  systemweit installierte Flatpaks sowie Oberfläche, Taskleiste, Designs und
  Hilfsskripte aus dem festen GitHub-Repository (`main`). Eigene Änderungen
  werden nach einem Neustart aktiv.
- Neustart und Ausschalten: erst nach Bestätigung; Abbrechen ist vorausgewählt.
- **Startseite** in der unteren Leiste bringt die Vereinsoberfläche wieder
  nach vorne. Laufende Apps bleiben über die Leiste erreichbar. Die Leiste
  verwendet den eigenen matten Plasma-Stil „Saar Olive“ mit Khaki-Akzenten.

Der Vereinsbenutzer `saar` meldet sich automatisch an und hat keine
sudo-Rechte. Das separate Konto `wartung` dient zur Administration.
Bei der ISO-Installation wird das Wartungspasswort selbst festgelegt.
Das zufällig erzeugte Passwort der ursprünglichen Entwicklungs-VM liegt
nur lokal in `build/vm/credentials.txt`, nicht im Repository.

## Architektur

Die Spieldateien liegen unter `app/rocket-launch/`; `app/rocket.py` stellt
sie und die validierte Konfiguration ausschließlich über Loopback bereit.
Die bestehenden Installer-, VM-, ISO- und Updatewege übernehmen diesen
App-Unterordner automatisch. Nach Änderungen am separaten Projekt
`airsoft rocket launch` dessen `index.html`, `js/`, `css/` und `assets/`
in den gebündelten Ordner übernehmen. Persönliche Konfiguration dabei nicht
als neue Vorgabe kopieren. Die veröffentlichte ISO 0.2.0 erhält Änderungen
erst durch ein veröffentlichtes Update oder einen neuen ISO-Build.

Die Oberfläche ist eine native Qt/PySide6-Anwendung. KDE Plasma/Wayland
übernimmt Fensterverwaltung, Audio, Netzwerk und Geräte. Ein angehefteter Taskleisten-Eintrag öffnet die Startseite. Ein Benutzerdienst startet sie beim
Anmelden und startet sie nach einem Absturz erneut. Ein lokaler Socket
verhindert doppelte Instanzen.

Alle Systemaktionen verwenden feste Programme und Argumentlisten. Nur
der Update-Helfer und im Live-System der feste Installationshelfer laufen
mit Adminrechten; die Oberfläche selbst bleibt
unprivilegiert. Ein eigener Python-Prozess spricht über D-Bus mit NetworkManager,
BlueZ und UPower; Audio läuft über PipeWire/PulseAudio. Er hält die Verbindung
für Bluetooth-Suche und Kopplungsabfragen offen. WLAN-Passwörter werden über
die Prozess-Eingabe und D-Bus weitergegeben, nicht als Kommandozeilenargument
oder Logeintrag. NetworkManager speichert das Verbindungsprofil für den
Vereinsbenutzer. Kopplungscodes müssen ausdrücklich bestätigt werden.
Während eines Updates blockiert ein systemd-Inhibitor
normales Herunterfahren und Suspend. Netzwerkprobleme, Paketkonflikte
und abgebrochene Freigaben werden als Fehler behandelt.

## Lokal ansehen

Benötigt Python, PySide6, QtSvg und dbus-next
(unter Arch: `pyside6 qt6-svg python-dbus-next`).
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

Das Entwicklungsskript `system/install.sh` richtet nur die Oberfläche in
der VM beziehungsweise im ISO-Build ein. Der getrennte Live-Installer unter
`installer/` partitioniert das ausdrücklich ausgewählte Laufwerk und richtet
ein bootfähiges System ein.

## Wartung und Grenzen

- Arch ist ein Rolling Release. Updates vor Vereinsterminen prüfen und ein
  aktuelles VM-/Datenträger-Backup bereithalten. Die Schaltfläche ersetzt
  weder Backups noch die Prüfung von Arch-Meldungen bei größeren Änderungen.
- Der Update-Knopf aktualisiert Pakete, Flatpaks und die eigene Oberfläche von
  dem öffentlichen Repository
  [`0Inexis0/saar-fighters`](https://github.com/0Inexis0/saar-fighters),
  Branch `main`. Auf dem Laptop sind kein Schlüssel und kein GitHub-Login nötig.
  Entwicklung, Tests, ISO-Bauwerkzeuge und Downloads liegen gemeinsam in diesem
  öffentlichen Repository. Änderungen auf `main` stehen direkt für Updates bereit.
  Vor dem Zusammenführen von Änderungen den Workflow „Check launcher“ prüfen.
  Der Download wird auf vollständige Dateien und Syntax geprüft; das allgemeine
  Installationsskript wird dabei nicht erneut ausgeführt. Die vorherige Oberfläche
  bleibt unter `/var/lib/saar-fighters-update/previous` erhalten. Schlägt der
  Dateiaustausch fehl, wird er zurückgerollt. System-/Flatpak-Updates werden dabei
  nicht zurückgerollt. Ein Stromausfall während des Austauschs erfordert eine
  Prüfung durch die Administration anhand von `recovery.json` im selben Ordner.
- Bestehende Installationen mit ISO 0.1.0 benötigen einmalig den neuen Update-Helfer;
  danach aktualisiert dieser auch sich selbst. Ab ISO 0.2.0 ist er enthalten.
  `python system/update_custom.py --check` lädt und prüft GitHub ohne Installation.
- Keine automatische Update- oder Neustartpflicht während der Musiknutzung.
- Das Vereinskonto ist eine Bedienungserleichterung, kein manipulationssicherer
  öffentlicher Kiosk. Über die gestarteten Apps ist normale Computernutzung möglich.
- Spotify muss einmal mit einem geeigneten Konto angemeldet werden.
  Zugangsdaten und Tokens gehören niemals ins Repository.
- VM-Tests ersetzen keine Prüfung des realen WLAN-/Bluetooth-Chips,
  der Boxen, der Akkulaufzeit oder der Leistung des Vereinslaptops.
- Im voreingestellten Vereinsprofil bleiben Bildschirm und Sitzung bei Inaktivität eingeschaltet,
  auch im Akku- und Niedrigakku-Profil. Automatisches Abdunkeln, Bildschirmabschalten,
  Sperren und Inaktivitäts-Suspend sind deaktiviert. Solange kein eigenes Energieprofil
  gewählt wurde, wird dies bei der Anmeldung übernommen. Manuelle Aktionen,
  Zuklappen und der Schutz bei kritisch leerem Akku bleiben unverändert.
- Der einfache WLAN-Dialog unterstützt sichtbare Netze mit WPA2/WPA3-Personal
  sowie offene/OWE-Netze. Versteckte Netze, Unternehmensanmeldung (802.1X) und
  Sonderkonfigurationen werden durch die Administration eingerichtet.
- Für Produktion: Hardwaretest, gewünschte Startprogramme,
  Datensicherung und Wiederherstellungsmedium vervollständigen.

## Quellen

- [Vereinswebseite und Original-Logo](https://www.saarfighters-as.de/)
- [Arch-Cloud-Images](https://wiki.archlinux.org/title/Arch_Linux_on_a_VPS)
- [Cloud-init](https://wiki.archlinux.org/title/Cloud-init)
- [KDE Plasma Scripting](https://develop.kde.org/docs/plasma/scripting/api/)
- [Spotify unter Linux](https://www.spotify.com/de/download/linux/)

Siehe [docs/validation.md](validation.md) für den tatsächlich geprüften Stand.

### Updates und Releases veröffentlichen

Es gibt nur ein Repository: [`0Inexis0/saar-fighters`](https://github.com/0Inexis0/saar-fighters).
Änderungen zuerst in einem Branch testen und erst nach erfolgreichem Workflow
„Check launcher“ nach `main` übernehmen. Die Vereinsrechner beziehen ihre
Updates direkt von `main`; ein Export-Repository und ein Deploy-Key sind nicht nötig.
ISO-Dateien weiterhin als Release-Anhänge veröffentlichen, nicht in Git einchecken.
`scripts/package-release.py` erstellt die ISO-Teile und Download-Helfer dafür.

Ältere Installationen und die ISO 0.2.0 enthalten noch die Adresse
`saar-fighters-updates`. Die GitHub-Weiterleitung auf `saar-fighters` bleibt
dafür erforderlich. Nach einem erfolgreichen Update nutzt der Helfer die neue
Adresse direkt. Das alte Repository unter diesem Namen nicht neu anlegen.


## Bildschirm, Energie, Systemübersicht und Meldungen

- Unter Bildschirm öffnet „Anzeige einrichten“ die KDE-Anzeigeverwaltung in einem
  eigenen Fenster. Dort lassen sich Auflösung, Skalierung, Drehung, Anordnung und
  Spiegelung angeschlossener Monitore einstellen. Die Helligkeit bleibt direkt
  in unserer Oberfläche erreichbar. Benötigt `kscreen` und `systemsettings`.
- Energie bietet Vereinsbetrieb, Laptopbetrieb und eigene Einstellungen.
  Laptopbetrieb dimmt nach zwei Minuten, schaltet den Bildschirm nach fünf Minuten
  aus und fordert nach 15 Minuten Standby an, am Netzteil und am Akku.
  Laufende Anwendungen können den Standby über die Energieverwaltung verhindern.
  Zuklappen, Einschalttasten und kritische Akkuschutzaktionen werden nicht verändert.
  Die Wahl liegt unter `~/.config/saar-fighters/energy.json`; nach der Wahl
  überschreibt die Anmeldung auch manuelle KDE-Anpassungen nicht mehr.
  „Weitere Energieeinstellungen“ öffnet KDE. Der Energiedienst wird nach einer
  Profilwahl neu geladen; bei Fehlern wird ausdrücklich auf die notwendige
  erneute Anmeldung hingewiesen. Das Profil ändert keine CPU-Leistungsmodi.
- Die Systemübersicht zeigt die installierte Oberflächenrevision, Kernel,
  Architektur, belegten RAM, freien Speicher auf dem Systemlaufwerk und den
  letzten erfolgreich abgeschlossenen Systemupdatezeitpunkt. Fehlende Werte
  werden als nicht verfügbar angezeigt. Aktualisierung alle zehn Sekunden.
- Die Glocke in der Kopfzeile öffnet „Mitteilungen“ als eigenes Fenster im
  Olive-Design mit einzelnen Meldungen, Zeitangaben und Gelesenstatus.
  „Schließen“ oder Escape führt zur vorherigen Ansicht zurück. Die lokale
  Historie enthält bis zu 100 Updateergebnisse, Energieprofil-Ergebnisse,
  Fehler bei der Statusabfrage, Warnungen bei höchstens 15 Prozent Akku ohne
  Netzteil sowie weniger als 2 GiB oder fünf Prozent freiem Systemspeicher.
  Speicher wird einmal pro Minute geprüft. Anhaltende Zustände erzeugen innerhalb
  einer Sitzung nur eine Meldung. Gelesenstatus und Verlauf bleiben erhalten;
  als gelesen markieren und Verlauf leeren sind separat möglich.
  Speicherung: `~/.local/state/saar-fighters/notifications.json`.
  Dies ist die Meldungszentrale unserer Oberfläche, kein Ersatz für die
  Benachrichtigungen fremder KDE-Anwendungen. Es erfolgt keine Online-Updateabfrage.
- Vorschauen verwenden Beispieldaten und ändern weder Geräte noch Profile oder
  gespeicherte Meldungen. Die erforderlichen KDE-Pakete sind im ISO-Paketplan,
  der Einrichtung und im Systemupdate berücksichtigt.

## Audio und Systemprotokolle (Bedienung)

- WLAN, Bluetooth, Ton und automatischer Bluetooth-Audiowechsel haben Ein/Aus-Schalter.
  Fernwartung verwendet weiterhin ihren bestätigten Schalter mit Administratorfreigabe.
- Unter Lautstärke hat jede erkannte Box einen eigenen Regler von 0 bis 100 Prozent.
  Die Häkchen wählen die gleichzeitig verwendeten Ausgänge. Die gemeinsame Lautstärke
  regelt den aktiven Ausgang beziehungsweise die Audiogruppe zusätzlich.
- Bei einem neu verfügbaren Bluetooth-Audioausgang wird innerhalb weniger Sekunden
  dorthin gewechselt, inklusive laufender Anwendungen. Lautstärke und Stummschaltung
  der bisherigen Ausgabe bleiben beim automatischen Wechsel erhalten. Die erste
  Geräteaufnahme nach dem Start bildet nur den Ausgangszustand. Eine anschließende
  manuelle Ausgangswahl bleibt bis zur nächsten Bluetooth-Neuverbindung bestehen.
  Der Schalter wird in `~/.config/saar-fighters/audio.json` gespeichert.
- Das kleine Musikwidget bietet eine direkte Ausgangsauswahl, die Ausgangslautstärke
  und einen Positionsregler mit Zeitangaben. Gemeinsame Boxengruppen werden angezeigt;
  eine einzelne Auswahl wechselt direkt auf diese Box. Gruppen werden in den Einstellungen
  zusammengestellt. Spulen ist nur bei entsprechender Player-Unterstützung aktiv.
  Ein Titelwechsel verwirft eine noch nicht übernommene Positionsänderung.
- Systemprotokolle zeigt bis zu 500 Journal-Einträge des aktuellen Starts, wahlweise
  Systemwarnungen oder die Benutzersitzung, sowie lokale Ereignisse der Vereinsprogramme.
  Es werden nur vorhandene Leserechte verwendet. Fehlende Zugriffsrechte werden angezeigt.
  „Als Text speichern“ exportiert ausschließlich die angezeigten Einträge an den gewählten Ort.
