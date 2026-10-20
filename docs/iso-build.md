# ISO bauen und testen

Der Build verwendet das offizielle [Archiso-Profil](https://gitlab.archlinux.org/archlinux/archiso)
als Grundlage für BIOS- und UEFI-Boot. Die Pakete werden frisch installiert.
Die Festplatte einer Entwicklungs-VM und deren Benutzerprofile sind **nicht**
die Quelle für das ISO-Dateisystem.

## Build in einer eigenen Arch-VM

Root-Rechte werden ausschließlich in der Build-VM benötigt. Internetzugang
ist zum Laden der Arch-Pakete, Spotify und seiner Flatpak-Laufzeit nötig.
Empfohlen: 8 GB RAM, 4–6 CPUs und mindestens 30 GB freier Speicher.

```bash
pacman -Syu --needed archiso flatpak python
bash iso/build.sh /root/saar-build-neu
```

Der Zielordner muss neu sein; bestehende Build-Verzeichnisse werden nicht
überschrieben. Ergebnis unter `/root/saar-build-neu/out/`:

- `saar-fighters-os-*.iso`
- `SHA256SUMS`
- `arch-packages.txt` und `flatpak-packages.txt`

Arch und Flathub werden als Paketquellen verwendet. Neue Builds können andere
Paketversionen enthalten; die Paketlisten dokumentieren den jeweiligen Stand.
Die eingebauten Konten sind gesperrt. Das Wartungspasswort wird erst bei der
Installation gewählt. Spotify wird in einen frischen, eigenen Flatpak-Speicher
installiert; persönliche Kontodaten werden nicht eingebunden.
Die Dateirechte dieses Speichers werden ausdrücklich in Archisos
`file_permissions` übernommen, damit Runtime-Programme ausführbar bleiben.

`iso/configure-live.sh` läuft als Pacman-Hook im neu aufgebauten Dateisystem.
`system/install.sh --image` richtet die gemeinsame Oberfläche ein. Der Hook
wird danach aus dem fertigen Image entfernt. Der Installer liest beim Kopieren
nur das unveränderliche SquashFS vom ISO, prüft dessen SHA512 und erstellt auf
dem ausdrücklich bestätigten Laufwerk ein neues System.

## Separate Test-VMs

Auf dem Entwicklungsrechner mit libvirt, KVM und OVMF:

```bash
python scripts/create-iso-test-vm.py /absoluter/pfad/zur.iso --firmware uefi
virsh -c qemu:///session start saar-iso-test-uefi
# Separat auch BIOS testen:
python scripts/create-iso-test-vm.py /absoluter/pfad/zur.iso --firmware bios
virsh -c qemu:///session start saar-iso-test-bios
```

Jede VM erhält ein leeres Ziellaufwerk (`SAAR_INSTALL_TARGET`) und ein zweites
Laufwerk (`SAAR_KEEP_UNCHANGED`) mit einem Prüfmuster. Nur das erste Laufwerk darf
im Installationstest gelöscht werden. Der VM-Ersteller verweigert vorhandene
VM-Namen und Laufwerksdateien. Die normale Vereins-VM bleibt unverändert.

Nach der Installation die virtuelle ISO auswerfen und **vom installierten
Laufwerk** neu starten. Autologin, Oberfläche, deutsche Sprache, Pakete,
fehlende Live-Freigaben und das unveränderte zweite Laufwerk prüfen.

Der Gast-Agent und die Skripte unterstützen gezielt benannte Test-VMs:

```bash
SAAR_VM=saar-iso-test-uefi python scripts/guest.py 'lsblk -f'
```

VM-Passwörter, Build-Verzeichnisse und ISO-Dateien bleiben außerhalb von Git.
