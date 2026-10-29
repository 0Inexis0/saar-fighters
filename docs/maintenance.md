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

## Zugriff über das Internet

Das Update installiert OpenSSH und Tailscale. Unter **Fernwartung** auf
**Internet verbinden** klicken, das Wartungspasswort eingeben und anschließend
**Tailscale-Anmeldung öffnen** wählen. Die Anmeldung erfolgt im Browser des
normalen Desktopbenutzers. Ein eigenes Tailscale-Konto und gegebenenfalls die
Gerätefreigabe in dessen Verwaltung sind erforderlich. Auch der Wartungsrechner
muss mit diesem Tailscale-Netz verbunden sein. Eine Repo-Aktualisierung kann diese
persönliche Anmeldung nicht ersetzen.

Die Seite zeigt die eigene Tailscale-IPv4-Adresse und den SSH-Aufruf auf Port 2222.
Der Dienst akzeptiert zusätzlich `100.64.0.0/10`, weiterhin ausschließlich als
`wartung` mit dem hinterlegten Schlüssel. Tailscale-Zugriffsregeln müssen Port 2222
zwischen den beiden Geräten erlauben. Tailscale SSH auf Port 22 wird nicht aktiviert.
Routerfreigaben werden nicht eingerichtet. **Internet trennen** führt `tailscale down`
aus und trennt alle Tailscale-Verbindungen dieses Geräts; LAN-SSH bleibt separat
schaltbar. **Fernwartung ausschalten** stoppt den SSH-Dienst für beide Zugangswege.
Tailscale wird erst durch den ausdrücklichen Verbindungsklick gestartet und für
weitere Neustarts aktiviert. Ein bloßes Update meldet kein Gerät bei Tailscale an.

Fehlen Pakete, bietet die Seite deren Installation mit vollständigem Arch-Update
an. Der neue Updater aktualisiert zuerst die Oberfläche und installiert die
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
