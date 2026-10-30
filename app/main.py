#!/usr/bin/env python3
"""Saar-Fighters Home: a small native launcher, no browser runtime."""
import argparse
import os
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QEvent, QLibraryInfo, QLocale, QProcess, QTranslator, Qt, QTimer, QSize, QRectF
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QStackedLayout, QVBoxLayout, QWidget,
)
from applications import Application, SHORTCUTS, GAMEMODES, application_catalog, gamemode_catalog
from devices import AudioSheet, BluetoothSheet, BrightnessSheet, DeviceClient, WifiSheet, LogsSheet, label
from hardware import status_labels
from slideshow import IdleSlideshow
from media_content import ArtworkLoader
from music_player import ArtworkView, MusicPlayerDialog, PlayerSlider, clock_text
from runtime_health import record as record_health, categories as error_categories
from browser import browser_command
from application_runner import application_command
from maintenance import MaintenancePage
from devices import NoticeLabel
from system_settings import DisplaySheet, EnergySheet, SystemSheet
from settings_ui import apply_soft_settings
from notifications import NotificationCenter
from notification_window import NotificationsDialog
from notification_bridge import NotificationBridge
from system_status import snapshot as system_snapshot

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
SOCKET = f"saar-home-{getattr(os, 'getuid', lambda: 0)()}"
CLUB_WEBSITE = "https://www.saarfighters-as.de/"

PATHS = {
    "gamemodes": '<path d="M7 7h10a4 4 0 0 1 4 3l1 6a2 2 0 0 1-3.4 1.7L16 15H8l-2.6 2.7A2 2 0 0 1 2 16l1-6a4 4 0 0 1 4-3Z"/><path d="M6 11h4M8 9v4"/><circle cx="16" cy="10" r=".7"/><circle cx="18" cy="12" r=".7"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    "expand": '<path d="M14 3h7v7M21 3l-7 7M10 21H3v-7M3 21l7-7"/>',
    "collapse": '<path d="m5 9 7 7 7-7"/>',
    "shuffle": '<path d="M3 6h3c5 0 7 12 12 12h3m-4-4 4 4-4 4M3 18h3c2 0 4-2 6-6s4-6 6-6h3m-4-4 4 4-4 4"/>',
    "repeat": '<path d="m17 2 4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3"/>',
    "repeat_one": '<path d="m17 2 4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3m8-8 2-1v6"/>',
    "apps": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "play": '<path d="m8 4 12 8-12 8z"/>',
    "pause": '<path d="M8 4v16M16 4v16"/>',
    "previous": '<path d="M5 5v14m14-14L8 12l11 7z"/>',
    "next": '<path d="M19 5v14M5 5l11 7-11 7z"/>',
    "muted": '<path d="M3 9h4l5-4v14l-5-4H3zM16 9l6 6M22 9l-6 6"/>',
    "youtube": '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3z"/>',
    "music": '<path d="M9 18V5l12-3v13M9 8l12-3"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="18" cy="15" rx="3" ry="2"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="m9 3 1-2h4l1 2 2 1 2-.2 2 3-1 2v3l1 2-2 3-2-.2-2 1-1 2h-4l-1-2-2-1-2 .2-2-3 1-2v-3l-1-2 2-3 2 .2z"/>',
    "brightness": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
    "web": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
    "wifi": '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M8.5 16a5.5 5.5 0 0 1 7 0"/><circle cx="12" cy="20" r=".8"/>',
    "sound": '<path d="M3 9h4l5-4v14l-5-4H3zM16 8a6 6 0 0 1 0 8M19 4a11 11 0 0 1 0 16"/>',
    "bluetooth": '<path d="M6 6l12 12-6 4V2l6 4L6 18"/>',
    "update": '<path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5M4 16a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
    "folder": '<path d="M3 6h7l2 3h9v11H3zM3 6V4h7l2 2h9v3"/>',
    "power": '<path d="M12 2v10M6 5a9 9 0 1 0 12 0"/>',
    "restart": '<path d="M4 9a9 9 0 1 1 1 9M4 3v6h6"/>',
    "home": '<path d="M3 11l9-8 9 8M6 9v12h5v-7h3v7h4V9"/>',
    "battery": '<rect x="2" y="6" width="18" height="12" rx="2"/><path d="M23 10v4M6 9v6M10 9v6M14 9v6"/>',
    "charger": '<path d="M8 2v5m8-5v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5"/>',
    "rocket": '<path d="M14 4c3-2 6-2 6-2s0 3-2 6l-7 7-5-5zM6 10H3l-1 5 5-1m4 1-1 5 5-1v-3M6 17l-3 4 4-3"/><circle cx="15" cy="7" r="1.5"/>',
}


def icon(name, color="#e6e9df", size=40):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
           f'<g fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" '
           f'stroke-linejoin="round">{PATHS[name]}</g></svg>')
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


BUTTON_ICONS = {
    "gamemodes": (),
    "apps": (),
    "rocket": (),
    "youtube": (),
    "settings": ("preferences-system",),
    "brightness": ("display-brightness",),
    "music": ("com.spotify.Client", "spotify"),
    "web": ("com.brave.Browser", "brave-browser", "brave"),
    "folder": ("org.kde.dolphin", "system-file-manager"),
    "wifi": ("network-wireless", "preferences-system-network-wireless"),
    "sound": ("preferences-desktop-sound", "audio-volume-high"),
    "bluetooth": ("preferences-system-bluetooth", "bluetooth"),
    "update": ("system-software-update",),
    "restart": ("system-reboot",),
    "power": ("system-shutdown",),
}


def configure_icons():
    # Include system Flatpak exports so Spotify uses its installed brand logo.
    paths = QIcon.themeSearchPaths()
    for path in ("/usr/share/icons", "/var/lib/flatpak/exports/share/icons",
                 str(Path.home() / ".local/share/flatpak/exports/share/icons")):
        if path not in paths:
            paths.append(path)
    QIcon.setThemeSearchPaths(paths)
    if not QIcon.themeName():
        QIcon.setThemeName("breeze-dark")
    QIcon.setFallbackThemeName("breeze-dark")


def button_icon(name, size=40):
    if name == "rocket":
        return QIcon(str(ASSETS / "rocket-launch.png"))
    if name == "youtube":
        return QIcon(str(ASSETS / "youtube.png"))
    if name == "club":
        return QIcon(str(ASSETS / "club-logo.gif"))
    flat_icon = ASSETS / "fluent" / f"{name}.svg"
    if flat_icon.is_file():
        return QIcon(str(flat_icon))
    for theme_name in BUTTON_ICONS[name]:
        result = QIcon.fromTheme(theme_name)
        if not result.isNull():
            return result
    # Keep controls usable in previews without the target applications installed.
    return icon(name, "#c3b48b", size)


class StatusValue(QLabel):
    """Keep long device names from pushing the header beyond the window."""
    def __init__(self):
        super().__init__()
        self.full_text = ""
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        self.full_text = text
        self.setAccessibleName(text)
        self.setToolTip(text)
        self.refresh_text()

    def refresh_text(self):
        super().setText(self.fontMetrics().elidedText(
            self.full_text, Qt.TextElideMode.ElideRight, self.contentsRect().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_text()



class StatusControl(QPushButton):
    """Compact, keyboard-accessible status icon with full details on hover."""
    def __init__(self, symbol, title, action):
        super().__init__()
        self.symbol = symbol
        self.setObjectName("statusControl")
        self.setFixedSize(44, 44)
        self.setIconSize(QSize(22, 22))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_status(title)
        self.clicked.connect(action)

    def set_status(self, description, active=True):
        self.setIcon(icon(self.symbol, "#e6e9df" if active else "#919480", 22))
        self.setAccessibleName(description)
        self.setToolTip(description)


class Tile(QPushButton):
    def __init__(self, symbol, title, subtitle, action, accent=False):
        super().__init__()
        self.setObjectName("primaryTile" if accent else "tile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(170, 104)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        layout.addStretch()
        image = QLabel()
        # The original YouTube artwork includes its own clear space.
        icon_size = QSize(84, 72) if symbol == "youtube" else QSize(64, 64)
        image.setPixmap(button_icon(symbol).pixmap(icon_size))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setFixedHeight(72)
        layout.addWidget(image)
        text = QLabel(title)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setObjectName("tileTitle")
        text.setStyleSheet(f"color: {'#24261b' if accent else '#efede3'};")
        layout.addWidget(text)
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setObjectName("tileSubtitle")
        sub.setStyleSheet(f"color: {'#41452e' if accent else '#b7b6a6'};")
        layout.addWidget(sub)
        layout.addStretch()
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.clicked.connect(action)


class MusicTile(QFrame):
    """Now-playing information and controls for the selected session player."""
    def __init__(self, action, expand, home=None):
        super().__init__()
        self.expand = expand
        self.home = home
        self.state = {}
        self.seek_identity = None
        self.setObjectName("musicTile")
        self.setAccessibleName("Musikplayer")
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.artwork = ArtworkView(icon, self)
        self.artwork.fill_tile = True
        self.artwork.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.artwork.lower()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(6)
        heading = QHBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(label("Musik", "font-size: 14px; font-weight: 700;"))
        heading.addStretch()
        self.expand_button = QPushButton()
        self.expand_button.setObjectName("musicControl")
        self.expand_button.setFixedSize(44, 44)
        self.expand_button.setStyleSheet("min-height: 44px; max-height: 44px;")
        self.expand_button.setIcon(icon("expand", "#c3b48b", 24))
        self.expand_button.setIconSize(QSize(24, 24))
        self.expand_button.setAccessibleName("Musikplayer aufklappen")
        self.expand_button.setToolTip("Großer Player mit Lyrics")
        self.expand_button.clicked.connect(expand)
        heading.addWidget(self.expand_button)
        layout.addLayout(heading)
        layout.addStretch(1)
        self.source = StatusValue()
        self.source.setStyleSheet("color: #afb6a4; font-size: 11px;")
        self.track = StatusValue()
        self.track.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.artist = StatusValue()
        self.artist.setStyleSheet("color: #e1e4db; font-size: 12px;")
        for widget in (self.track, self.artist):
            widget.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(widget)
        self.source.setTextFormat(Qt.TextFormat.PlainText)
        self.source.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.source)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addStretch()
        self.buttons = {}
        for name, title in (("previous", "Vorheriger Titel"), ("playpause", "Play"),
                            ("next", "Nächster Titel")):
            button = QPushButton()
            button.setObjectName("musicPlay" if name == "playpause" else "musicControl")
            size = 52 if name == "playpause" else 44
            button.setFixedSize(size, size)
            button.setStyleSheet(f"min-height: {size}px; max-height: {size}px; border-radius: {size // 2}px;")
            button.setIcon(icon("play" if name == "playpause" else name,
                                "#24261b" if name == "playpause" else "#eeece1", 32))
            button.setIconSize(QSize(32, 32))
            button.setAccessibleName(title)
            button.setToolTip(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, a=name: action(a))
            controls.addWidget(button)
            self.buttons[name] = button
        controls.addStretch()
        layout.addLayout(controls)
        self.position = PlayerSlider("Wiedergabeposition", 1000)
        self.position.setMinimumHeight(24)
        self.position.sliderPressed.connect(self.capture_seek)
        self.position.actionTriggered.connect(lambda _: self.capture_seek())
        self.position.committed.connect(self.seek)
        layout.addWidget(self.position)
        self.times = label("--:-- / --:--", "font-size: 11px;")
        self.times.setFixedHeight(20)
        layout.addWidget(self.times)
        output_row = QHBoxLayout()
        self.outputs = QComboBox()
        self.outputs.setMinimumWidth(0)
        self.outputs.setFixedHeight(30)
        self.outputs.setStyleSheet("QComboBox {font-size: 11px; padding: 3px 6px; border: none; border-radius: 6px; background: #30362b;}")
        self.outputs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.outputs.setAccessibleName("Audioausgang schnell wechseln")
        self.outputs.activated.connect(self.choose_output)
        output_row.addWidget(self.outputs, 1)
        self.volume = PlayerSlider("Ausgangslautstärke")
        self.volume.setMinimumHeight(24)
        self.volume.setMinimumWidth(65)
        self.volume.setMaximumWidth(110)
        self.volume.committed.connect(lambda value: self.home.quick_action("audio", "volume", value=value) if self.home else None)
        output_row.addWidget(self.volume, 1)
        layout.addLayout(output_row)
        self.update_state({})

    def capture_seek(self):
        self.seek_identity = tuple(self.state.get(key) for key in ("player", "track_id", "duration"))

    def seek(self, value):
        if self.home and self.seek_identity and self.seek_identity == tuple(self.state.get(key) for key in ("player", "track_id", "duration")):
            player, track, duration = self.seek_identity
            self.home.quick_action("media", "seek", player=player, track_id=track, position=value / 1000 * duration)

    def choose_output(self, index):
        target = self.outputs.itemData(index)
        if self.home and target is not None:
            self.home.quick_action("audio", "output", id=target)

    def update_audio(self, data, error=None):
        if self.outputs.view().isVisible():
            return
        self.outputs.blockSignals(True)
        self.outputs.clear()
        outputs = data.get("outputs", []) if not error else []
        selected = [o for o in outputs if o.get("selected", o.get("default"))]
        if len(selected) > 1:
            self.outputs.addItem(f"{len(selected)} Boxen gemeinsam", None)
        for output in outputs:
            self.outputs.addItem(output.get("description", "Audioausgang"), output.get("id"))
            if len(selected) == 1 and output in selected:
                self.outputs.setCurrentIndex(self.outputs.count() - 1)
        self.outputs.blockSignals(False)
        self.outputs.setEnabled(bool(outputs))
        control = data.get("control")
        self.volume.setEnabled(bool(control) and not error)
        self.volume.reflect(min(100, control.get("volume", 0)) if control else 0)
        self.volume.setToolTip(f"Ausgangslautstärke: {self.volume.value()} %")

    def update_state(self, data, error=None):
        data = data if not error else {}
        identity = tuple(data.get(key) for key in ("player", "track_id", "duration"))
        if identity != tuple(self.state.get(key) for key in ("player", "track_id", "duration")):
            self.position.cancel()
            self.seek_identity = None
        self.state = dict(data)
        duration = data.get("duration", 0)
        position = data.get("position")
        self.position.setEnabled(bool(data.get("can_seek") and duration))
        self.position.reflect(round(position / duration * 1000) if position is not None and duration else 0)
        self.times.setText(f"{clock_text(position)} / {clock_text(duration or None)}")
        if error or not data.get("player"):
            self.source.setText("Nicht verbunden" if error else "Keine Wiedergabe")
            self.track.setText("Player nicht erreichbar" if error else "Bereit für Musik")
            self.artist.setText("Bitte erneut versuchen" if error else "Spotify oder YouTube öffnen")
        else:
            state = "Läuft" if data.get("playing") else (
                "Gestoppt" if data.get("playback_status") == "Stopped" else "Pausiert")
            self.source.setText(f"{data.get('player_name', 'Player')} · {state}")
            self.track.setText(data.get("title") or "Kein Titel verfügbar")
            self.artist.setText(data.get("artist") or "Kein Interpret verfügbar")
        self.setToolTip(error or "Steuert die Wiedergabe in Spotify oder im Browser.")
        playing = not error and data.get("playing", False)
        play = self.buttons["playpause"]
        play.setAccessibleName("Pause" if playing else "Play")
        play.setToolTip("Pause" if playing else "Play")
        play.setIcon(icon("pause" if playing else "play", "#24261b", 32))
        for name, capability in (("playpause", "available"), ("previous", "can_previous"),
                                 ("next", "can_next")):
            self.buttons[name].setEnabled(not error and bool(data.get(capability)))

    def set_busy(self):
        for button in self.buttons.values():
            button.setEnabled(False)
        self.position.setEnabled(False)

    def resizeEvent(self, event):
        self.artwork.setGeometry(self.rect())
        super().resizeEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.expand()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.expand()
            event.accept()
        else:
            super().keyPressEvent(event)


class UpdateDialog(QDialog):
    def __init__(self, parent, preview=False):
        super().__init__(parent)
        self.notifications = getattr(getattr(parent, "home", parent), "notifications", None)
        self.setWindowTitle("System aktualisieren")
        self.resize(740, 490)
        layout = QVBoxLayout(self)
        title = QLabel("Updates")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        info = QLabel("System und Apps aktualisieren.")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.hide()
        layout.addWidget(self.output, 1)
        self.state = NoticeLabel()
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        buttons = QHBoxLayout()
        self.start = QPushButton("Update starten")
        self.start.setObjectName("confirm")
        self.close_button = QPushButton("Zurück")
        buttons.addWidget(self.start)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        layout.addStretch()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.output.setMaximumBlockCount(2000)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished_update)
        self.process.errorOccurred.connect(self.process_error)
        self.start.clicked.connect(lambda: self.begin(preview))
        self.close_button.clicked.connect(self.reject)

    def begin(self, preview):
        if preview:
            self.state.clear()
            return
        self.start.setEnabled(False)
        self.close_button.setEnabled(False)
        self.output.clear()
        self.output.show()
        self.state.setText("Update läuft. Netzteil anschließen und nicht ausschalten.")
        self.process.start("pkexec", ["/usr/local/libexec/saar-update"])

    def read_output(self):
        self.output.appendPlainText(bytes(self.process.readAllStandardOutput()).decode(errors="replace"))

    def finished_update(self, code, status):
        self.close_button.setEnabled(True)
        if status == QProcess.ExitStatus.NormalExit and code == 0:
            self.state.setText("Update erfolgreich. Bitte neu starten, um alle Änderungen zu übernehmen.")
        elif code in (126, 127):
            self.state.setText("Update nicht freigegeben oder abgebrochen. Es wurde nicht erfolgreich abgeschlossen.")
            self.start.setEnabled(True)

        else:
            self.state.setText("Update fehlgeschlagen. Bitte die Ausgabe dem Administrator zeigen.")
            self.start.setEnabled(True)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.state.setText("Die Update-Verwaltung konnte nicht gestartet werden.")
            self.close_button.setEnabled(True)
            self.start.setEnabled(True)

    def reject(self):
        if self.process.state() == QProcess.ProcessState.NotRunning:
            super().reject()

    def closeEvent(self, event):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            event.ignore()
        else:
            super().closeEvent(event)


class AppTile(QPushButton):
    def __init__(self, application, action):
        super().__init__()
        self.setObjectName("tile")
        self.setAutoDefault(False)
        self.setMinimumSize(140, 112)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(application.title)
        self.setAccessibleDescription(application.description)
        self.setToolTip(application.title + ("\n" + application.description if application.description else ""))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(5)
        layout.addStretch()
        if application.id in {app.id for app in SHORTCUTS + GAMEMODES}:
            app_icon = button_icon(application.icon)
        elif Path(application.icon).is_absolute():
            app_icon = QIcon(application.icon)
        else:
            app_icon = QIcon.fromTheme(application.icon)
        if app_icon.isNull():
            app_icon = button_icon("apps")
        image = QLabel()
        image.setPixmap(app_icon.pixmap(QSize(64, 64)))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image)
        for text, style in ((application.title, "font-size: 20px; font-weight: 700;"),
                            (application.description or "Anwendung öffnen", "font-size: 12px; color: #b7b6a6;")):
            value = StatusValue()
            value.setTextFormat(Qt.TextFormat.PlainText)
            value.setStyleSheet(style)
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setText(" ".join(text.split()))
            layout.addWidget(value)
        layout.addStretch()
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.clicked.connect(action)


class AppsPage(QWidget):
    def __init__(self, home, gamemodes=False):
        super().__init__(home)
        self.home = home
        self.gamemodes = gamemodes
        self.category = "Gamemodes" if gamemodes else "Apps"
        self.setObjectName("appsPage")
        self.page = 0
        self.columns = 3
        self.applications = []
        self.filtered = []
        self.tiles = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)
        header = QHBoxLayout()
        header.addWidget(label(self.category, "font-size: 28px; font-weight: 700;"))
        self.count_label = label("", "color: #b7b6a6;")
        header.addWidget(self.count_label)
        header.addStretch()
        self.back_button = QPushButton("Zurück zur Startseite")
        self.back_button.clicked.connect(home.show_dashboard)
        header.addWidget(self.back_button)
        layout.addLayout(header)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(f"{self.category} suchen …")
        self.search.setAccessibleName(f"{self.category} suchen")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_apps)
        search_row.addWidget(self.search, 1)
        layout.addLayout(search_row)
        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        layout.addLayout(self.grid, 1)
        self.empty_label = label(f"Keine {self.category} gefunden. Versuche einen anderen Suchbegriff.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback = label("", "color: #c3b48b; font-size: 12px;")
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        layout.addWidget(self.feedback)
        self.navigation = QWidget()
        navigation = QHBoxLayout(self.navigation)
        navigation.setContentsMargins(0, 0, 0, 0)
        self.previous_button = QPushButton("Vorherige Seite")
        self.next_button = QPushButton("Nächste Seite")
        self.previous_button.clicked.connect(lambda: self.change_page(-1))
        self.next_button.clicked.connect(lambda: self.change_page(1))
        self.page_label = label("")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.page_label, 1)
        navigation.addWidget(self.next_button)
        layout.addWidget(self.navigation)
        self.reload_apps()
        self.search.setFocus()
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)

    @property
    def page_size(self):
        return self.columns * 2

    @property
    def page_count(self):
        return max(1, (len(self.filtered) + self.page_size - 1) // self.page_size)

    def reload_apps(self):
        self.applications = gamemode_catalog() if self.gamemodes else application_catalog()
        self.filter_apps()

    def filter_apps(self):
        words = self.search.text().casefold().split()
        self.filtered = [app for app in self.applications if all(
            word in f"{app.title} {app.description} {app.id}".casefold() for word in words)]
        self.page = 0
        self.show_page()

    def change_page(self, offset):
        self.page = max(0, min(self.page + offset, self.page_count - 1))
        self.show_page()

    def show_page(self):
        self.page = min(self.page, self.page_count - 1)
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            widget.hide()
            if widget is not self.empty_label:
                widget.deleteLater()
        self.tiles.clear()
        start = self.page * self.page_size
        for index, application in enumerate(self.filtered[start:start + self.page_size]):
            tile = AppTile(application, lambda checked=False, app=application: self.open_app(app))
            self.tiles[application.id] = tile
            self.grid.addWidget(tile, index // self.columns, index % self.columns)
        for column in range(4):
            self.grid.setColumnStretch(column, 1 if column < self.columns else 0)
            self.grid.setColumnMinimumWidth(column, 0)
        for row in range(2):
            self.grid.setRowStretch(row, 1)
        if not self.filtered:
            self.grid.addWidget(self.empty_label, 0, 0, 2, self.columns)
            self.empty_label.show()
        total = len(self.applications)
        unit = "Gamemode" if self.gamemodes and total == 1 else self.category
        self.count_label.setText(f"{len(self.filtered)} von {total} {unit}" if self.search.text().strip() else f"{total} {unit}")
        self.page_label.setText(f"Seite {self.page + 1} von {self.page_count}" if self.filtered else "Keine Treffer")
        self.previous_button.setEnabled(self.page > 0)
        self.next_button.setEnabled(self.page + 1 < self.page_count)
        self.navigation.setVisible(self.page_count > 1)

    def open_app(self, application):
        if self.home.launch_application(application):
            self.home.show_dashboard()
        else:
            self.feedback.setText(self.home.feedback.text())
            self.feedback.hide()


class SettingsDialog(QDialog):
    def __init__(self, home, section="wifi"):
        super().__init__(home)
        self.home = home
        self.page = None
        self.current_section = None
        self.update_page = None
        self.setWindowTitle("Einstellungen")
        self.setObjectName("settingsDialog")
        self.resize(min(home.width() - 32, 1040), min(home.height() - 24, 760))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("settingsSidebar")
        self.sidebar.setMinimumWidth(238)
        navigation = QVBoxLayout(self.sidebar)
        navigation.setContentsMargins(14, 22, 14, 14)
        navigation.setSpacing(3)
        navigation.addWidget(label("Einstellungen", "font-size: 21px; font-weight: 700;"))
        self.nav_buttons = {}
        for category, entries in (
            ("Verbindungen", (
                ("wifi", "WLAN", "wifi"),
                ("bluetooth", "Bluetooth", "bluetooth"),
            )),
            ("Gerät", (
                ("sound", "Ton && Lautsprecher", "sound"),
                ("brightness", "Bildschirm && Helligkeit", "brightness"),
                ("power", "Energie && Leistung", "energy"),
            )),
            ("Allgemein", (
                ("settings", "Systeminformationen", "system"),
            )),
            ("Wartung", (
                ("update", "Updates", "updates"),
                ("settings", "Fernwartung", "remote"),
                ("restart", "Wiederherstellung", "recovery"),
                ("settings", "Systemprotokolle", "logs"),
            )),
        ):
            navigation.addSpacing(12)
            heading = label(category, "font-size: 12px; font-weight: 600; color: #b9b8a7;")
            heading.setContentsMargins(12, 0, 0, 2)
            navigation.addWidget(heading)
            for symbol, title, action in entries:
                button = QPushButton(title)
                button.setObjectName("settingsNav")
                button.setIcon(button_icon(symbol, 22))
                button.setIconSize(QSize(18, 18))
                button.setCheckable(True)
                button.setAutoDefault(False)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(lambda checked=False, section=action: self.select_section(section))
                self.nav_buttons[action] = button
                navigation.addWidget(button)
        navigation.addStretch()
        self.back_button = QPushButton("Startseite")
        self.back_button.setIcon(icon("home", "#c3b48b", 20))
        self.back_button.setToolTip("Zurück zur Startseite")
        self.back_button.setAccessibleName("Zurück zur Startseite")
        self.back_button.setAutoDefault(False)
        self.back_button.clicked.connect(self.reject)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setWidget(self.sidebar)
        self.sidebar_scroll = sidebar_scroll
        rail = QFrame()
        rail.setObjectName("settingsRail")
        rail.setFixedWidth(254)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(0)
        rail_layout.addWidget(sidebar_scroll, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(14, 10, 14, 14)
        footer.addWidget(self.back_button)
        rail_layout.addLayout(footer)
        layout.addWidget(rail)
        self.content = QScrollArea()
        self.content.setObjectName("settingsContent")
        self.content.setWidgetResizable(True)
        self.content.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.content, 1)
        self.select_section(section)

    def page_back_button(self):
        return self.page.close_button if isinstance(self.page, UpdateDialog) else self.page.back

    def update_navigation(self):
        available = self.page_back_button().isEnabled()
        for section, button in self.nav_buttons.items():
            button.setChecked(section == self.current_section)
            button.setEnabled(available)
        self.back_button.setEnabled(available)

    def eventFilter(self, watched, event):
        if self.page:
            if watched is self.page_back_button() and event.type() == QEvent.Type.EnabledChange:
                self.update_navigation()
            elif watched is self.page and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(watched, event)

    def release_page(self):
        if not self.page:
            return True
        if not self.page_back_button().isEnabled():
            return False
        # Use the existing dialog lifecycle to stop searches and pending timers.
        self.page.reject()
        if self.page.isVisible():
            return False
        self.page_back_button().removeEventFilter(self)
        self.page.removeEventFilter(self)
        self.content.takeWidget()
        if self.page is self.update_page:
            self.page.setParent(self)
        else:
            self.page.deleteLater()
        self.page = None
        return True

    def select_section(self, section):
        if section == self.current_section or not self.release_page():
            self.update_navigation()
            return
        if section == "updates":
            if self.update_page is None:
                self.update_page = UpdateDialog(self, self.home.preview)
            self.page = self.update_page
        elif section in ("remote", "recovery"):
            self.page = MaintenancePage(self, self.home.preview, section)
        else:
            self.page = {"wifi": WifiSheet, "bluetooth": BluetoothSheet,
                         "sound": AudioSheet, "brightness": DisplaySheet, "logs": LogsSheet,
                         "energy": EnergySheet, "system": SystemSheet}[section](
                self, self.home.device_client)
        self.current_section = section
        # Reuse the device controls inside the settings window instead of opening a modal.
        self.page.setWindowFlags(Qt.WindowType.Widget)
        apply_soft_settings(self.page, section)
        self.page_back_button().hide()
        self.page_back_button().installEventFilter(self)
        self.page.installEventFilter(self)
        self.content.setWidget(self.page)
        self.page.show()
        self.content.verticalScrollBar().setValue(0)
        self.sidebar_scroll.ensureWidgetVisible(self.nav_buttons[section])
        self.update_navigation()

    def reject(self):
        if self.release_page():
            super().reject()

    def closeEvent(self, event):
        if self.release_page():
            super().closeEvent(event)
        else:
            event.ignore()


class Home(QWidget):
    def __init__(self, preview=False):
        super().__init__()
        self.preview = preview
        configure_icons()
        self.setObjectName("home")
        self.setWindowTitle("Saar-Fighters · Startseite")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 540)
        self.background = QSvgRenderer(str(ASSETS / "terrain.svg"))
        self.processes = []
        self.last_action = None
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.page_area = QWidget()
        self.pages = QStackedLayout(self.page_area)
        self.pages.setContentsMargins(0, 0, 0, 0)
        self.dashboard = QWidget()
        self.pages.addWidget(self.dashboard)
        self.apps_page = None
        self.gamemodes_page = None
        layout = QVBoxLayout(self.dashboard)
        layout.setContentsMargins(48, 24, 48, 22)
        layout.setSpacing(10)
        self.status_header = QWidget()
        header = QHBoxLayout(self.status_header)
        header.setContentsMargins(24, 12, 24, 0)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(ASSETS / "club-logo.gif")).scaled(
            56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAccessibleName("Original-Logo der Saar-Fighters AS")
        header.addWidget(logo)
        brand = QLabel("SAAR-FIGHTERS\nAS e.V.")
        brand.setStyleSheet("font-size: 14px; font-weight: 800; letter-spacing: 2px; color: #c3b48b;")
        header.addWidget(brand)
        header.addStretch()
        header.setSpacing(6)
        self.device_client = DeviceClient(self, preview)
        self.notifications = NotificationCenter(self, preview)
        self.notification_bridge = NotificationBridge(self.notifications, self, preview)
        self.notification_dialog = None
        self.notification_button = StatusControl("bell", "Mitteilungen öffnen", self.show_notifications)
        self.notification_badge = QLabel(self.notification_button)
        self.notification_badge.setObjectName("notificationBadge")
        self.notification_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_badge.setGeometry(23, 0, 21, 18)
        self.notification_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.notification_button.setAccessibleName("Benachrichtigungszentrale öffnen")
        self.notifications.changed.connect(self.update_notification_count)
        self.update_notification_count()
        self.system_timer = QTimer(self)
        self.system_timer.setInterval(60000)
        self.system_timer.timeout.connect(self.check_system_notifications)
        self.system_timer.start()
        QTimer.singleShot(1500, self.check_system_notifications)
        self.status_values = []
        for title, symbol, section in (("Netzwerk", "wifi", "wifi"),
                                       ("Bluetooth", "bluetooth", "bluetooth"),
                                       ("Netzteil", "charger", "energy"),
                                       ("Akku", "battery", "energy")):
            control = StatusControl(symbol, f"{title}: Wird geprüft …",
                                    lambda checked=False, target=section: self.show_status_section(target))
            header.addWidget(control)
            self.status_values.append(control)
        self.battery_percentage = label("", "font-size: 12px; color: #b6b393;")
        header.addWidget(self.battery_percentage)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedHeight(22)
        separator.setStyleSheet("color: #50523e;")
        header.addWidget(separator)
        header.addWidget(self.notification_button)
        shell.addWidget(self.status_header)
        shell.addWidget(self.page_area, 1)
        self.network = self.status_values[0]
        self.device_client.status_changed.connect(self.update_status)
        QTimer.singleShot(800, self.device_client.refresh_status)

        if preview:
            layout.addWidget(label("Vorschau · Statusanzeigen mit Beispieldaten",
                                   "font-size: 15px; color: #b9b8a7;"))

        if Path("/etc/saar-live").exists() and not preview:
            install_button = QPushButton("Auf diesem Rechner installieren")
            install_button.setObjectName("confirm")
            install_button.clicked.connect(lambda: self.launch("install"))
            layout.addWidget(install_button)

        grid = QGridLayout()
        self.tile_grid = grid
        grid.setSpacing(24)
        grid.setContentsMargins(48, 36, 48, 36)
        specs = [
            ("apps", "Apps", "Alle Anwendungen öffnen", "apps", False),
            ("gamemodes", "Gamemodes", "Spielmodus auswählen", "gamemodes", False),
            ("settings", "Einstellungen", "WLAN, Bluetooth, Ton, Bildschirm & Updates", "settings", False),
        ]
        self.tiles = {}
        for i, (symbol, title, subtitle, action, accent) in enumerate(specs):
            tile = Tile(symbol, title, subtitle, lambda checked=False, a=action: self.launch(a), accent)
            tile.setMinimumWidth(150)
            self.tiles[action] = tile
            if action == "gamemodes":
                grid.addWidget(tile, 1, 0, 1, 2)
            else:
                grid.addWidget(tile, 0, 0 if action == "apps" else 1)
        self.music_dialog = None
        self.artwork_loader = ArtworkLoader(self)
        self.music_tile = MusicTile(lambda action: self.quick_action("media", action), self.show_music, self)
        self.artwork_loader.changed.connect(self.music_tile.artwork.set_image)
        grid.addWidget(self.music_tile, 0, 2, 2, 1)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        layout.addLayout(grid, 1)
        self.feedback = QLabel()
        self.feedback.hide()
        self.feedback.setStyleSheet("color: #b6b393; font-size: 12px;")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        footer = QHBoxLayout()
        self.media_state = {}
        self.quick_busy = {"media": False, "audio": False}
        self.quick_pending = {"media": False, "audio": False}
        self.play_button = self.music_tile.buttons["playpause"]
        self.mute_button = QPushButton("Stummschalten")
        self.mute_button.setEnabled(False)
        self.mute_button.setIconSize(QSize(20, 20))
        footer.addWidget(self.mute_button)
        self.mute_button.setIcon(icon("sound", size=20))
        self.mute_button.clicked.connect(lambda: self.quick_action("audio"))
        self.quick_timer = QTimer(self)
        self.quick_timer.timeout.connect(self.refresh_quick_controls)
        self.quick_timer.start(3000)
        QTimer.singleShot(900, self.refresh_quick_controls)
        footer.addStretch()
        for symbol, text, action in (("restart", "Neustart", "reboot"), ("power", "Ausschalten", "poweroff")):
            button = QPushButton(f"  {text}")
            button.setIcon(button_icon(symbol, 20))
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda checked=False, a=action: self.power(a))
            footer.addWidget(button)
        layout.addLayout(footer)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.slideshow = IdleSlideshow(self, ASSETS / "slideshow", preview)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.background.render(painter, QRectF(self.rect()))
        painter.end()

    def refresh_quick_controls(self):
        for group, operation in (("media", "media_status"), ("audio", "audio")):
            if self.quick_pending[group] or self.quick_busy[group]:
                continue
            self.quick_pending[group] = True
            self.device_client.request(operation, callback=lambda data, error, g=group:
                                       self.quick_status(g, data, error))

    def quick_status(self, group, data, error):
        self.quick_pending[group] = False
        if self.quick_busy[group]:
            return
        data = data or {}
        if group == "media":
            self.media_state = data if not error else {}
            self.music_tile.update_state(data, error)
            self.artwork_loader.load(self.media_state.get("art_url", ""))
            if self.music_dialog:
                self.music_dialog.update_state(data, error)
        else:
            self.music_tile.update_audio(data, error)
            output = data.get("control") or next((o for o in data.get("outputs", []) if o.get("default")), None)
            muted = bool(output and output.get("mute"))
            self.mute_button.setText("Ton einschalten" if muted else "Stummschalten")
            self.mute_button.setIcon(icon("muted" if muted else "sound", size=20))
            self.mute_button.setEnabled(not error and output is not None)
            self.mute_button.setToolTip(error or ("Ton für alle ausgewählten Audioausgänge ein-/ausschalten."
                                                if output else "Kein Audioausgang verfügbar."))

    def quick_action(self, group, action="playpause", **options):
        if group == "media" and action not in ("playpause", "previous", "next", "seek", "volume", "shuffle", "repeat"):
            raise ValueError("Diese Medienaktion ist nicht verfügbar.")
        if self.quick_busy[group]:
            return
        if self.preview:
            self.set_feedback("Vorschau: Die Wiedergabe und der Ton bleiben unverändert.")
            if self.music_dialog:
                self.music_dialog.update_state(self.media_state)
            return
        self.quick_busy[group] = True
        if group == "media":
            self.music_tile.set_busy()
            if self.music_dialog:
                self.music_dialog.set_busy()
        else:
            self.mute_button.setEnabled(False)
        operation = f"media_{action}" if group == "media" else f"audio_{action}" if action in ("volume", "output") else "audio_toggle"
        args = {"player": self.media_state.get("player")} if group == "media" else {}
        args.update(options)
        def finished(data, error):
            self.quick_busy[group] = False
            self.set_feedback(error or "")
            self.refresh_quick_controls()
        self.device_client.request(operation, args, finished)

    def resizeEvent(self, event):
        self.status_header.layout().setContentsMargins(24 if self.width() < 1000 else 40, 12,
                                                       24 if self.width() < 1000 else 40, 0)
        self.dashboard.layout().setContentsMargins(24 if self.width() < 1000 else 40, 12, 24 if self.width() < 1000 else 40, 14)
        compact = self.width() < 1000 or self.height() < 650
        inset_x, inset_y = (8, 14) if compact else (24, 36)
        self.tile_grid.setContentsMargins(inset_x, inset_y, inset_x, inset_y)
        self.tile_grid.setSpacing(14 if compact else 24)
        for tile in self.tiles.values():
            title = tile.findChild(QLabel, "tileTitle")
            title.setStyleSheet("color: #efede3; font-size: 18px;" if compact else "color: #efede3; font-size: 22px;")
        super().resizeEvent(event)

    def update_status(self, status):
        self.notifications.devices(status)
        values = status_labels(status)
        network = status.get("network", {})
        bluetooth = status.get("bluetooth", {})
        power = status.get("power", {})
        active = (not network.get("error") and network.get("state", 0) >= 50,
                  not bluetooth.get("error") and bluetooth.get("powered", False),
                  not power.get("error") and power.get("plugged") is True,
                  not power.get("error") and power.get("percentage") is not None)
        for widget, text, enabled in zip(self.status_values, values, active):
            widget.set_status(text, enabled)
        connectivity = {0: "Internetstatus nicht geprüft", 1: "Kein Internet",
                        2: "Anmeldung im Browser erforderlich", 3: "Internet eingeschränkt",
                        4: "Internet erreichbar"}.get(network.get("connectivity", 0), "")
        self.network.setToolTip("\n".join(filter(None, (values[0], network.get("name", ""), connectivity))))
        names = [d["name"] for d in bluetooth.get("devices", []) if d.get("connected")]
        self.status_values[1].setToolTip("\n".join([values[1], *names]))
        pct = power.get("percentage")
        self.battery_percentage.setText(f"{round(pct)} %" if isinstance(pct, (int, float)) and not power.get("error") else "")
        self.battery_percentage.setToolTip(values[3])

    def update_notification_count(self):
        count = self.notifications.unread
        self.notification_badge.setText(str(count) if count < 100 else "99+")
        self.notification_badge.setVisible(count > 0)
        self.notification_button.set_status(
            f"Mitteilungen öffnen: {count} ungelesen" if count else "Mitteilungen öffnen: Keine ungelesenen Meldungen")

    def show_status_section(self, section):
        dialog = SettingsDialog(self, section)
        dialog.exec()
        dialog.deleteLater()

    def check_system_notifications(self):
        if not self.preview:
            data = system_snapshot()
            self.notifications.disk(data["disk_free"], data["disk_total"])

    def show_notifications(self):
        if self.notification_dialog is None:
            self.notification_dialog = NotificationsDialog(self)
        if self.notification_dialog.isVisible():
            self.notification_dialog.hide()
        else:
            self.notification_dialog.show()
            self.notification_dialog.raise_()

    def command_for(self, action):
        if action == "spotify":
            if Path("/var/lib/flatpak/app/com.spotify.Client/current/active").exists():
                return [sys.executable, str(HERE / "spotify_launcher.py")]
            return browser_command("https://open.spotify.com")
        return {
            "rocket": [sys.executable, str(HERE / "rocket.py")],
            "web": browser_command("https://start.duckduckgo.com"),
            "files": ["dolphin", str(Path.home())],
            "club": browser_command(CLUB_WEBSITE),
            "youtube": browser_command("https://www.youtube.com/"),
            "install": [sys.executable, str(HERE.parent / "installer/ui.py")],
        }[action]

    def launch(self, action):
        self.last_action = action
        if action == "apps":
            self.show_apps()
            return
        if action == "gamemodes":
            self.show_gamemodes()
            return
        if action == "settings":
            self.show_settings()
            return
        if action in ("wifi", "bluetooth", "sound"):
            self.open_device(action)
            return
        if self.preview:
            title = next((app.title for app in SHORTCUTS + GAMEMODES if app.action == action), "Installation")
            self.set_feedback(f"Vorschau: „{title}“ gewählt. Es wird keine App gestartet.")
            return False
        command = self.command_for(action)
        return self.start_application(command, action)

    def launch_application(self, application: Application):
        return self.launch(application.action)

    def start_application(self, command, action):
        command = application_command(command, action)
        if not shutil.which(command[0]):
            self.set_feedback("Diese Anwendung fehlt. Bitte die Vereinsadministration kontaktieren.")
            return False
        if action == "rocket" and any(p.property("action") == "rocket" for p in self.processes):
            return True
        process = QProcess(self)
        process.setProperty("action", action)
        process.setProperty("reported_errors", [])
        # Long-running apps must not accumulate unlimited unread stdout in Qt.
        process.setStandardOutputFile(QProcess.nullDevice())
        if action != "rocket":
            process.readyReadStandardError.connect(lambda p=process: self.app_error_output(p))
        # Qt owns only the service waiter; systemd owns the desktop application.
        self.processes.append(process)
        process.errorOccurred.connect(lambda error, p=process: self.app_failed(p, error))
        process.finished.connect(lambda code, status, p=process: self.app_finished(p, code, status))
        process.start(command[0], command[1:])
        self.set_feedback("")
        return True

    def app_failed(self, process, error):
        self.set_feedback("Die Anwendung konnte nicht gestartet werden.")
        # FailedToStart does not emit finished; stale Rocket entries prevented
        # retries forever and every failed click retained another QObject.
        if error == QProcess.ProcessError.FailedToStart:
            record_health(process.property("action"), "exit", code=127)
            if process in self.processes:
                self.processes.remove(process)
            process.deleteLater()

    def set_feedback(self, text):
        self.feedback.setText(text)
        self.feedback.hide()
        if text:
            self.notifications.add("Mitteilung", text)
        if self.music_dialog:
            self.music_dialog.set_message(text)

    def show_music(self):
        if self.music_dialog:
            self.music_dialog.raise_()
            return
        dialog = MusicPlayerDialog(self, icon)
        self.music_dialog = dialog
        def closed():
            self.music_dialog = None
            dialog.deleteLater()
            self.music_tile.expand_button.setFocus()
        dialog.finished.connect(closed)
        dialog.setScreen(self.screen())
        dialog.showFullScreen()

    def show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def show_apps(self):
        if self.apps_page is None:
            self.apps_page = AppsPage(self)
            self.pages.addWidget(self.apps_page)
        self.pages.setCurrentWidget(self.apps_page)
        self.apps_page.search.setFocus()

    def show_dashboard(self):
        previous = self.pages.currentWidget()
        self.pages.setCurrentWidget(self.dashboard)
        self.tiles["gamemodes" if previous is self.gamemodes_page else "apps"].setFocus()

    def show_gamemodes(self):
        if self.gamemodes_page is None:
            self.gamemodes_page = AppsPage(self, gamemodes=True)
            self.pages.addWidget(self.gamemodes_page)
        self.pages.setCurrentWidget(self.gamemodes_page)
        self.gamemodes_page.search.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.pages.currentWidget() in (self.apps_page, self.gamemodes_page):
            self.show_dashboard()
            event.accept()
        else:
            super().keyPressEvent(event)

    def open_device(self, action, parent=None):
        sheet = {"wifi": WifiSheet, "bluetooth": BluetoothSheet, "sound": AudioSheet,
                 "brightness": BrightnessSheet}[action](
            parent or self, self.device_client)
        sheet.exec()
        sheet.deleteLater()

    def app_error_output(self, process):
        text = bytes(process.readAllStandardError()).decode(errors="replace")
        previous = set(process.property("reported_errors") or [])
        found = error_categories(text)
        for category in found - previous:
            record_health(process.property("action"), "error", category=category)
        process.setProperty("reported_errors", sorted(previous | found))

    def app_finished(self, process, code, status):
        if code != 0 or status == QProcess.ExitStatus.CrashExit:
            detail = bytes(process.readAllStandardError()).decode(errors="replace").strip()
            self.set_feedback(detail if process.property("action") == "rocket" and detail else
                              "Die App wurde mit einem Fehler beendet. Bitte erneut versuchen.")
        if process in self.processes:
            self.processes.remove(process)
        process.deleteLater()

    def show_updates(self, parent=None):
        dialog = UpdateDialog(parent or self, self.preview)
        dialog.exec()
        dialog.deleteLater()

    def power(self, action):
        if action not in ("reboot", "poweroff"):
            raise ValueError("Unsupported power action")
        title = "Neu starten?" if action == "reboot" else "Ausschalten?"
        body = "Die Musik wird beendet. Bitte offene Dateien vorher speichern."
        dialog = QMessageBox(QMessageBox.Icon.Question, title, body, parent=self)
        confirm = dialog.addButton("Neu starten" if action == "reboot" else "Ausschalten",
                                   QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() != confirm:
            return
        self.last_action = action
        if self.preview:
            self.set_feedback(f"Vorschau: {title} bestätigt. Dieser Rechner bleibt unverändert.")
            return
        process = QProcess(self)
        self.processes.append(process)
        process.finished.connect(lambda code, status: self.set_feedback(
            "Aktion läuft …" if code == 0 else "Aktion nicht möglich. Bitte laufende Updates prüfen."))
        process.errorOccurred.connect(lambda _: self.set_feedback("Aktion konnte nicht ausgeführt werden."))
        process.start("systemctl", [action])

    def reveal(self):
        self.show_dashboard()
        if self.music_dialog:
            self.music_dialog.reject()
        self.showMaximized()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.preview:
            event.accept()
        else:
            # A closed application should not strand a nontechnical user.
            event.ignore()


STYLE = """
QWidget { font-family: "Noto Sans", "DejaVu Sans", "Segoe UI"; color: #eeece1; font-size: 14px; }
QLabel { background: transparent; }
QPushButton { background: #35372c; border: none; border-radius: 12px;
              padding: 11px 18px; font-weight: 600; min-height: 24px; outline: none; }
QPushButton:hover, QPushButton:focus { background: #50523e; }
QPushButton:pressed { background: #616347; }
QPushButton:disabled { color: #929382; background: #2c2e25; }
QPushButton#tile { background: #303329; border-radius: 18px; padding: 0; }
QPushButton#tile:hover, QPushButton#tile:focus { background: #454a36; }
QPushButton#tile:pressed { background: #53583e; }
QFrame#musicTile { background: #303329; border: none; border-radius: 18px; }
QPushButton#musicControl, QPushButton#musicPlay { padding: 0; border-radius: 10px; }
QPushButton#musicPlay { background: #a5a77a; }
QPushButton#musicPlay:hover, QPushButton#musicPlay:focus { background: #bec093; }
QPushButton#musicPlay:pressed { background: #929568; }
QPushButton#musicPlay:disabled { background: #454936; }
QPushButton#primaryTile { background: #a5a77a; border-radius: 18px; padding: 0; }
QPushButton#primaryTile:hover, QPushButton#primaryTile:focus { background: #bec093; }
QPushButton#primaryTile:pressed { background: #929568; }
QLabel#tileTitle { font-size: 24px; font-weight: 750; }
QLabel#tileSubtitle { font-size: 12px; font-weight: 400; }
QDialog, QMessageBox { background: #25281f; }
QDialog#deviceSheet { background: #25281f; border: none; border-radius: 18px; }
QFrame#settingsSidebar { background: #20231e; border-right: 1px solid #34392f; }
QFrame#settingsRail { background: #20231e; }
QScrollArea#settingsContent { background: #191e18; }
QDialog#settingsDialog QScrollBar:vertical { background: transparent; width: 6px; margin: 4px 0; }
QDialog#settingsDialog QScrollBar::handle:vertical { background: #505647; border-radius: 3px; min-height: 36px; }
QDialog#settingsDialog QScrollBar::add-line:vertical, QDialog#settingsDialog QScrollBar::sub-line:vertical { height: 0; }
QDialog#settingsDialog QScrollBar::add-page:vertical, QDialog#settingsDialog QScrollBar::sub-page:vertical { background: transparent; }
QDialog#settingsDialog QPushButton#settingsNav { padding: 6px 10px; min-height: 24px; font-size: 13px; font-weight: 400; }
QDialog#settingsDialog QPushButton#settingsNav:checked { background: #414b34; font-weight: 600; }
QDialog#settingsDialog QListWidget { background: #2c3027; padding: 4px; }
QDialog#settingsDialog QPlainTextEdit { background: #20241d; }

QDialog#settingsDialog QPushButton { padding: 10px 12px; }
QPushButton#settingsNav { background: transparent; text-align: left; border-radius: 9px;
                         border: none; }
QPushButton#settingsNav:hover, QPushButton#settingsNav:focus { background: #353b2b; }
QPushButton#settingsNav:checked { background: #3c4430; color: #f3f1e6; }
QPushButton#settingsNav:disabled { color: #929382; }
QPushButton#statusControl { background: transparent; padding: 0; min-height: 0; border-radius: 8px; }
QPushButton#statusControl:hover, QPushButton#statusControl:focus { background: #454a36; }
QPushButton#statusControl:pressed { background: #53583e; }
QLabel#notificationBadge { background: #c3b48b; color: #24261b; border-radius: 7px; font-size: 10px; font-weight: 800; }
QDialog#notificationsDialog { background: #25281f; border-radius: 18px; }
QDialog#notificationsDialog QScrollArea, QWidget#notificationList { background: #25281f; }
QFrame#notificationCard { background: #2e3328; border-radius: 12px; }
QFrame#notificationCard[unread="true"] { background: #3a4230; }
QDialog#notificationsDialog QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QDialog#notificationsDialog QScrollBar::handle:vertical { background: #59614b; border-radius: 3px; min-height: 36px; }
QDialog#notificationsDialog QScrollBar::add-line:vertical, QDialog#notificationsDialog QScrollBar::sub-line:vertical { height: 0; }
QDialog#notificationsDialog QScrollBar::add-page:vertical, QDialog#notificationsDialog QScrollBar::sub-page:vertical { background: transparent; }
QComboBox { background: #363b2e; color: #eeece1; border: none; border-radius: 6px; padding: 5px; min-height: 24px; }
QComboBox QAbstractItemView { background: #292e23; color: #eeece1; selection-background-color: #50563c; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 22px; height: 22px; }
QListWidget { background: #1e211a; border: none; border-radius: 12px; padding: 6px; outline: none; }
QListWidget::item { padding: 8px 14px; border-radius: 9px; color: #e8e6d9; }
QListWidget::item:selected { background: #50563c; color: #f3f1e6; border: none; }
QLineEdit { background: #1e211a; border: none; border-radius: 9px; padding: 12px; }
QLineEdit:focus { background: #383d2c; }
QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: #444935; }
QSlider::sub-page:horizontal { background: #a5a77a; border-radius: 4px; }
QSlider::handle:horizontal { width: 26px; margin: -10px 0; border-radius: 12px; background: #c3b48b; }
QPlainTextEdit { background: #1e211a; color: #d4d4bb; border: none;
                 border-radius: 8px; font-family: monospace; font-size: 12px; padding: 8px; }
QPushButton#confirm { background: #a5a77a; color: #24261b; }
QPushButton#confirm:hover, QPushButton#confirm:focus { background: #bec093; }
QPushButton#confirm:disabled { background: #35392b; color: #929382; }
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Disable all system actions")
    parser.add_argument("--screenshot", type=Path, help="Save a preview render and exit")
    parser.add_argument("--size", default="1280x800")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    QLocale.setDefault(QLocale("de_DE"))
    translator = QTranslator()
    if translator.load("qtbase_de", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    app.setApplicationName("saar-home")
    app.setDesktopFileName("de.saarfighters.Home")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(str(ASSETS / "home.svg")))
    server = None
    if not (args.preview or args.screenshot):
        socket = QLocalSocket()
        socket.connectToServer(SOCKET)
        if socket.waitForConnected(600):
            socket.write(b"show")
            socket.waitForBytesWritten(600)
            return 0
        QLocalServer.removeServer(SOCKET)
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(SOCKET):
            raise SystemExit("Could not create user-local launcher socket")
    window = Home(args.preview or bool(args.screenshot))
    app.aboutToQuit.connect(window.device_client.stop)
    if server:
        def reveal():
            peer = server.nextPendingConnection()
            window.reveal()
            peer.disconnectFromServer()
            peer.deleteLater()
        server.newConnection.connect(reveal)
    if args.preview or args.screenshot:
        width, height = map(int, args.size.split("x"))
        window.resize(width, height)
        window.show()
    else:
        window.showMaximized()
    if args.screenshot:
        def capture():
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.screenshot)):
                raise RuntimeError("Could not save screenshot")
            app.quit()
        QTimer.singleShot(1100, capture)
    result = app.exec()
    window.device_client.stop()
    # Dispose the widget tree while QApplication and Python callbacks are alive.
    import shiboken6
    shiboken6.delete(window)
    app.removeTranslator(translator)
    return result


if __name__ == "__main__":
    sys.exit(main())
