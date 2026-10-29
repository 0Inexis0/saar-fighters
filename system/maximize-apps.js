// Loaded in the dedicated club user's KWin session at every login.
// Only main app windows are enlarged; dialogs and the panel keep their size.
function maximizeClubApp(window) {
    if (window && window.caption === "Saar-Fighters · Diashow"
            && [window.resourceClass, window.desktopFileName].some(function (id) {
                return /^(saar-home|de\.saarfighters\.Home)(\.desktop)?$/i.test(String(id || ""));
            })) {
        // An idle-triggered window needs compositor-side focus on Wayland.
        if (typeof workspace.activateWindow === "function") workspace.activateWindow(window);
        else workspace.activeWindow = window;
        return;
    }
    if (!window || !window.normalWindow || window.dialog || window.transient
            || window.fullScreen || !window.maximizable) return;
    const ids = [window.resourceClass, window.resourceName, window.desktopFileName];
    const brave = /^(brave|brave-browser|brave-browser-stable|com\.brave\.browser)(\.desktop)?$/i;
    if (ids.some(function (id) { return brave.test(String(id || "")); })) {
        window.fullScreen = true;
        return;
    }
    const knownApp = /^(firefox|org\.mozilla\.firefox|spotify|com\.spotify\.client|dolphin|org\.kde\.dolphin)(\.desktop)?$/i;
    if (ids.some(function (id) { return knownApp.test(String(id || "")); })) {
        window.setMaximize(true, true);
    }
}

workspace.windowAdded.connect(maximizeClubApp);
workspace.windowList().forEach(maximizeClubApp);
