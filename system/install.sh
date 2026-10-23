#!/usr/bin/env bash
# Deploy the shell to an already installed Arch test VM.
set -euo pipefail
[[ $EUID == 0 ]] || { echo "Run as root inside the VM."; exit 1; }
if [[ ${1:-} == --image && -e /etc/saar-live && -e /etc/mkinitcpio.conf.d/archiso.conf ]]; then
    : # Clean image root prepared by iso/configure-live.sh.
else
    systemd-detect-virt --vm --quiet || { echo "Use the live ISO installer on physical machines."; exit 1; }
fi
[[ -f /var/lib/saar-base-ready ]] || { echo "Base provisioning is incomplete."; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $root == /opt/saar-fighters ]] || { echo "Deploy project to /opt/saar-fighters first."; exit 1; }
# Existing installations also need the device worker and German translations.
for package in python-dbus-next qt6-translations upower libpulse git; do
    pacman -Q "$package" >/dev/null 2>&1 || pacman -S --needed --noconfirm "$package"
done
if ! locale -a | grep -qi '^de_DE.utf8$'; then
    grep -qxF 'de_DE.UTF-8 UTF-8' /etc/locale.gen || printf '\nde_DE.UTF-8 UTF-8\n' >> /etc/locale.gen
    locale-gen
fi
printf 'LANG=de_DE.UTF-8\n' > /etc/locale.conf
# A club laptop must boot offline too. Keep time synchronization in the
# background, without making the desktop wait for an NTP server.
systemctl disable systemd-time-wait-sync.service
systemctl reset-failed systemd-time-wait-sync.service || true
mkdir -p /etc/cloud
touch /etc/cloud/cloud-init.disabled
install -Dm755 "$root/system/saar-update" /usr/local/libexec/saar-update
install -Dm755 "$root/system/update_custom.py" /usr/local/libexec/saar-update-custom.py
install -Dm644 "$root/system/de.saarfighters.update.policy" /usr/share/polkit-1/actions/de.saarfighters.update.policy
install -Dm644 "$root/system/de.saarfighters.Home.desktop" /usr/share/applications/de.saarfighters.Home.desktop
cat > /usr/local/bin/saar-home <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/python /opt/saar-fighters/app/main.py "$@"
EOF
chmod 755 /usr/local/bin/saar-home
install -d /usr/share/plasma/plasmoids/de.saarfighters.home
cp -a "$root/system/plasmoid/." /usr/share/plasma/plasmoids/de.saarfighters.home/
install -d /usr/share/plasma/desktoptheme/saar-olive
cp -a "$root/system/desktoptheme/saar-olive/." /usr/share/plasma/desktoptheme/saar-olive/
mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/saar.conf <<'EOF'
[Autologin]
User=saar
Session=plasma.desktop
[General]
DisplayServer=x11
EOF
club=/home/saar
install -d -o saar -g saar "$club/.config/autostart" \
    "$club/.config/systemd/user/plasma-workspace.target.wants" \
    "$club/.local/share" "$club/Musik" "$club/Dokumente"
install -m644 "$root/system/saar-home.service" "$club/.config/systemd/user/saar-home.service"
ln -sf ../saar-home.service "$club/.config/systemd/user/plasma-workspace.target.wants/saar-home.service"
cat > "$club/.config/autostart/saar-layout.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Saar-Fighters Einrichtung
Exec=/bin/bash /opt/saar-fighters/system/first-login.sh
OnlyShowIn=KDE;
EOF
if [[ ! -f "$club/.local/state/saar-profile-v1" ]]; then
cat > "$club/.config/kdeglobals" <<'EOF'
[General]
font=Noto Sans,11,-1,5,50,0,0,0,0,0
[KDE]
SingleClick=false
[Icons]
Theme=breeze-dark
EOF
cat > "$club/.config/kxkbrc" <<'EOF'
[Layout]
Use=true
LayoutList=de
EOF
cat > "$club/.config/kscreenlockerrc" <<'EOF'
[Daemon]
Autolock=false
LockOnResume=false
EOF
cat > "$club/.config/kwalletrc" <<'EOF'
[Wallet]
Enabled=false
EOF
cat > "$club/.config/baloofilerc" <<'EOF'
[Basic Settings]
Indexing-Enabled=false
EOF
cat > "$club/.config/powerdevilrc" <<'EOF'
[AC][SuspendAndShutdown]
AutoSuspendAction=0
[AC][Display]
DimDisplayWhenIdle=false
TurnOffDisplayWhenIdle=false
EOF
mkdir -p "$club/.local/state"
touch "$club/.local/state/saar-profile-v1"
fi
cat > "$club/.config/plasma-localerc" <<'EOF'
[Formats]
LANG=de_DE.UTF-8
[Translations]
LANGUAGE=de
EOF
chown -R saar:saar "$club/.config" "$club/.local" "$club/Musik" "$club/Dokumente"
mkdir -p /usr/lib/firefox/distribution
cat > /usr/lib/firefox/distribution/policies.json <<'EOF'
{
  "policies": {
    "RequestedLocales": ["de"],
    "DisableAppUpdate": true,
    "DisableTelemetry": true,
    "DisableFirefoxStudies": true,
    "DontCheckDefaultBrowser": true,
    "OverrideFirstRunPage": "",
    "OverridePostUpdatePage": "",
    "Preferences": {
      "browser.aboutwelcome.enabled": false,
      "browser.shell.checkDefaultBrowser": false
    }
  }
}
EOF
# Authentication is explicit, including on distributions with different defaults.
cat > /etc/polkit-1/rules.d/40-saar-admin.rules <<'EOF'
polkit.addAdminRule(function(action, subject) {
    return ["unix-user:wartung"];
});
EOF
if [[ ${1:-} != --image ]]; then
    flatpak remote-add --system --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi
echo "Saar-Fighters shell installed."
