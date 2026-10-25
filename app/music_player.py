"""Expanded, touch-friendly now-playing view shared with the desktop tile."""
from bisect import bisect_right
import time

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFrame, QHBoxLayout, QLabel,
                              QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
                              QSlider, QStyledItemDelegate, QVBoxLayout, QWidget)
from media_content import LyricsLoader


class ArtworkView(QWidget):
    clicked = Signal()

    def __init__(self, icon, parent=None, clickable=False):
        super().__init__(parent)
        self.image = QPixmap()
        self.symbol = icon("music", "#b6b393", 64)
        self.clickable = clickable
        self.fill_tile = False
        self.setAccessibleName("Titelbild")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setAccessibleName("Musikplayer aufklappen")
            self.setToolTip("Musikplayer aufklappen")

    def set_image(self, image):
        self.image = image
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(box, min(16, self.width() / 6), min(16, self.width() / 6))
        painter.setClipPath(path)
        painter.fillRect(box, QColor("#363a30"))
        if not self.image.isNull():
            # The tile fills its entire surface; the large player preserves video aspect ratios.
            fitted = self.image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding if self.fill_tile
                                       else Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width() - fitted.width()) // 2,
                               (self.height() - fitted.height()) // 2, fitted)
        else:
            size = min(64, int(self.width() * .45))
            self.symbol.paint(painter, (self.width() - size) // 2, (self.height() - size) // 2, size, size)
        if self.fill_tile:
            shade = QLinearGradient(0, 0, 0, self.height())
            shade.setColorAt(0, QColor(8, 12, 9, 135))
            shade.setColorAt(.3, QColor(8, 12, 9, 25))
            shade.setColorAt(.58, QColor(8, 12, 9, 85))
            shade.setColorAt(1, QColor(8, 12, 9, 235))
            painter.fillRect(box, shade)
        if self.hasFocus():
            painter.setClipping(False)
            painter.setPen(QColor("#c3b48b"))
            painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), 10, 10)

    def mouseReleaseEvent(self, event):
        if self.clickable and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.clickable and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class PlayerSlider(QSlider):
    committed = Signal(int)

    def __init__(self, name, maximum=100):
        super().__init__(Qt.Orientation.Horizontal)
        self.setAccessibleName(name)
        self.setRange(0, maximum)
        self.setMinimumHeight(32)
        self.delay = QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.setInterval(350)
        self.delay.timeout.connect(self.commit)
        self.sliderReleased.connect(self.commit)
        self.valueChanged.connect(self.schedule)

    def schedule(self):
        if not self.isSliderDown():
            self.delay.start()

    def commit(self):
        self.delay.stop()
        if self.isEnabled():
            self.committed.emit(self.value())

    def reflect(self, value):
        if not self.isSliderDown() and not self.delay.isActive():
            self.blockSignals(True)
            self.setValue(value)
            self.blockSignals(False)


class LyricDelegate(QStyledItemDelegate):
    """Draw plain lyric text without the launcher's global list selection colors."""
    def paint(self, painter, option, index):
        painter.save()
        painter.setFont(index.data(Qt.ItemDataRole.FontRole))
        painter.setPen(index.data(Qt.ItemDataRole.ForegroundRole).color())
        painter.drawText(option.rect.adjusted(8, 13, -8, -13),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                         index.data())
        painter.restore()

    def sizeHint(self, option, index):
        from PySide6.QtGui import QFontMetrics
        width = max(100, self.parent().viewport().width() - 16)
        metrics = QFontMetrics(index.data(Qt.ItemDataRole.FontRole))
        bounds = metrics.boundingRect(QRect(0, 0, width, 100000), Qt.TextFlag.TextWordWrap, index.data())
        return QSize(width + 16, bounds.height() + 26)


def text_label(text="", size=14, color="#eeece1", bold=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setStyleSheet(f"background: transparent; color: {color}; font-size: {size}px; font-weight: {700 if bold else 400};")
    return widget


def clock_text(seconds):
    if seconds is None:
        return "--:--"
    seconds = max(0, int(seconds))
    return f"{seconds // 3600}:{seconds % 3600 // 60:02}:{seconds % 60:02}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02}"


class MusicPlayerDialog(QDialog):
    def __init__(self, home, icon):
        super().__init__(home)
        self.home = home
        self.icon = icon
        self.state = {}
        self.sample_time = time.monotonic()
        self.track_key = None
        self.seek_identity = None
        self.volume_player = None
        self.lines = []
        self.synced = False
        self.active_line = -1
        self.follow_after = 0
        self.tint = QColor("#464936")
        self.setObjectName("expandedMusicPlayer")
        self.setWindowTitle("Musikplayer · Saar-Fighters")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.resize(home.size())
        self.setMinimumSize(760, 500)
        self.setStyleSheet("""
            QDialog#expandedMusicPlayer { background: #22261f; }
            QPushButton#transport { background: transparent; padding: 0; border-radius: 22px; min-height: 44px; max-height: 44px; }
            QPushButton#transport:hover, QPushButton#transport:focus { background: #545847; }
            QPushButton#transport:checked { background: #62684b; }
            QPushButton#transport:disabled { background: transparent; }
            QPushButton#largePlay { background: #eeece1; border-radius: 30px; padding: 0; min-height: 60px; max-height: 60px; }
            QPushButton#largePlay:hover, QPushButton#largePlay:focus { background: #ffffff; }
            QPushButton#largePlay:disabled { background: #565b4c; }
            QListWidget#lyrics { background: transparent; border: none; padding: 0; outline: none; }
            QListWidget#lyrics::item { background: transparent; padding: 13px 8px; border: none; }
            QListWidget#lyrics::item:hover { background: #3d4335; border-radius: 10px; }
            QScrollBar:vertical { width: 7px; background: transparent; }
            QScrollBar::handle:vertical { background: #626653; border-radius: 3px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(32, 20, 32, 24)
        self.root.setSpacing(16)
        top = QHBoxLayout()
        self.close_button = QPushButton("  Einklappen")
        self.close_button.setIcon(icon("collapse", size=18))
        self.close_button.setAccessibleName("Musikplayer einklappen")
        self.close_button.clicked.connect(self.reject)
        top.addWidget(self.close_button)
        top.addStretch()
        self.source = text_label("JETZT LÄUFT", 12, "#c2c5b4", True)
        top.addWidget(self.source)
        self.root.addLayout(top)
        body = QHBoxLayout()
        body.setSpacing(46)
        self.root.addLayout(body, 1)
        left = QWidget()
        left.setMinimumWidth(290)
        left.setMaximumWidth(470)
        player = QVBoxLayout(left)
        player.setContentsMargins(0, 0, 0, 0)
        player.setSpacing(10)
        player.addStretch()
        self.artwork = ArtworkView(icon)
        player.addWidget(self.artwork, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = text_label(size=26, bold=True)
        self.artist = text_label(size=17, color="#bdc2ae")
        for label in (self.title, self.artist):
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            player.addWidget(label)
        self.position = PlayerSlider("Wiedergabeposition", 1000)
        self.position.sliderPressed.connect(self.capture_seek)
        self.position.actionTriggered.connect(lambda _: self.capture_seek())
        self.position.committed.connect(self.seek)
        player.addWidget(self.position)
        times = QHBoxLayout()
        self.elapsed = text_label("0:00", 11, "#bdc2ae")
        self.remaining = text_label("--:--", 11, "#bdc2ae")
        times.addWidget(self.elapsed)
        times.addStretch()
        times.addWidget(self.remaining)
        player.addLayout(times)
        transport = QHBoxLayout()
        transport.setSpacing(12)
        self.buttons = {}
        for name, title, symbol in (("shuffle", "Zufallswiedergabe", "shuffle"),
                                     ("previous", "Vorheriger Titel", "previous"),
                                     ("playpause", "Play", "play"),
                                     ("next", "Nächster Titel", "next"),
                                     ("repeat", "Wiederholen", "repeat")):
            button = QPushButton()
            button.setObjectName("largePlay" if name == "playpause" else "transport")
            size = 60 if name == "playpause" else 44
            button.setFixedSize(size, size)
            button.setIcon(icon(symbol, "#24261b" if name == "playpause" else "#eeece1", 24))
            button.setIconSize(QSize(24, 24))
            button.setAccessibleName(title)
            button.setToolTip(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoDefault(False)
            if name in ("shuffle", "repeat"):
                button.setCheckable(True)
            button.clicked.connect(lambda checked=False, action=name: self.control(action))
            transport.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
            self.buttons[name] = button
        player.addLayout(transport)
        volume_row = QHBoxLayout()
        volume_icon = QLabel()
        volume_icon.setPixmap(icon("sound", "#bdc2ae", 18).pixmap(QSize(18, 18)))
        volume_row.addWidget(volume_icon)
        self.volume = PlayerSlider("Player-Lautstärke")
        self.volume.sliderPressed.connect(self.capture_volume)
        self.volume.actionTriggered.connect(lambda _: self.capture_volume())
        self.volume.committed.connect(lambda value: self.send("volume", value=value,
                                                             player=self.volume_player or self.state.get("player")))
        volume_row.addWidget(self.volume, 1)
        self.volume_value = text_label("", 11, "#bdc2ae")
        self.volume_value.setFixedWidth(38)
        volume_row.addWidget(self.volume_value)
        player.addLayout(volume_row)
        player.addStretch()
        body.addWidget(left, 1)
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background: #555b45;")
        body.addWidget(divider)
        right = QVBoxLayout()
        right.setSpacing(12)
        lyric_heading = QHBoxLayout()
        lyric_heading.addWidget(text_label("Lyrics", 21, bold=True))
        lyric_heading.addStretch()
        self.follow_button = QPushButton("Aktuelle Zeile")
        self.follow_button.setAutoDefault(False)
        self.follow_button.clicked.connect(self.resume_follow)
        self.follow_button.hide()
        lyric_heading.addWidget(self.follow_button)
        right.addLayout(lyric_heading)
        self.lyric_hint = text_label("", 12, "#bdc2ae")
        self.lyric_hint.setWordWrap(True)
        right.addWidget(self.lyric_hint)
        self.lyrics = QListWidget()
        self.lyrics.setObjectName("lyrics")
        self.lyrics.setAccessibleName("Songtext")
        self.lyrics.setWordWrap(True)
        self.lyrics.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lyrics.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lyrics.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.lyrics.setSpacing(4)
        self.lyrics.setItemDelegate(LyricDelegate(self.lyrics))
        self.lyrics.viewport().installEventFilter(self)
        self.lyrics.installEventFilter(self)
        self.lyrics.verticalScrollBar().sliderPressed.connect(self.pause_follow)
        self.lyrics.itemClicked.connect(self.seek_line)
        self.lyrics.itemActivated.connect(self.seek_line)
        right.addWidget(self.lyrics, 1)
        self.empty = text_label(size=23, color="#c8cbbd", bold=True)
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.empty, 1)
        self.retry = QPushButton("Erneut laden")
        self.retry.setAutoDefault(False)
        self.retry.clicked.connect(lambda: self.loader.load(self.state, force=True))
        self.retry.hide()
        right.addWidget(self.retry, 0, Qt.AlignmentFlag.AlignLeft)
        self.attribution = text_label("", 11, "#a2aa95")
        right.addWidget(self.attribution)
        body.addLayout(right, 1)
        self.message = text_label(size=12, color="#e1cba0")
        self.message.setWordWrap(True)
        self.message.hide()
        self.root.addWidget(self.message)
        self.loader = LyricsLoader(self, preview=home.preview)
        self.loader.changed.connect(self.set_lyrics)
        home.artwork_loader.changed.connect(self.set_artwork)
        self.set_artwork(home.artwork_loader.pixmap)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.finished.connect(self.cleanup)
        self.update_state(home.media_state)

    def cleanup(self):
        self.timer.stop()
        self.loader.cancel()
        self.volume.delay.stop()
        self.position.delay.stop()

    def set_artwork(self, pixmap):
        self.artwork.set_image(pixmap)
        if pixmap.isNull():
            self.tint = QColor("#464936")
        else:
            small = pixmap.toImage().scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
            self.tint = small.pixelColor(0, 0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, self.tint.darker(230))
        gradient.setColorAt(1, QColor("#20251f"))
        painter.fillRect(self.rect(), gradient)

    def resizeEvent(self, event):
        compact = self.height() < 650
        self.root.setContentsMargins(24 if compact else 40, 16 if compact else 24,
                                    24 if compact else 40, 16 if compact else 28)
        self.root.setSpacing(8 if compact else 20)
        side = max(130, min(340, self.height() - 380, int(self.width() * .34)))
        self.artwork.setFixedSize(side, side)
        self.lyrics.doItemsLayout()
        self.update_labels()
        super().resizeEvent(event)

    def update_labels(self):
        for label, value in ((self.title, self.state.get("title") or "Bereit für Musik"),
                             (self.artist, self.state.get("artist") or "Spotify oder YouTube öffnen")):
            label.setText(label.fontMetrics().elidedText(value, Qt.TextElideMode.ElideRight, label.width()))
            label.setToolTip(value)
            label.setAccessibleName(value)

    def update_state(self, data, error=None):
        state = data if not error else {}
        key = tuple(state.get(name) for name in ("player", "track_id", "title", "artist"))
        if key != self.track_key:
            self.track_key = key
            self.seek_identity = None
            self.position.delay.stop()
            self.position.setSliderDown(False)
            self.follow_after = 0
        self.state = dict(state)
        self.sample_time = time.monotonic()
        self.update_labels()
        playing = bool(state.get("playing"))
        source = state.get("player_name", "Kein Player")
        self.source.setText(f"{source} · {'Läuft' if playing else 'Pausiert' if state.get('player') else 'Keine Wiedergabe'}")
        for name, button in self.buttons.items():
            button.setEnabled(bool(state.get("available" if name == "playpause" else "can_" + name)))
        play = self.buttons["playpause"]
        play.setIcon(self.icon("pause" if playing else "play", "#24261b", 26))
        play.setAccessibleName("Pause" if playing else "Play")
        play.setToolTip(play.accessibleName())
        self.buttons["shuffle"].setChecked(bool(state.get("shuffle")))
        self.buttons["shuffle"].setToolTip("Zufallswiedergabe " + ("ausschalten" if state.get("shuffle") else "einschalten"))
        repeat = state.get("repeat", "None")
        self.buttons["repeat"].setChecked(repeat != "None")
        repeat_name = {"None": "Wiederholen aus", "Playlist": "Wiedergabeliste wiederholen", "Track": "Titel wiederholen"}.get(repeat, "Wiederholen")
        self.buttons["repeat"].setToolTip(repeat_name)
        self.buttons["repeat"].setAccessibleName(repeat_name)
        self.buttons["repeat"].setIcon(self.icon("repeat_one" if repeat == "Track" else "repeat", size=24))
        self.position.setEnabled(bool(state.get("can_seek")))
        self.volume.setEnabled(bool(state.get("can_volume")))
        self.volume.reflect(int(state.get("volume", 0)))
        self.volume_value.setText(f"{state.get('volume', 0)} %" if state.get("can_volume") else "")
        self.volume.setToolTip("Player-Lautstärke" if state.get("can_volume") else "Dieser Player meldet keine Lautstärkesteuerung.")
        self.loader.load(state)
        if error:
            self.set_message(error)
        if self.home.quick_busy["media"]:
            self.set_busy()
        self.tick()

    def current_position(self):
        position = self.state.get("position")
        if position is None:
            return None
        if self.state.get("playing"):
            position += (time.monotonic() - self.sample_time) * self.state.get("rate", 1)
        duration = self.state.get("duration", 0)
        return min(position, duration) if duration else position

    def tick(self):
        position = self.current_position()
        duration = self.state.get("duration", 0)
        if self.position.isSliderDown() or self.position.delay.isActive():
            visible_position = self.position.value() / 1000 * duration
        else:
            visible_position = position
            self.position.reflect(round(position / duration * 1000) if position is not None and duration else 0)
        self.elapsed.setText(clock_text(visible_position))
        self.remaining.setText("-" + clock_text(duration - visible_position)
                               if duration and visible_position is not None else clock_text(duration or None))
        self.position.setAccessibleDescription(f"{clock_text(visible_position)} von {clock_text(duration or None)}")
        if not self.synced or position is None:
            return
        active = bisect_right([stamp for stamp, _ in self.lines], position) - 1
        if active != self.active_line:
            self.active_line = active
            for index in range(self.lyrics.count()):
                self.lyrics.item(index).setForeground(QColor("#fffdf2" if index == active else "#929b86"))
            if time.monotonic() >= self.follow_after:
                self.scroll_active()
        if self.follow_after and time.monotonic() >= self.follow_after:
            self.resume_follow()

    def set_lyrics(self, result):
        self.lines = result.get("lines", [])
        self.synced = result.get("synced", False)
        self.active_line = -1
        self.lyrics.clear()
        self.lyrics.setVisible(bool(self.lines))
        self.empty.setVisible(not self.lines)
        self.empty.setText(result.get("message", ""))
        self.retry.setVisible(result.get("status") == "error")
        self.lyric_hint.setText("Die aktuelle Zeile folgt der Musik." if self.synced and self.state.get("position") is not None else
                                "Der Player meldet keine Wiedergabeposition." if self.synced else
                                "Songtext ohne Zeitmarken" if self.lines else "")
        self.attribution.setText("Lyrics · " + result["source"] if result.get("source") else "")
        for _, words in self.lines:
            item = QListWidgetItem(words or "♪")
            font = QFont(self.font())
            font.setPixelSize(25 if self.width() >= 1000 else 22)
            font.setBold(True)
            item.setFont(font)
            item.setForeground(QColor("#d6dbcc" if not self.synced else "#929b86"))
            self.lyrics.addItem(item)
        self.follow_button.hide()
        self.tick()
        QTimer.singleShot(0, self, self.scroll_active)

    def pause_follow(self):
        if self.synced:
            self.follow_after = time.monotonic() + 8
            self.follow_button.show()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Wheel, QEvent.Type.TouchBegin, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            self.pause_follow()
        return super().eventFilter(watched, event)

    def scroll_active(self):
        if 0 <= self.active_line < self.lyrics.count():
            self.lyrics.scrollToItem(self.lyrics.item(self.active_line), QAbstractItemView.ScrollHint.PositionAtCenter)

    def resume_follow(self):
        self.follow_after = 0
        self.follow_button.hide()
        self.scroll_active()

    def capture_seek(self):
        self.seek_identity = (self.state.get("player"), self.state.get("track_id"), self.state.get("duration", 0))

    def capture_volume(self):
        self.volume_player = self.state.get("player")

    def seek(self, value):
        if self.seek_identity:
            player, track_id, duration = self.seek_identity
            self.send("seek", position=value / 1000 * duration, track_id=track_id, player=player)

    def seek_line(self, item):
        if self.synced and self.state.get("can_seek"):
            position = self.lines[self.lyrics.row(item)][0]
            if position <= self.state.get("duration", 0):
                self.send("seek", position=position, track_id=self.state.get("track_id"))

    def control(self, action):
        options = {}
        if action == "shuffle":
            options["value"] = not self.state.get("shuffle", False)
        elif action == "repeat":
            options["value"] = {"None": "Playlist", "Playlist": "Track", "Track": "None"}.get(self.state.get("repeat"), "Playlist")
        self.send(action, **options)

    def send(self, action, **options):
        self.home.quick_action("media", action, **options)

    def set_busy(self):
        for button in self.buttons.values():
            button.setEnabled(False)
        self.position.setEnabled(False)
        self.volume.setEnabled(False)

    def set_message(self, text):
        self.message.setText(text)
        self.message.setVisible(bool(text))
