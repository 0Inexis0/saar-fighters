#!/usr/bin/env bash
# Build only in a disposable Arch VM. No host drives are modified.
set -euo pipefail
[[ $EUID == 0 ]] || { echo "Build benötigt Root-Rechte in der Build-VM."; exit 1; }
systemd-detect-virt --vm --quiet || { echo "Bitte eine separate Build-VM verwenden."; exit 1; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_dir=${1:?Aufruf: iso/build.sh ABSOLUTER_BUILD_ORDNER}
[[ $build_dir == /* && ! -e $build_dir ]] || { echo "Build-Ordner muss absolut und neu sein."; exit 1; }
mkdir -p "$build_dir/out"
cp -a /usr/share/archiso/configs/releng "$build_dir/profile"
profile=$build_dir/profile
rootfs=$profile/airootfs
cp "$source_dir/iso/packages.x86_64" "$profile/packages.x86_64"
# Preserve upstream boot machinery, use our own identity and bounded compressor.
cat >> "$profile/profiledef.sh" <<'PROFILE'
iso_name="saar-fighters-os"
iso_label="SAAR_$(date +%Y%m%d)"
iso_publisher="Saar-Fighters AS e.V."
iso_application="Saar-Fighters OS ausprobieren und installieren"
iso_version="0.1.0-$(date +%Y.%m.%d)"
install_dir="saar"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '10' '-b' '1M' '-processors' '4')
PROFILE
# No cloud-init, SSH or root console autologin in the club live image.
rm -f "$rootfs/etc/passwd" "$rootfs/etc/shadow"
rm -rf "$rootfs/etc/ssh" "$rootfs/etc/systemd/network" \
  "$rootfs/etc/systemd/system/getty@tty1.service.d" \
  "$rootfs/etc/systemd/system/multi-user.target.wants" \
  "$rootfs/etc/systemd/system/sockets.target.wants"
# Install our package transaction hook, avoiding deprecated customize_airootfs.sh.
mkdir -p "$rootfs/opt/saar-fighters" "$rootfs/etc/pacman.d/hooks"
for folder in app system installer iso; do
  cp -a "$source_dir/$folder" "$rootfs/opt/saar-fighters/"
done
cp "$source_dir/LICENSE" "$rootfs/opt/saar-fighters/LICENSE"
find "$rootfs/opt/saar-fighters" -type d -name __pycache__ -prune -exec rm -rf {} +
cat > "$rootfs/etc/pacman.d/hooks/zzzz90-saar-configure.hook" <<'HOOK'
# remove from airootfs!
[Trigger]
Operation = Install
Type = Package
Target = linux
[Action]
Description = Deutsche Vereinsoberfläche einrichten
When = PostTransaction
Exec = /bin/bash /opt/saar-fighters/iso/configure-live.sh
HOOK
cat > "$rootfs/etc/mkinitcpio.conf.d/archiso.conf" <<'INITRD'
HOOKS=(base udev microcode modconf kms memdisk archiso archiso_loop_mnt block filesystems keyboard keymap consolefont)
COMPRESSION="zstd"
INITRD
# Spotify and its runtime come from a fresh store, never a user's profile.
export FLATPAK_SYSTEM_DIR="$rootfs/var/lib/flatpak"
flatpak remote-add --system --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak config --system --set languages 'de;en'
flatpak install --system --noninteractive flathub com.spotify.Client
flatpak list --system --columns=application,version,branch > "$build_dir/out/flatpak-packages.txt"
# Archiso intentionally normalizes overlay modes. Flatpak's runtime contains
# executables and a content-addressed repository whose exact modes must survive.
python - "$rootfs" "$profile/profiledef.sh" <<'PY'
import os
from pathlib import Path
import shlex
import stat
import sys
root = Path(sys.argv[1])
with open(sys.argv[2], "a") as profile:
    for directory, folders, files in os.walk(root / "var/lib/flatpak"):
        for path in [Path(directory), *(Path(directory) / name for name in files)]:
            if path.is_symlink():
                continue
            relative = "/" + str(path.relative_to(root))
            mode = stat.S_IMODE(path.stat().st_mode)
            profile.write(f'file_permissions[{shlex.quote(relative)}]="0:0:{mode:04o}"\n')
PY
# German boot menus, with the official Archiso kernel parameters.
cp -a "$source_dir/iso/syslinux/." "$profile/syslinux/"
rm -f "$profile/efiboot/loader/entries/"*.conf
cp -a "$source_dir/iso/efiboot/." "$profile/efiboot/"
mkarchiso -v -w "$build_dir/work" -o "$build_dir/out" "$profile"
cp "$build_dir/work/iso/saar/pkglist.x86_64.txt" "$build_dir/out/arch-packages.txt"
(cd "$build_dir/out" && sha256sum ./*.iso > SHA256SUMS)
echo "ISO fertig: $build_dir/out"
