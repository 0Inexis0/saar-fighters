# Stabilitätsprüfung vor dem Einsatz

## Codeprüfung am 30. Oktober 2026

Der betroffene Laptop ist ausgeschaltet. Die folgenden Änderungen sind im
Quellcode vorbereitet, noch nicht auf dem Laptop installiert oder dort geprüft.
Die aktuellen Browser-Verknüpfungen starten Brave; die älteren Firefox-Befunde
unten sind keine Prüfung von Brave und kein Nachweis einer behobenen Ursache.

| Fehler / Risiko | Änderung | Prüfung |
| --- | --- | --- |
| Dashboard und gestartete Anwendungen teilen die Lebensdauer von QProcess bzw. `saar-home.service`; dessen Beenden kann Anwendungen mit beenden. | Linux-Starts verwenden eigene systemd-Benutzerdienste. Qt wartet nur auf deren Ergebnis. Dienste enden mit der grafischen Sitzung. | Aufrufvertrag geprüft; Dienst-Neustartprobe auf dem Laptop noch offen. |
| Ein fehlgeschlagener QProcess-Start sendet kein `finished`; Prozessobjekte bleiben gespeichert und blockieren Rocket-Wiederholungen. | `FailedToStart` entfernt das Objekt und gibt den Start wieder frei. | Drei echte fehlgeschlagene Starts hintereinander. |
| Geräte- und Idle-Helfer sammeln ungelesenes stderr in Qt; Update- und Wartungsfenster behalten unbegrenzt Ausgabezeilen. | Ungenutztes stderr geht nach `/dev/null`; beide Textansichten behalten maximal 2.000 Blöcke. | Gerätehelfer mit 1,4 MB stderr; begrenzte Textansichten. |
| Abbruch einer Audioanfrage kann einen wartenden `pactl`-Prozess hinterlassen. Beim Worker-Ende werden abgebrochene Tasks nicht abgewartet. | Timeout und Cancellation beenden und leeren den Helfer; Shutdown wartet auf Tasks. | Echter schlafender Ersatzprozess nach Cancellation beendet; Prozessende-Rennen getestet. |
| Kontinuierlich langsam gelieferte Cover/Lyrics umgehen den Inaktivitäts-Timeout. | Zusätzliche absolute Frist von zehn Sekunden. | Lokaler HTTP-Server mit kontinuierlicher langsamer Antwort. |
| Sehr große LRC-Offsets lösen bei der Zahlumwandlung ValueError oder OverflowError aus. | Offset-Länge begrenzt; ungültige Offsets werden ignoriert. | Lyrics mit 400 und 5.000 Offset-Ziffern. |

Der neue App-Helfer verarbeitet stderr in begrenzten Blöcken und speichert nur
Fehlerkategorien und Prozesscodes. Ein Test mit großen Ausgaben prüft das ohne
Speicherung von URLs. Signalabbrüche werden als Fehler gemeldet. Es gibt keinen
automatischen Neustart von Browsern oder Spotify, der Abstürze verdecken würde.
Der Rocket-HTTP-Server erhält einen eigenen Sitzungsdienst, damit das Ende eines
Browser-Startbefehls ihn nicht beendet. Die App-Dienste benötigen systemd ab 254
(`--expand-environment=no`) und einen laufenden Benutzer-Manager, wie im
vorgesehenen Arch/Plasma-System. Ohne Manager wird ein Startfehler angezeigt;
es gibt keinen Rückfall auf einen mit dem Dashboard gekoppelten Start.

Die Isolation gilt für neu gestartete Prozesse. Bereits laufende Anwendungen
werden nicht verschoben. Nach Installation im regulären Wartungsfenster neu
anmelden. Anschließend neben den Wiedergabeprüfungen unten kontrollieren:

1. Brave, Spotify und Rocket über das Dashboard öffnen.
2. PIDs und Kontrollgruppen notieren, `saar-home.service` neu starten und prüfen,
   dass alle Apps, Tabs, Ton und der Rocket-Server weiterlaufen.
3. Browser schließen und erneut öffnen: Der Rocket-Server muss wiederverwendbar
   bleiben. Eine Abmeldung muss die zugehörigen Sitzungsdienste beenden.
4. Mehrstündige gemeinsame Nutzung mit echten Inhalten prüfen, dabei RAM/Swap,
   Kernel-/OOM-/GPU-Ereignisse, neue Coredumps und hörbare Aussetzer vergleichen.

Lokales Ergebnis: 268 Tests ausgeführt, davon 267 bestanden und ein KDE-Test
wegen fehlender KDE-Konfigurationsprogramme übersprungen. 14 Regressionstests
hinzugefügt. Die Offscreen-Startvorschau bei 1024 × 600, Shell-Syntaxprüfung und
`git diff --check` sind erfolgreich. Bereits im Ausgangsstand meldet der
D-Bus-Integrationstest ResourceWarnings über nicht geschlossene Sockets; die
Tests bestehen dennoch. Das ist kein bestandener Langzeittest der Sitzung.

Offen bleiben die ursprünglichen nativen Spotify-/Browser-Abstürze und mögliche
Hardwarefehler. Ohne laufenden Laptop, aktuelle Crashdaten und Praxistest ist
keine Freigabe als vollständig stabil möglich.

## Beobachtungen am 29. Oktober 2026

Der betroffene Laptop hat einen Intel i5-7200U, Intel HD Graphics 620 und rund
3,7 GiB nutzbaren RAM sowie 2 GiB Swap. Spotify wurde nach etwa 24 Sekunden mit
SIGABRT beendet; Firefox-Inhaltsprozesse zeigten wiederholt SIGSEGV. Beim zuletzt
beobachteten Tab-Absturz war kein OOM-Ereignis und kein GPU-Hänger protokolliert.
Die Ursache ist bislang nicht abschließend bestimmt.

- `pacman -Qkk firefox glibc mesa`: keine veränderten Programmdateien.
- OSTree-Prüfung: 22.302 Objekte geprüft, keine Fehler; ein partieller Commit
  wurde vom Werkzeug nicht verifiziert.
- Begrenzter Online-Speichertest: 32 Prozesse mit je 7 MiB gesperrtem RAM.
  Keine gemeldeten Speicherfehler. Nur 12 Prozesse beendeten beide Durchläufe
  innerhalb von 180 Sekunden, 20 wurden am Zeitlimit beendet. Kein vollständiger
  RAM-Test und kein Beleg für fehlerfreie Hardware.
- Firefox mit frischem Testprofil, ohne sichtbare Desktopausgabe: 120 Sekunden,
  118 JavaScript-Heartbeats, kein vorzeitiges Prozessende und keine Fehler im
  synthetischen Datenmuster. Das prüft weder das echte Nutzerprofil noch
  YouTube-Wiedergabe, Spotify-Audio oder stundenlangen Betrieb.

## Reversible Gegenproben

Das Update setzt die dokumentierte Firefox-Policy `HardwareAcceleration` auf
`false` und sichert die vorherige Policy als `policies.before-stability.json`.
Andere Policies, Profile, Lesezeichen und Anmeldungen bleiben erhalten. Die
Änderung gilt erst nach vollständigem Beenden und Neustarten von Firefox.
Softwaredarstellung kann die CPU-Auslastung erhöhen; Video und Rocket müssen im
realen Betrieb erneut geprüft werden. Eine bestandene Codeprüfung beweist diese
Wiedergabe nicht.

Der Dashboard-Start von Spotify verwendet `--disable-gpu` und
`--audio-api=pulseaudio`. Das nutzt den vorhandenen PipeWire-Pulse-Dienst.
Ein bestehender Spotify-Player wird über MPRIS wieder angezeigt. Ein zusätzlicher
Start-Lock verhindert konkurrierende Starts aus dem Dashboard. Ein bereits
laufender Player wird nicht beendet; neue Optionen gelten beim nächsten Start.
Starts außerhalb des Dashboards verwenden weiterhin ihre bisherigen Optionen.

Für eine Rücknahme: die gesicherte Policy nach Prüfung wiederherstellen und
`HardwareAcceleration` aus der aktuellen Policy entfernen; anschließend die
Stabilitätsmigration im Updater deaktivieren, damit das nächste Update sie nicht
erneut setzt. Spotify kann zum Vergleich direkt mit `flatpak run com.spotify.Client`
gestartet werden. Niemals die Sandbox oder Paket-Signaturprüfung abschalten.

## Nach dem Update prüfen

1. Browser und Spotify vollständig beenden und über das Dashboard neu öffnen.
2. Spotify-Musik und den tatsächlich benötigten Browserinhalt gleichzeitig laufen
   lassen. YouTube, Rocket und die Dashboard-Steuerung separat bedienen.
3. Über SSH den festen Diagnosebefehl ausführen. Er liefert jetzt zusätzlich den
   Wiedergabestatus und Positionsfortschritt ohne Titel, Kontodaten oder URLs.
4. Während eines mehrstündigen Praxistests Prozessabbrüche, Speicherverbrauch,
   Kernelmeldungen, hörbare Aussetzer und den Wiedergabefortschritt prüfen.

Die Dashboard-Protokolle enthalten nur App-Kategorie, Start/Ende, Exitcode und
vordefinierte Fehlerkategorien. Kein roher Programmausgabestrom wird gespeichert.
Die Protokolle sind auf eine aktive Datei und eine Vorgängerdatei begrenzt.

Bei weiteren Abstürzen ist der Test nicht bestanden. Dann insbesondere einen
vollständigen Offline-RAM-Test und eine kontrollierte Software-Gegenprobe
einplanen. Ein automatisch neu gestarteter Player zählt nicht als behobener Fehler.

Referenzen: [Mozilla HardwareAcceleration-Policy](https://firefox-admin-docs.mozilla.org/reference/policies/hardwareacceleration/)
und [Spotify-Flatpak Startoptionen und Audio-Backend](https://github.com/flathub/com.spotify.Client#pipewire-and-pulseaudio).
