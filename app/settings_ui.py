"""Olive Soft presentation for the existing, native settings controllers.

The controller-owned widgets are moved into groups without replacing their
signals, timers or busy-state controls. The standalone rescue UI stays independent.
"""
from PySide6.QtCore import Qt, QTimer, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import (QFrame, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                              QSizePolicy, QStyledItemDelegate, QStyle, QRadioButton, QCheckBox,
                              QBoxLayout)
import shiboken6


SOFT_STYLE = """
QDialog#oliveSettingsPage { background: #191e18; }
QWidget { color: #f1f4eb; font-size: 14px; }
QFrame#softGroup { background: #272e24; border: none; border-radius: 16px; }
QWidget#softRow, QWidget#softAudioRow, QWidget#softActions { background: transparent; }
QLabel#softTitle { font-size: 28px; font-weight: 600; color: #f1f4eb; }
QLabel#softSubtitle, QLabel#softCaption { color: #aebba3; font-size: 12px; }
QLabel#softSection { color: #aebba3; font-size: 12px; font-weight: 600; }
QLabel#softValue { font-size: 22px; font-weight: 500; }
QFrame#softDivider { background: #3c4736; min-height: 1px; max-height: 1px; border: none; }
QDialog#oliveSettingsPage QPushButton { background: #333d2e; color: #f1f4eb;
    border: 1px solid transparent; border-radius: 10px; padding: 10px 16px;
    min-height: 22px; font-size: 13px; font-weight: 500; }
QDialog#oliveSettingsPage QPushButton:hover { background: #414c39; }
QDialog#oliveSettingsPage QPushButton:pressed { background: #4c5941; }
QDialog#oliveSettingsPage QPushButton:focus { border: 1px solid #c3d6a2; }
QDialog#oliveSettingsPage QPushButton#confirm { background: #c3d6a2; color: #202b18; }
QDialog#oliveSettingsPage QPushButton#confirm:hover { background: #d3e4b7; }
QDialog#oliveSettingsPage QPushButton:disabled { background: #2b3127; color: #77836c; }
QDialog#oliveSettingsPage QSlider { background: transparent; min-height: 36px; }
QDialog#oliveSettingsPage QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: #46513d; }
QDialog#oliveSettingsPage QSlider::sub-page:horizontal { background: #c3d6a2; border-radius: 4px; }
QDialog#oliveSettingsPage QSlider::handle:horizontal { width: 22px; height: 22px;
    margin: -7px 0; border-radius: 11px; background: #f4f7ed; border: none; }
QDialog#oliveSettingsPage QSlider::handle:horizontal:focus { border: 2px solid #c3d6a2; }
QDialog#oliveSettingsPage QSlider::groove:horizontal:disabled { background: #353e30; }
QDialog#oliveSettingsPage QSlider::sub-page:horizontal:disabled { background: #69765a; }
QDialog#oliveSettingsPage QSlider::handle:horizontal:disabled { background: #89917f; }
QDialog#oliveSettingsPage QListWidget { background: #272e24; border: none; border-radius: 16px; padding: 4px; }
QDialog#oliveSettingsPage QListWidget::item { padding: 0; background: transparent; border: none; }
QDialog#oliveSettingsPage QCheckBox { background: transparent; spacing: 10px; }
QDialog#oliveSettingsPage QCheckBox::indicator { width: 20px; height: 20px;
    background: #191e18; border: 1px solid #59644e; border-radius: 6px; }
QDialog#oliveSettingsPage QCheckBox::indicator:checked { background: #c3d6a2; border-color: #c3d6a2; }
QDialog#oliveSettingsPage QCheckBox::indicator:focus { border: 2px solid #f4f7ed; }
QDialog#oliveSettingsPage QCheckBox::indicator:disabled { background: #353e30; border-color: #46513d; }
QDialog#oliveSettingsPage QLineEdit { background: #272e24; border: 1px solid #46513d;
    border-radius: 10px; padding: 12px 14px; selection-background-color: #414b34; }
QDialog#oliveSettingsPage QLineEdit:focus { border-color: #c3d6a2; }
QDialog#oliveSettingsPage QPlainTextEdit { background: #272e24; color: #bcc7b2;
    border: none; border-radius: 14px; padding: 16px; font-size: 12px; }
"""

TITLES = {
    "wifi": ("WLAN", "Verbinde den Rechner mit eurem Netzwerk."),
    "bluetooth": ("Bluetooth", "Lautsprecher und andere Geräte verbinden."),
    "sound": ("Ton & Lautsprecher", "Lautstärke und Wiedergabegeräte auswählen."),
    "brightness": ("Bildschirm & Helligkeit", "Helligkeit und Anzeige anpassen."),
    "energy": ("Energie & Leistung", "Die richtige Balance für euren Rechner."),
    "system": ("Systeminformationen", "Alles Wichtige über dieses Gerät."),
    "updates": ("Updates", "System, Apps und Oberfläche aktualisieren."),
    "remote": ("Fernwartung", "Zugriff für die Wartung im gleichen WLAN oder LAN."),
    "recovery": ("Wiederherstellung", "Zur vorherigen Oberfläche zurückkehren."),
    "logs": ("Systemprotokolle", "Ereignisse und Fehler dieses Starts ansehen."),
}


def text(value, name=""):
    widget = QLabel(value)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setObjectName(name)
    return widget


def panel(*widgets):
    frame = QFrame()
    frame.setObjectName("softGroup")
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    box = QVBoxLayout(frame)
    box.setContentsMargins(20, 18, 20, 18)
    box.setSpacing(12)
    for widget in widgets:
        box.addWidget(widget)
        widget.show()
    return frame


def row(title, control, description=""):
    widget = QWidget()
    widget.setObjectName("softRow")
    box = QHBoxLayout(widget)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(16)
    copy = QVBoxLayout()
    copy.setSpacing(4)
    copy.addWidget(title if isinstance(title, QWidget) else text(title))
    if description:
        copy.addWidget(text(description, "softCaption"))
    box.addLayout(copy, 1)
    box.addWidget(control, 1 if isinstance(control, QLabel) else 0)
    control.show()
    if isinstance(title, QWidget):
        title.show()
    return widget


def actions(*buttons):
    widget = QWidget()
    widget.setObjectName("softActions")
    box = QHBoxLayout(widget)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(10)
    box.addStretch()
    for button in buttons:
        button.setAutoDefault(False)
        box.addWidget(button)
        button.show()
    return widget


def section(title, widget):
    container = QWidget()
    box = QVBoxLayout(container)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(9)
    box.addWidget(text(title, "softSection"))
    box.addWidget(widget)
    widget.show()
    return container


class AudioCheckBox(QCheckBox):
    """Native checkbox semantics with an explicit, legible Soft selection mark."""
    def paintEvent(self, event):
        parent = self.parentWidget()
        while parent and not parent.property("oliveSoft"):
            parent = parent.parentWidget()
        if parent is None:
            return super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1 if self.isEnabled() else .4)
        rect = QRectF(2, (self.height() - 22) / 2, 22, 22)
        painter.setPen(QPen(QColor("#c3d6a2" if self.isChecked() else "#59644e"), 1))
        painter.setBrush(QColor("#c3d6a2" if self.isChecked() else "#191e18"))
        painter.drawRoundedRect(rect, 6, 6)
        if self.isChecked():
            painter.setPen(QPen(QColor("#202b18"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            y = self.height() // 2
            painter.drawLine(7, y, 11, y + 4)
            painter.drawLine(11, y + 4, 19, y - 5)
        if self.hasFocus():
            painter.setPen(QPen(QColor("#f4f7ed"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 7, 7)
        painter.setPen(QColor("#f1f4eb"))
        painter.drawText(self.rect().adjusted(35, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, max(1, self.width() - 37)))

    def hitButton(self, position):
        return self.rect().contains(position)


class AudioDeviceRow(QWidget):
    """Inline sliders on desktop, stacked controls in the narrow settings pane."""
    def __init__(self, check, slider):
        super().__init__()
        self.setObjectName("softAudioRow")
        self.check, self.slider = check, slider
        self.box = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.box.setContentsMargins(16, 8, 16, 8)
        self.box.setSpacing(16)
        check.setMinimumWidth(0)
        check.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        check.setMinimumHeight(32)
        self.box.addWidget(check, 3)
        self.box.addWidget(slider, 2)

    def resizeEvent(self, event):
        narrow = self.width() < 580
        self.box.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        self.box.setSpacing(2 if narrow else 16)
        super().resizeEvent(event)


class SoftListDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(3, 2, -3, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#414b34" if selected else "#272e24"))
        painter.drawRoundedRect(QRectF(rect), 11, 11)
        lines = str(index.data() or "").split("\n", 1)
        font = QFont(option.font)
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QColor("#f1f4eb"))
        title_rect = rect.adjusted(16, 10, -34, -10)
        title_rect.setHeight(24 if len(lines) > 1 else title_rect.height())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(lines[0], Qt.TextElideMode.ElideRight, title_rect.width()))
        if len(lines) > 1:
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.Normal)
            painter.setFont(font)
            painter.setPen(QColor("#aebba3"))
            detail_rect = rect.adjusted(16, 34, -34, -8)
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignVCenter,
                             painter.fontMetrics().elidedText(lines[1], Qt.TextElideMode.ElideRight, detail_rect.width()))
        if selected:
            painter.setPen(QPen(QColor("#c3d6a2"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            x, y = rect.right() - 17, rect.center().y()
            painter.drawLine(x - 5, y, x - 1, y + 4)
            painter.drawLine(x - 1, y + 4, x + 7, y - 5)
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(QColor("#c3d6a2"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 11, 11)
        painter.restore()


class AudioListDelegate(QStyledItemDelegate):
    """Rows are rendered by their accessible embedded widgets, not twice."""
    def paint(self, painter, option, index):
        if index.row() < index.model().rowCount() - 1:
            painter.save()
            painter.setPen(QColor("#3c4736"))
            painter.drawLine(option.rect.left() + 16, option.rect.bottom(),
                             option.rect.right() - 16, option.rect.bottom())
            painter.restore()


def fit_list(widget, *, audio=False):
    widget.setMinimumWidth(0)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if not audio:
        widget.setItemDelegate(SoftListDelegate(widget))
    timer = QTimer(widget)
    timer.setSingleShot(True)
    widget.soft_resize_timer = timer

    def resize():
        height = 0
        for index in range(widget.count()):
            item = widget.item(index)
            row_height = 96 if audio and widget.viewport().width() < 580 else 72
            if item.sizeHint().height() != row_height:
                item.setSizeHint(QSize(0, row_height))
            if item.toolTip() != item.text():
                item.setToolTip(item.text())
            height += max(64, item.sizeHint().height())
        widget.setFixedHeight(max(76, min(380, height + 10)))

    timer.timeout.connect(resize)
    for signal in (widget.model().rowsInserted, widget.model().rowsRemoved,
                   widget.model().dataChanged, widget.model().modelReset):
        signal.connect(lambda *_, clock=timer: clock.start(0))
    resize()


class DisplayPreview(QWidget):
    def __init__(self, slider):
        super().__init__()
        self.slider = slider
        self.setFixedHeight(142)
        self.setAccessibleName("Vorschau der Bildschirmhelligkeit")
        slider.valueChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = min(210, self.width() - 20)
        monitor = QRectF((self.width() - width) / 2, 5, width, 116)
        painter.setPen(QPen(QColor("#414b34"), 6))
        gradient = QLinearGradient(monitor.topLeft(), monitor.bottomRight())
        gradient.setColorAt(0, QColor("#687b52"))
        gradient.setColorAt(1, QColor("#253323"))
        painter.setBrush(gradient)
        painter.drawRoundedRect(monitor, 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, int((100 - self.slider.value()) * 1.4)))
        painter.drawRoundedRect(monitor.adjusted(3, 3, -3, -3), 7, 7)
        painter.setPen(QColor("#f1f4eb"))
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(monitor, Qt.AlignmentFlag.AlignCenter, "SAAR-FIGHTERS")
        painter.setPen(QPen(QColor("#414b34"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.width() // 2 - 30, 131, self.width() // 2 + 30, 131)


def _empty(layout, owner):
    """Detach, but never delete controller widgets or their signal connections."""
    while layout.count():
        item = layout.takeAt(0)
        if item.layout():
            _empty(item.layout(), owner)
            shiboken6.delete(item.layout())
        elif item.widget():
            item.widget().setParent(owner)
            item.widget().hide()


def apply_soft_settings(page, key):
    if page.property("oliveSoft"):
        return
    page.setProperty("oliveSoft", True)
    page.setObjectName("oliveSettingsPage")
    page.setStyleSheet(SOFT_STYLE)
    body = page.layout()
    _empty(body, page)
    body.setContentsMargins(28, 28, 28, 28)
    body.setSpacing(20)
    for button in page.findChildren(QRadioButton):
        button.setProperty("oliveSoft", True)
    title, description = TITLES[key]
    header = QWidget()
    header_box = QVBoxLayout(header)
    header_box.setContentsMargins(0, 0, 0, 4)
    header_box.setSpacing(8)
    header_box.addWidget(text(title, "softTitle"))
    header_box.addWidget(text(description, "softSubtitle"))
    body.addWidget(header)

    if key in ("wifi", "bluetooth"):
        body.addWidget(panel(row(title, page.toggle, "Netzwerke verbinden" if key == "wifi" else "Geräte verbinden")))
        body.addWidget(row(text("Netzwerke" if key == "wifi" else "Geräte", "softSection"), page.scan))
        fit_list(page.list)
        body.addWidget(page.list)
        page.list.show()
        if key == "wifi":
            body.addWidget(page.password)
        body.addWidget(actions(page.connect))
        page.connect.setObjectName("confirm")
        page.selection()
    elif key == "sound":
        page.level.setStyleSheet("font-size: 16px; font-weight: 500;")
        body.addWidget(panel(page.level, page.slider, row("Ton", page.mute)))
        body.addWidget(panel(row("Automatisch wechseln", page.auto_audio, "Bei einer neuen Bluetooth-Audioverbindung")))
        fit_list(page.list, audio=True)
        body.addWidget(section("Wiedergabegeräte · Mehrfachauswahl möglich", page.list))
        page.reload.setText("Neu laden")
        body.addWidget(actions(page.reload, page.choose))
    elif key == "brightness":
        fit_list(page.list)
        body.addWidget(panel(DisplayPreview(page.slider), page.list))
        page.level.setStyleSheet("font-size: 17px; font-weight: 500;")
        body.addWidget(panel(page.level, page.slider))
        body.addWidget(actions(page.reload, page.advanced))
    elif key == "energy":
        body.addWidget(section("Leistungsprofil", panel(page.profile)))
        body.addWidget(page.availability)
        page.availability.setVisible(bool(page.availability.text()))
        body.addWidget(actions(page.advanced))
    elif key == "system":
        page.soft_info = {}
        fields = (("version", "Oberflächenstand"), ("kernel", "Kernel"), ("architecture", "Architektur"),
                  ("memory", "Arbeitsspeicher"), ("disk", "Systemlaufwerk"), ("last_update", "Letztes erfolgreiches Systemupdate"))
        for heading, subset in (("System", fields[:3]), ("Speicher", fields[3:5]), ("Aktualisierung", fields[5:])):
            rows = []
            for field, name in subset:
                value = text("", "softCaption")
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                page.soft_info[field] = value
                rows.append(row(name, value))
            body.addWidget(section(heading, panel(*rows)))
        page.refresh()
    elif key == "updates":
        body.addWidget(panel(text("System aktualisieren"), text("Systempakete, Anwendungen und Saar-Fighters-Oberfläche.", "softCaption")))
        body.addWidget(actions(page.start))
        body.addWidget(page.output)
        page.output.setMinimumHeight(180)
    elif key == "remote":
        page.summary.setStyleSheet("font-size: 14px; font-weight: 500;")
        body.addWidget(panel(row(page.summary, page.action, "Fernwartung im lokalen Netzwerk")))
        page.soft_details_group = panel(page.details)
        body.addWidget(page.soft_details_group)
        page.soft_details_group.setVisible(bool(page.details.text()))
        page.details.setVisible(bool(page.details.text()))
        body.addWidget(page.notice)
        page.notice.setVisible(bool(page.notice.text()) and page.snapshot.get("live", False))
    elif key == "recovery":
        page.summary.setStyleSheet("font-size: 20px; font-weight: 500;")
        body.addWidget(panel(page.summary, page.details))
        body.addWidget(text("Persönliche Dateien, Browserprofile und Systempakete bleiben erhalten.", "softCaption"))
        body.addWidget(page.notice)
        page.notice.setVisible(bool(page.notice.text()))
        page.action.setText("Wiederherstellen")
        page.action.setObjectName("confirm")
        body.addWidget(actions(page.reload, page.action))
        body.addWidget(page.output)
    elif key == "logs":
        body.addWidget(page.source)
        page.source.show()
        body.addWidget(page.output)
        page.output.setMinimumHeight(240)
        page.output.show()
        body.addWidget(actions(page.reload, page.export))
    message = getattr(page, "message", getattr(page, "state", None))
    if message is not None:
        body.addWidget(message)
        message.setVisible(bool(message.text()))
    body.addStretch(1)
