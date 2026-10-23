#!/usr/bin/env bash
set -euo pipefail
[[ $(id -un) == saar ]] || exit 0
mkdir -p "$HOME/.local/state"
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
    exit 0
fi
plasma-apply-colorscheme BreezeDark
# Plasma's DBus service can take a few seconds after graphical-session startup.
for attempt in {1..30}; do
    if /usr/lib/qt6/bin/qdbus org.kde.plasmashell /PlasmaShell \
        org.kde.PlasmaShell.evaluateScript \
        "$(cat /opt/saar-fighters/system/plasma-layout.js)"; then
        touch "$HOME/.local/state/saar-layout-v1" "$HOME/.local/state/saar-panel-bottom-v1"
        exit 0
    fi
    sleep 1
done
exit 1
