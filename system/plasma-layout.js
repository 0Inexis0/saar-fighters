// Applied once to the dedicated club user, never to an administrator's desktop.
for (const panel of panels()) panel.remove();
const panel = new Panel;
panel.location = "top";
panel.height = 48;
panel.hiding = "none";
panel.addWidget("de.saarfighters.home");
const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", "");
tasks.writeConfig("showOnlyCurrentDesktop", true);
panel.addWidget("org.kde.plasma.panelspacer");
panel.addWidget("org.kde.plasma.digitalclock");
for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///opt/saar-fighters/app/assets/terrain.svg");
}
