# Saar-Fighters OS 0.2.0 mit Ventoy

Bei `EFI stub: Failed to decompress kernel` trotz korrekter ISO-Prüfsumme:

1. Den Ordner `ventoy` aus dem Kompatibilitätspaket auf die große Ventoy-Partition kopieren.
2. Die ISO `saar-fighters-os-0.2.0-2026.10.23-x86_64.iso` liegt im Hauptverzeichnis des Sticks.
3. Stick sicher auswerfen, am Zielrechner starten und die ISO wie gewohnt auswählen.

**Vorhandene Konfiguration:** Eine vorhandene `ventoy/ventoy.json` nicht überschreiben.
Stattdessen den Eintrag aus `custom_boot` ergänzen und `saar-fighters.vcfg` daneben kopieren.
Bei anderem ISO-Namen oder Unterordner den `file`-Pfad in `ventoy.json` entsprechend anpassen.
Zum Rückgängigmachen nur diesen `custom_boot`-Eintrag entfernen.

Ventoy lädt Kernel und Initramfs direkt mit GRUB. Archisos vorhandener Loop-Mount-Hook
öffnet anschließend die ISO auf der anhand ihrer UUID gefundenen USB-Partition.
Die ISO selbst bleibt unverändert. Secure Boot muss ausgeschaltet sein.

Geprüft am 24.10.2026 mit Ventoy 1.1.17, QEMU/OVMF UEFI, USB-Massenspeicher und
Saar-Fighters 0.2.0: normale ISO-Auswahl erreicht den Live-Desktop über den direkten
Startweg. Die Testpartition war FAT32; der physische Stick verwendet exFAT, dessen
Treiber im ISO-Initramfs enthalten ist. Der ursprüngliche Laptopfehler wurde in der
Testumgebung nicht reproduziert; die Wirkung auf diesem Laptop ist noch unbestätigt.

Grundlage: Ventoy 1.1.17 `custom_boot` in
[ventoy_plugin.c](https://github.com/ventoy/Ventoy/blob/v1.1.17/GRUB2/MOD_SRC/grub-2.04/grub-core/ventoy/ventoy_plugin.c).
