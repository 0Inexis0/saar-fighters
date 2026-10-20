#!/usr/bin/env bash
set -euo pipefail
[[ $(id -un) == saar ]] || exit 0
mkdir -p "$HOME/.local/state"
[[ -f "$HOME/.local/state/saar-layout-v1" ]] && exit 0
plasma-apply-colorscheme BreezeDark
# Plasma's DBus service can take a few seconds after graphical-session startup.
for attempt in {1..30}; do
    if /usr/lib/qt6/bin/qdbus org.kde.plasmashell /PlasmaShell \
        org.kde.PlasmaShell.evaluateScript \
        "$(cat /opt/saar-fighters/system/plasma-layout.js)"; then
        touch "$HOME/.local/state/saar-layout-v1"
        exit 0
    fi
    sleep 1
done
exit 1
