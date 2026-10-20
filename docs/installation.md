# Vom USB-Stick installieren

Die ISO ist für PCs und Laptops mit **x86_64-Prozessor**, mindestens **4 GB RAM**
und einem **Laufwerk ab 32 GB** vorgesehen. Ein USB-Stick ab 8 GB wird empfohlen.
UEFI und älteres BIOS werden unterstützt. Secure Boot muss ausgeschaltet sein.
Die Installation ersetzt das gewählte Laufwerk vollständig; Dual-Boot,
Verschlüsselung und die Übernahme bestehender Benutzerdaten sind nicht enthalten.

## Vorbereiten und ausprobieren

1. Die Saar-Fighters-ISO und `SHA256SUMS` aus demselben Build verwenden.
   Die Prüfsumme lässt sich unter Linux mit `sha256sum -c SHA256SUMS` vergleichen.
2. Die ISO als **Datenträgerabbild** auf den USB-Stick schreiben. Einfaches
   Kopieren der ISO-Datei auf einen gewöhnlichen Stick reicht nicht.
   Das Schreiben des Abbilds löscht den Inhalt dieses USB-Sticks.
3. Den Vereinslaptop über sein Bootmenü vom USB-Stick starten.
4. Die Vereinsoberfläche startet auf Deutsch. WLAN, Bluetooth und Audio lassen
   sich ausprobieren, bevor etwas installiert wird. Spotify benötigt zum
   Anmelden und Streamen weiterhin eine Internetverbindung.

## Installieren

1. Persönliche Daten des Ziellaufwerks vorher sichern und das Netzteil anschließen.
2. Oben **„Auf diesem Rechner installieren“** anklicken.
3. Das Ziellaufwerk anhand von Größe, Gerätename und gegebenenfalls Seriennummer
   auswählen. Der gestartete USB-Stick und bereits verwendete Laufwerke sind
   von der Auswahl ausgeschlossen. Bei Bedarf Laufwerke neu suchen.
4. Ein eigenes Passwort für das Konto **`wartung`** eingeben und wiederholen.
   Es wird für Updates und Administration benötigt. Es gibt kein gemeinsames
   Standardpasswort.
5. Das Löschen bestätigen und die zweite Abfrage mit den Laufwerksdaten prüfen.
   Erst **„Laufwerk löschen und installieren“** startet die Neuinstallation.
6. Nach der Erfolgsmeldung neu starten und den USB-Stick entfernen.

Die eigentliche Installation benötigt kein Internet. Sie übernimmt die
unveränderten Systemdateien vom ISO-Abbild, einschließlich Spotify und seiner
Laufzeitumgebung. Konten, Passwörter, WLAN-Verbindungen oder Spotify-Anmeldungen,
die während des Ausprobierens im Live-System verwendet wurden, werden **nicht**
übernommen. WLAN und Spotify nach der Installation erneut anmelden.

## Was auf dem Laufwerk eingerichtet wird

- GPT-Partitionstabelle mit BIOS-Startbereich, 512 MiB EFI-Partition und ext4-Systempartition.
- GRUB für BIOS und UEFI; UEFI verwendet den portablen Standard-Bootpfad.
- 2 GiB Auslagerungsdatei; kein eingerichteter Ruhezustand.
- Benutzer `saar` mit automatischer Anmeldung und ohne Administratorrechte.
- Separates Wartungskonto mit dem selbst gewählten Passwort.
- Deutsche Sprache, deutsche Tastatur und Zeitzone Europe/Berlin.
- Live-Installerfreigabe wird entfernt; Updates verlangen das Wartungspasswort.

Während der Installation wird normales Herunterfahren und Einschlafen blockiert.
Der Dialog lässt sich dann nicht schließen. Bei einem Fehler wird kein Erfolg
angezeigt; erneut vom USB-Stick starten. Eine begonnene Installation kann das
Ziellaufwerk bereits gelöscht haben. Technische Diagnose liegt im Live-System
unter `/run/saar-install.log` und enthält keine Passworteingaben.

Der konkrete WLAN-/Bluetooth-Chip, Grafik und Energiesparen des Vereinslaptops
müssen weiterhin an diesem Gerät geprüft werden.
