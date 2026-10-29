# Stabilitätsprüfung vor dem Einsatz

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
