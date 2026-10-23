#!/usr/bin/env python3
"""Fixed root helper, only available on the booted live ISO. One JSON request/stdin."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

from installer.core import disks, validate_request

MEDIA = Path("/run/archiso/bootmnt")
IMAGE = MEDIA / "saar/x86_64/airootfs.sfs"
ENV = {"PATH": "/usr/bin:/bin", "LANG": "de_DE.UTF-8", "LC_ALL": "de_DE.UTF-8", "LANGUAGE": "de"}


def emit(percent, message):
    print(json.dumps({"percent": percent, "message": message}, ensure_ascii=False), flush=True)


def run(*args, input=None):
    # Never relay command stderr, argv or stdin: an error must not reveal passwords.
    result = subprocess.run(args, input=input, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=ENV)
    log = Path("/run/saar-install.log")
    with log.open("a") as stream:
        log.chmod(0o600)
        stream.write("Schritt: " + " ".join(args) + "\n")
        if input is None:
            stream.write(result.stdout + "\n")
        else:
            stream.write("Geschützte Eingabe; Ausgabe wird nicht protokolliert.\n")
    if result.returncode:
        # Fixed internal commands only; paths selected by us are safe to report.
        raise RuntimeError(f"Der Installationsschritt „{Path(args[0]).name}“ ist fehlgeschlagen.")
    return result.stdout


def unlink(root, relative):
    path = root / relative
    if path.is_symlink() or path.is_file():
        path.unlink()


def configure_target(root, password):
    # Never copy the live overlay: installed user data comes only from the immutable image.
    for path in ("etc/saar-live", "etc/sudoers.d/90-saar-live",
                 "usr/share/applications/de.saarfighters.Install.desktop",
                 "usr/local/libexec/saar-install", "etc/mkinitcpio.conf.d/archiso.conf",
                 "etc/systemd/logind.conf.d/do-not-suspend.conf",
                 "etc/systemd/journald.conf.d/volatile-storage.conf",
                 "etc/systemd/system/etc-pacman.d-gnupg.mount",
                 "etc/systemd/system/pacman-init.service",
                 "etc/systemd/system/multi-user.target.wants/pacman-init.service",
                 "etc/systemd/system/sockets.target.wants/systemd-networkd.socket",
                 "etc/systemd/system/multi-user.target.wants/systemd-networkd.service",
                 "etc/systemd/system/multi-user.target.wants/systemd-resolved.service"):
        unlink(root, path)
    shutil.rmtree(root / "root/.gnupg", ignore_errors=True)
    shutil.rmtree(root / "root/.ssh", ignore_errors=True)
    for path in ("root/.automated_script.sh", "root/.zlogin", "root/.zshrc", "root/install.txt"):
        unlink(root, path)
    (root / "etc/machine-id").write_text("")
    unlink(root, "var/lib/dbus/machine-id")
    unlink(root, "var/lib/systemd/random-seed")
    (root / "etc/mkinitcpio.conf").write_text(
        'HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)\n')
    (root / "etc/mkinitcpio.d").mkdir(exist_ok=True)
    (root / "etc/mkinitcpio.d/linux.preset").write_text(
        "ALL_config='/etc/mkinitcpio.conf'\nALL_kver='/boot/vmlinuz-linux'\n"
        "PRESETS=('default' 'fallback')\ndefault_image='/boot/initramfs-linux.img'\n"
        "fallback_image='/boot/initramfs-linux-fallback.img'\nfallback_options='-S autodetect'\n")
    kernel = MEDIA / "saar/boot/x86_64/vmlinuz-linux"
    shutil.copyfile(kernel, root / "boot/vmlinuz-linux")
    (root / "etc/default/grub").write_text(
        'GRUB_DEFAULT=0\nGRUB_TIMEOUT=3\nGRUB_DISTRIBUTOR="Saar-Fighters OS"\n'
        'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\nGRUB_CMDLINE_LINUX=""\n'
        'GRUB_DISABLE_OS_PROBER=true\nGRUB_LANG=de_DE\n')
    run("arch-chroot", str(root), "chpasswd", input="wartung:" + password + "\n")
    run("arch-chroot", str(root), "usermod", "-L", "root")
    run("arch-chroot", str(root), "usermod", "-L", "saar")
    # Installed keys persist; the live ISO's tmpfs keyring must not be carried over.
    run("arch-chroot", str(root), "pacman-key", "--init")
    run("arch-chroot", str(root), "pacman-key", "--populate", "archlinux")
    run("arch-chroot", str(root), "systemctl", "enable", "fstrim.timer")
    # VM integrations activate only when relevant hardware is present.
    run("arch-chroot", str(root), "mkinitcpio", "-P")


def partition_device(path, fd):
    # udev takes its own shared flock while probing devices. Release our table
    # write lock before partprobe/settle, otherwise discovery waits on us.
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        run("wipefs", "--all", path)
        run("sgdisk", "--zap-all", path)
        run("sgdisk", "--new=1:2048:+2M", "--typecode=1:ef02",
            "--new=2:0:+512M", "--typecode=2:ef00",
            "--new=3:0:0", "--typecode=3:8300", path)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
    run("partprobe", path)
    run("udevadm", "settle", "--timeout=30")


def install(request):
    if os.geteuid() != 0 or not Path("/etc/saar-live").is_file() or not IMAGE.is_file():
        raise ValueError("Die Installation ist nur vom Saar-Fighters-USB-Stick möglich.")
    if run("findmnt", "-rn", "-T", str(IMAGE), "-o", "FSTYPE").strip() != "iso9660":
        raise ValueError("Das Installationsmedium wurde nicht als ISO erkannt.")
    lock = open("/run/saar-install.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError("Eine Installation läuft bereits.") from None
    target = validate_request(request, disks())
    path = target["path"]
    # Verify a real block device; partition writes use a scoped advisory lock.
    if not stat.S_ISBLK(os.stat(path).st_mode):
        raise ValueError("Kein gültiges Laufwerk.")
    emit(3, "Installationsmedium wird auf Lesefehler geprüft …")
    expected = (IMAGE.parent / "airootfs.sha512").read_text().split()[0]
    with IMAGE.open("rb") as source:
        actual = hashlib.file_digest(source, "sha512").hexdigest()
    if actual != expected:
        raise ValueError("Die ISO ist beschädigt. Bitte den USB-Stick neu erstellen.")
    # Revalidate after the slow checksum and before the first destructive write.
    validate_request(request, disks())
    fd = os.open(path, os.O_RDWR)
    root = Path(tempfile.mkdtemp(prefix="saar-target-", dir="/mnt"))
    mounted = False
    try:
        emit(10, "Das bestätigte Laufwerk wird neu eingerichtet …")
        partition_device(path, fd)
        suffix = "p" if path[-1].isdigit() else ""
        efi, system = path + suffix + "2", path + suffix + "3"
        run("mkfs.fat", "-F", "32", "-n", "SAAR_EFI", efi)
        run("mkfs.ext4", "-F", "-L", "SAAR_SYSTEM", system)
        run("mount", system, str(root))
        mounted = True
        emit(20, "Vereinsoberfläche, Programme und Spotify werden kopiert …")
        run("unsquashfs", "-no-progress", "-processors", "2", "-f", "-d", str(root), str(IMAGE))
        (root / "boot/efi").mkdir(parents=True, exist_ok=True)
        run("mount", efi, str(root / "boot/efi"))
        root_uuid = run("blkid", "-s", "UUID", "-o", "value", system).strip()
        efi_uuid = run("blkid", "-s", "UUID", "-o", "value", efi).strip()
        (root / "etc/fstab").write_text(
            f"UUID={root_uuid} / ext4 defaults,noatime 0 1\n"
            f"UUID={efi_uuid} /boot/efi vfat umask=0077 0 2\n/swapfile none swap defaults 0 0\n")
        run("fallocate", "-l", "2G", str(root / "swapfile"))
        (root / "swapfile").chmod(0o600)
        run("mkswap", str(root / "swapfile"))
        emit(65, "Deutsche Systemeinstellungen und Wartungskonto werden eingerichtet …")
        configure_target(root, request["admin_password"])
        request["admin_password"] = ""
        emit(88, "Startsystem für UEFI und ältere BIOS-Geräte wird installiert …")
        run("arch-chroot", str(root), "grub-install", "--target=i386-pc", "--recheck", path)
        run("arch-chroot", str(root), "grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi",
            "--bootloader-id=SaarFighters", "--removable", "--no-nvram")
        run("arch-chroot", str(root), "grub-mkconfig", "-o", "/boot/grub/grub.cfg")
        # Independent prerequisites for a bootable result, not just a successful copy.
        for relative in ("boot/vmlinuz-linux", "boot/initramfs-linux.img", "boot/grub/grub.cfg",
                         "boot/efi/EFI/BOOT/BOOTX64.EFI", "etc/fstab"):
            if not (root / relative).is_file() or (root / relative).stat().st_size == 0:
                raise RuntimeError("Die Abschlussprüfung ist fehlgeschlagen. Bitte nicht neu starten.")
        run("sync")
        run("umount", "-R", str(root))
        mounted = False
        emit(100, "Installation abgeschlossen. USB-Stick beim Neustart entfernen.")
    finally:
        request["admin_password"] = ""
        if mounted:
            subprocess.run(["umount", "-R", str(root)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(fd)
        try:
            root.rmdir()
        except OSError:
            pass
        lock.close()


def main():
    try:
        request = json.loads(sys.stdin.readline(16384))
        if not isinstance(request, dict):
            raise ValueError("Ungültiger Installationsauftrag.")
        install(request)
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), flush=True)
        return 1
    except Exception:
        print(json.dumps({"error": "Die Installation ist fehlgeschlagen. Bitte neu starten und erneut versuchen."}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
