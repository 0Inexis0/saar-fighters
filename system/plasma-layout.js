// Applied once to the dedicated club user, never to an administrator's desktop.
for (const panel of panels()) panel.remove();
const panel = new Panel;
panel.location = "bottom";
panel.height = 48;
panel.hiding = "none";
const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", "applications:de.saarfighters.Home.desktop");
tasks.writeConfig("showOnlyCurrentDesktop", true);
panel.addWidget("org.kde.plasma.panelspacer");
panel.addWidget("org.kde.plasma.digitalclock");
for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///opt/saar-fighters/app/assets/terrain.svg");
}
