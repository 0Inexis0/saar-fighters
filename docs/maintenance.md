# Fernwartung und Wiederherstellung

Die Einstellungen enthalten die Bereiche **Fernwartung** und **Wiederherstellen**.
Sie werden über das normale Systemupdate ausgeliefert. Nach dem Update die
Oberfläche durch einen Neustart neu laden. Bei Installationen mit dem alten
Updater ohne SSH-Erweiterung sind weiterhin einmalig zwei Update-Durchläufe nötig.

## Fernwartung

Die Seite fragt den Zustand von `saar-sshd.service` und die aktuellen lokalen
IPv4-Adressen ab. Sie zeigt den SSH-Aufruf für Port 2222 und das Konto `wartung`.
Ein aktiver Dienst bedeutet nicht, dass eine Verbindung von einem anderen Gerät
bereits getestet wurde. Beide Geräte benötigen ein gegenseitig erreichbares Netz.

Ein- und Ausschalten verlangt das Wartungspasswort. Das Ausschalten setzt
`/etc/saar-fighters/ssh/disabled` und stoppt sowie deaktiviert den Dienst.
Weitere Systemupdates respektieren die Auswahl. Bestehende SSH-Sitzungen können
weiterlaufen; neue Verbindungen werden nach dem Stoppen nicht mehr angenommen.
Beim Einschalten bleiben Schlüsselanmeldung und die bisherigen Netzgrenzen erhalten.

## LAN-Fernwartung und Update

Die Seite zeigt einen Ein/Aus-Schalter und bei aktivem SSH die lokale IP-Adresse.
Die Änderung wird erst nach erfolgreicher Passwortfreigabe und Statusabfrage
angezeigt. Die Fernwartung bleibt auf das gleiche WLAN oder LAN beschränkt.
Das Update stoppt und deinstalliert die zuvor eingeführte Tailscale-Komponente
und entfernt deren Netzbereich aus der SSH-Konfiguration. Ein bestehendes
SSH-Opt-out bleibt erhalten.

Fehlende OpenSSH-Pakete werden beim vollständigen Arch-Update installiert. Der neue Updater aktualisiert zuerst die Oberfläche und installiert die
Wartungswerkzeuge, bevor Paketupdates starten. Ein Signaturfehler löst genau einen
erneuten Download mit leerem temporärem Cache und `geo.mirror.pkgbuild.com` aus.
Signaturregeln und die dauerhafte Mirrorliste bleiben unverändert. Scheitert auch
dieser Versuch, wird das Update als fehlgeschlagen gemeldet.

**Migration bei blockiertem alten Updater:** Ein noch alter Updater kann weiterhin
vor dem GitHub-Schritt scheitern. Nach Veröffentlichung der neuen Version einmal
`sudo python /usr/local/libexec/saar-update-custom.py` ausführen. Beim ersten Lauf
ersetzt der alte Helfer nur die Dateien. Danach das Dashboard-Systemupdate starten;
nun läuft die neue Reihenfolge einschließlich der Wartungseinrichtung.

## Oberfläche wiederherstellen

Vor einem Oberflächenupdate wird der vorherige Projektstand unter
`/var/lib/saar-fighters-update/previous` gesichert. Neue Sicherungen enthalten
Dateiprüfsummen. Die Seite zeigt aktuelle und gesicherte Version und bietet eine
Wiederherstellung nur bei einer lesbaren, strukturell gültigen Sicherung an.
Ältere Sicherungen ohne Prüfsummen werden zusätzlich anhand von Syntax und
lokalen Python-Modulen geprüft. Das beweist nicht, dass diese Version auf dem
konkreten Laptop störungsfrei gelaufen ist.

Nach ausdrücklicher Bestätigung und Wartungspasswort werden App, Taskleiste,
Design und zugehörige Darstellungshelfer zurückgesetzt. Die Sicherungskennung
wird erneut geprüft, damit ein zwischenzeitliches Update nicht unbemerkt eine
andere Sicherung auswählt. Ein gemeinsames Schloss verhindert parallele Updates
und Wartungsänderungen; der Vorgang blockiert normales Einschlafen und Herunterfahren.

Persönliche Dateien, Browserprofile, Spotify-Anmeldung, Systempakete, SSH,
Wartungswerkzeuge und der aktuelle Updater werden nicht zurückgesetzt.
Anschließend den Rechner neu starten. Ein später ausdrücklich gestartetes
Systemupdate installiert wieder den neuesten Stand, auch wenn dessen
Updater-Versionsnummer unverändert ist.

Schlägt ein Dateiaustausch fehl, werden bereits ersetzte Dateien zurückgenommen.
Bei einem Stromausfall oder einer fehlgeschlagenen Rücknahme bleibt eine
Wartungsmarkierung bestehen. Weitere Änderungen werden dann blockiert, bis
die Administration den Zustand geprüft hat.

## Wenn die Startseite nicht mehr startet

Der separate Eintrag **Saar-Fighters Wartung** wird außerhalb der Oberfläche
installiert und bei einer Wiederherstellung beibehalten. Er lässt sich über die
KDE-Anwendungssuche öffnen, üblicherweise mit `Alt` + `Leertaste` und der Suche
nach „Saar-Fighters Wartung“. Die Bedienung entspricht den Einstellungsseiten.
Das ersetzt keine Wiederherstellung eines nicht mehr startenden Linux-Systems.

## Umsetzung und Prüfung

- Öffentlicher Status unter `/var/lib/saar-fighters/surface-status.json` enthält
  nur Versions- und Sicherungsinformationen; der Sicherungsordner bleibt geschützt.
- Polkit erlaubt Änderungen nur nach Administratorfreigabe über den festen
  Helfer `/usr/local/libexec/saar-maintenance` mit begrenzten Aktionen.
- Der vorhandene SSH-Einrichtungsschritt installiert die neuen Wartungswerkzeuge
  auch beim ersten Update einer Installation mit dem bisherigen SSH-Updater.
- Tests prüfen Wiederherstellung, Rücknahme bei Dateifehlern, geänderte Sicherungen,
  fehlende Module und Prüfsummen, Nutzerdatenerhalt, SSH-Opt-out und UI-Bediensperren.
