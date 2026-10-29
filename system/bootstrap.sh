#!/usr/bin/env bash
# Run only inside the disposable development VM.
set -euo pipefail
exec > >(tee -a /var/log/saar-bootstrap.log) 2>&1
systemd-detect-virt --vm --quiet || { echo "VM required"; exit 1; }
printf 'Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch\n' > /etc/pacman.d/mirrorlist
sed -i 's/^#ParallelDownloads.*/ParallelDownloads = 8/' /etc/pacman.conf
pacman -Syu --noconfirm --needed qemu-guest-agent
systemctl enable --now qemu-guest-agent
pacman -S --noconfirm --needed plasma-desktop kscreen powerdevil systemsettings plasma-nm plasma-pa bluedevil \
  breeze-gtk sddm xorg-server mesa pyside6 python-dbus-next qt6-svg qt6-tools qt6-translations upower libpulse \
  networkmanager pipewire pipewire-pulse wireplumber \
  dolphin konsole flatpak vlc vlc-plugins-all noto-fonts noto-fonts-emoji \
  ttf-dejavu polkit-kde-agent spice-vdagent spectacle sudo
grep -qxF 'de_DE.UTF-8 UTF-8' /etc/locale.gen || printf '\nde_DE.UTF-8 UTF-8\n' >> /etc/locale.gen
locale-gen
printf 'LANG=de_DE.UTF-8\n' > /etc/locale.conf
printf 'KEYMAP=de-latin1\n' > /etc/vconsole.conf
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime
mkdir -p /etc/sudoers.d /etc/sddm.conf.d
printf '%%wheel ALL=(ALL:ALL) ALL\n' > /etc/sudoers.d/10-wheel
chmod 440 /etc/sudoers.d/10-wheel
cat > /etc/sddm.conf.d/saar.conf <<'EOF'
[Autologin]
User=saar
Session=plasma.desktop
[General]
DisplayServer=x11
EOF
systemctl enable NetworkManager bluetooth sddm
systemctl disable sshd
systemctl disable systemd-time-wait-sync.service
systemctl disable systemd-networkd systemd-networkd-wait-online || true
touch /var/lib/saar-base-ready
echo "SAAR_BASE_READY"
