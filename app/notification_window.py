"""Standalone notification inbox for the dashboard bell."""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from devices import NoticeLabel, label


class NotificationsDialog(QDialog):
    def __init__(self, home):
        super().__init__(home)
        self.center = home.notifications
        self.setWindowTitle("Mitteilungen")
        self.setObjectName("notificationsDialog")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(min(home.width() - 32, 580), min(home.height() - 32, 640))
        body = QVBoxLayout(self)
        body.setContentsMargins(24, 24, 24, 24)
        body.setSpacing(18)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.addWidget(label("Mitteilungen", "font-size: 26px; font-weight: 700;"))
        self.summary = label("", "color: #b9b8a7; font-size: 12px;")
        heading.addWidget(self.summary)
        header.addLayout(heading, 1)
        self.close_button = QPushButton("Schließen")
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        body.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setAccessibleName("Mitteilungsverlauf")
        body.addWidget(self.scroll, 1)
        self.message = NoticeLabel()
        body.addWidget(self.message)

        actions = QHBoxLayout()
        self.read_button = QPushButton("Alle als gelesen markieren")
        self.read_button.setAutoDefault(False)
        self.read_button.clicked.connect(self.center.mark_read)
        actions.addWidget(self.read_button)
        self.clear_button = QPushButton("Verlauf leeren")
        self.clear_button.setAutoDefault(False)
        self.clear_button.clicked.connect(self.center.clear)
        actions.addWidget(self.clear_button)
        body.addLayout(actions)
        self.center.changed.connect(self.refresh)
        self.refresh()
        self.close_button.setFocus()

    def refresh(self):
        position = self.scroll.verticalScrollBar().value()
        unread = self.center.unread
        self.summary.setText(f"{unread} ungelesen" if unread else "Alles gelesen")
        self.read_button.setEnabled(unread > 0)
        self.clear_button.setEnabled(bool(self.center.items))
        self.message.setText(self.center.storage_error)
        content = QWidget()
        content.setObjectName("notificationList")
        rows = QVBoxLayout(content)
        rows.setContentsMargins(0, 0, 8, 0)
        rows.setSpacing(10)
        self.cards = []
        if not self.center.items:
            self.summary.setText("Meldungen zu Geräten und Updates")
            rows.addStretch()
            empty = label("Keine Mitteilungen", "font-size: 18px; font-weight: 600;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rows.addWidget(empty)
            detail = label("Neue Meldungen erscheinen hier.", "color: #b9b8a7;")
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rows.addWidget(detail)
        for item in reversed(self.center.items):
            card = QFrame()
            card.setObjectName("notificationCard")
            card.setProperty("unread", not item["read"])
            entry = QVBoxLayout(card)
            entry.setContentsMargins(16, 14, 16, 14)
            entry.setSpacing(6)
            try:
                timestamp = datetime.fromisoformat(item["time"]).astimezone().strftime("%d.%m.%Y · %H:%M")
            except ValueError:
                timestamp = item["time"]
            entry.addWidget(label(("Neu · " if not item["read"] else "") + timestamp,
                                  "color: #c3b48b; font-size: 11px;"))
            entry.addWidget(label(item["title"], "font-size: 16px; font-weight: 600;"))
            detail = label(item["body"], "color: #d0d0c1;")
            detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            entry.addWidget(detail)
            rows.addWidget(card)
            self.cards.append(card)
        rows.addStretch()
        self.scroll.setWidget(content)
        self.scroll.verticalScrollBar().setValue(position)
