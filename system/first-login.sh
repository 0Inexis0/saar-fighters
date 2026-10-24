#!/usr/bin/env bash
set -euo pipefail
[[ $(id -un) == saar ]] || exit 0
mkdir -p "$HOME/.local/state"
# Run every login, including existing installations after an update.
# This is independent of the one-time desktop layout migration below.
for attempt in {1..30}; do
    if /usr/lib/qt6/bin/qdbus org.kde.KWin /Scripting \
        org.kde.kwin.Scripting.isScriptLoaded saar-maximize-apps | grep -qx true; then
        /usr/lib/qt6/bin/qdbus org.kde.KWin /Scripting org.kde.kwin.Scripting.start
        break
    fi
    if script_id=$(/usr/lib/qt6/bin/qdbus org.kde.KWin /Scripting \
        org.kde.kwin.Scripting.loadScript \
        /opt/saar-fighters/system/maximize-apps.js saar-maximize-apps) \
        && [[ "$script_id" =~ ^[0-9]+$ ]] \
        && /usr/lib/qt6/bin/qdbus org.kde.KWin /Scripting org.kde.kwin.Scripting.start; then
        break
    fi
    sleep 1
done
# Apply the panel style independently of the one-time layout migration.
if [[ ! -f "$HOME/.local/state/saar-panel-olive-v1" ]]; then
    plasma-apply-desktoptheme saar-olive
    touch "$HOME/.local/state/saar-panel-olive-v1"
fi
if [[ -f "$HOME/.local/state/saar-layout-v1" ]]; then
    if [[ ! -f "$HOME/.local/state/saar-panel-bottom-v1" ]]; then
        /usr/lib/qt6/bin/qdbus org.kde.plasmashell /PlasmaShell \
            org.kde.PlasmaShell.evaluateScript \
            'for (const panel of panels()) { panel.location = "bottom"; }'
        touch "$HOME/.local/state/saar-panel-bottom-v1"
    fi
    if [[ ! -f "$HOME/.local/state/saar-single-home-v1" ]]; then
        /usr/lib/qt6/bin/qdbus org.kde.plasmashell /PlasmaShell \
            org.kde.PlasmaShell.evaluateScript \
            'for (const panel of panels()) {
                for (const widget of panel.widgets()) {
                    if (widget.type === "de.saarfighters.home") widget.remove();
                    if (widget.type === "org.kde.plasma.icontasks") {
                        widget.currentConfigGroup = ["General"];
                        widget.writeConfig("launchers", "applications:de.saarfighters.Home.desktop");
                    }
                }
            }'
        touch "$HOME/.local/state/saar-single-home-v1"
    fi
    exit 0
fi
plasma-apply-colorscheme BreezeDark
# Plasma's DBus service can take a few seconds after graphical-session startup.
for attempt in {1..30}; do
    if /usr/lib/qt6/bin/qdbus org.kde.plasmashell /PlasmaShell \
        org.kde.PlasmaShell.evaluateScript \
        "$(cat /opt/saar-fighters/system/plasma-layout.js)"; then
        touch "$HOME/.local/state/saar-layout-v1" "$HOME/.local/state/saar-panel-bottom-v1" "$HOME/.local/state/saar-single-home-v1"
        exit 0
    fi
    sleep 1
done
exit 1
