#!/usr/bin/env bash
# Runs inside the NEW Archiso root during the package transaction.
set -euo pipefail
[[ -e /etc/mkinitcpio.conf.d/archiso.conf ]] || exit 1
useradd -m -u 1000 -G audio,video -s /bin/bash -c 'Saar-Fighters AS e.V.' saar
useradd -m -u 1001 -G wheel -s /bin/bash -c Wartung wartung
usermod -L root
usermod -L saar
usermod -L wartung
mkdir -p /var/lib /etc/sudoers.d /etc/cloud
touch /var/lib/saar-base-ready /etc/saar-live
printf 'saar-fighters-os\n' > /etc/hostname
printf '127.0.0.1 localhost\n::1 localhost\n127.0.1.1 saar-fighters-os\n' > /etc/hosts
printf 'de_DE.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\n' > /etc/locale.gen
printf 'KEYMAP=de-latin1\n' > /etc/vconsole.conf
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime
bash /opt/saar-fighters/system/install.sh --image
printf '%%wheel ALL=(ALL:ALL) ALL\n' > /etc/sudoers.d/10-wheel
printf 'saar ALL=(root) NOPASSWD: /usr/local/libexec/saar-install ""\n' > /etc/sudoers.d/90-saar-live
chmod 440 /etc/sudoers.d/10-wheel /etc/sudoers.d/90-saar-live
install -Dm755 /opt/saar-fighters/installer/saar-install /usr/local/libexec/saar-install
install -Dm644 /opt/saar-fighters/installer/de.saarfighters.Install.desktop /usr/share/applications/de.saarfighters.Install.desktop
systemctl enable NetworkManager bluetooth sddm qemu-guest-agent systemd-timesyncd
systemctl set-default graphical.target
# NetworkManager owns the resolver; no competing live network manager.
ln -sf /run/NetworkManager/resolv.conf /etc/resolv.conf
rm -f /etc/motd /etc/systemd/system/default.target.wants/*
# Pacman keyring is initialized once when live/installed media boots.
systemctl enable pacman-init.service
# No build-time identity or random seed is distributed.
: > /etc/machine-id
rm -f /var/lib/dbus/machine-id /var/lib/systemd/random-seed
chmod -R go-w /opt/saar-fighters
