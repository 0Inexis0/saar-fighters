#!/usr/bin/env bash
# Public entry point for an ALREADY INSTALLED Arch Linux. Never partitions disks.
set -euo pipefail
export PATH=/usr/bin:/bin
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo starten.'; exit 1; }
[[ $# == 0 ]] || { echo 'Keine Argumente erlaubt.'; exit 1; }
[[ -f /etc/arch-release && $(uname -m) == x86_64 ]] || { echo 'Benötigt installiertes Arch Linux (x86_64).'; exit 1; }
[[ ! -d /run/archiso && ! -e /etc/saar-live ]] || { echo 'Für eine Neuinstallation bitte die Saar-Fighters-ISO verwenden.'; exit 1; }
[[ -e /dev/tty ]] || { echo 'Bitte in einem interaktiven Terminal starten.'; exit 1; }
exec 9>/run/saar-setup.lock
flock -n 9 || { echo 'Eine Einrichtung läuft bereits.'; exit 1; }
for account in saar wartung; do
    if id "$account" &>/dev/null && [[ ! -f /var/lib/saar-existing-arch ]]; then
        echo "Konto $account existiert bereits. Zum Schutz vorhandener Konten wird abgebrochen."
        exit 1
    fi
done
if [[ -e /opt/saar-fighters && ! -f /var/lib/saar-existing-arch ]]; then
    echo 'Vorhandene Saar-Installation: bitte den Update-Button verwenden.'
    exit 1
fi
cat <<'INFO'
Saar-Fighters auf diesem Arch einrichten

- Arch und Pakete werden aktualisiert; KDE Plasma, Brave und Spotify installiert.
- Vereinsbenutzer saar mit automatischer Anmeldung und Administrator wartung.
- SDDM wird ab dem nächsten Start der Anmeldemanager.
- Systemsprache Deutsch, Tastatur Deutsch, Zeitzone Europe/Berlin.
- NetworkManager übernimmt nach dem Neustart die Netzwerkverwaltung.
- Bestehende Benutzer und persönliche Dateien bleiben erhalten.
- Es werden KEINE Laufwerke formatiert. Der Rechner startet nicht automatisch neu.

INFO
read -r -p 'Zum Einrichten EINRICHTEN eingeben: ' consent </dev/tty
[[ $consent == EINRICHTEN ]] || { echo 'Abgebrochen, keine Änderungen.'; exit 1; }
# No credential helpers, private keys or GitHub account are needed on this PC.
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0
pacman -Syu --needed --noconfirm git
stage=$(mktemp -d /var/tmp/saar-setup.XXXXXX)
trap 'rm -rf -- "$stage"' EXIT
git -c core.hooksPath=/dev/null clone --depth=1 --single-branch --branch main \
    https://github.com/0Inexis0/saar-fighters.git "$stage/source"
source_dir=$stage/source
revision=$(git -C "$source_dir" rev-parse HEAD)
packages=(plasma-desktop kscreen powerdevil systemsettings plasma-nm plasma-pa bluedevil breeze-gtk sddm xorg-server
    mesa pyside6 python-dbus-next qt6-svg qt6-tools qt6-translations upower libpulse
    networkmanager bluez bluez-utils pipewire pipewire-pulse wireplumber
    dolphin konsole flatpak vlc vlc-plugins-all noto-fonts
    noto-fonts-emoji ttf-dejavu polkit-kde-agent sudo xdg-utils)
pacman -S --needed --noconfirm "${packages[@]}"
backup=/var/lib/saar-setup-backups/$(date +%Y%m%d-%H%M%S)
mkdir -p "$backup"
chmod 700 "$backup"
for path in /etc/locale.conf /etc/vconsole.conf /etc/localtime /etc/sddm.conf.d \
    /usr/share/wayland-sessions/plasma.desktop /usr/lib/firefox/distribution/policies.json \
    /etc/polkit-1/rules.d/40-saar-admin.rules; do
    if [[ -e $path || -L $path ]]; then cp -a --parents "$path" "$backup/"; fi
done
readlink /etc/systemd/system/display-manager.service > "$backup/previous-display-manager" || true
for service in NetworkManager systemd-networkd systemd-networkd-wait-online; do
    systemctl is-enabled "$service" > "$backup/$service.enabled" || true
done
id saar &>/dev/null || useradd -m -G audio,video -s /bin/bash -c 'Saar-Fighters AS e.V.' saar
id wartung &>/dev/null || useradd -m -G wheel -s /bin/bash -c Wartung wartung
# Marker permits a failed setup to be retried without treating its own users as strangers.
touch /var/lib/saar-existing-arch
usermod -L saar
echo 'Eigenes Passwort für den Administrator wartung festlegen:'
passwd wartung </dev/tty >/dev/tty 2>&1
install -d /etc/sudoers.d
printf 'wartung ALL=(ALL:ALL) ALL\n' > /etc/sudoers.d/40-saar-wartung
chmod 440 /etc/sudoers.d/40-saar-wartung
visudo -cf /etc/sudoers.d/40-saar-wartung
mkdir -p /opt/saar-fighters
for folder in app system installer; do
    rm -rf -- "/opt/saar-fighters/$folder"
    cp -a "$source_dir/$folder" /opt/saar-fighters/
done
cp "$source_dir/LICENSE" /opt/saar-fighters/
chmod -R go-w /opt/saar-fighters
printf '%s\n' "$revision" > /opt/saar-fighters/.revision
touch /var/lib/saar-base-ready
bash /opt/saar-fighters/system/install.sh --existing-arch
printf 'KEYMAP=de-latin1\n' > /etc/vconsole.conf
ln -sfn /usr/share/zoneinfo/Europe/Berlin /etc/localtime
flatpak install --system --noninteractive flathub com.spotify.Client com.brave.Browser
# Only change next-boot activation. Do not terminate the current desktop/network.
old_display=$(readlink -f /etc/systemd/system/display-manager.service || true)
if [[ -n $old_display && ${old_display##*/} != sddm.service ]]; then
    systemctl disable "${old_display##*/}"
fi
systemctl enable sddm NetworkManager bluetooth
systemctl disable systemd-networkd systemd-networkd-wait-online || true
systemctl set-default graphical.target
cat <<INFO

Saar-Fighters wurde eingerichtet. Bitte jetzt selbst neu starten.
Anmeldung: saar automatisch; Wartung: wartung mit deinem gewählten Passwort.
Vorherige Systemkonfiguration gesichert unter: $backup
Updates später über die Oberfläche, ohne GitHub-Anmeldung.
INFO
