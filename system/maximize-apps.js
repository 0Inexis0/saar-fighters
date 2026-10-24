// Loaded in the dedicated club user's KWin session at every login.
// Only main app windows are enlarged; dialogs and the panel keep their size.
function maximizeClubApp(window) {
    if (!window || !window.normalWindow || window.dialog || window.transient
            || window.fullScreen || !window.maximizable) return;
    const ids = [window.resourceClass, window.resourceName, window.desktopFileName];
    const knownApp = /^(firefox|org\.mozilla\.firefox|spotify|com\.spotify\.client|dolphin|org\.kde\.dolphin)(\.desktop)?$/i;
    if (ids.some(function (id) { return knownApp.test(String(id || "")); })) {
        window.setMaximize(true, true);
    }
}

workspace.windowAdded.connect(maximizeClubApp);
workspace.windowList().forEach(maximizeClubApp);
