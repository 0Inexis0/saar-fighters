"""Bounded, asynchronous cover and lyrics loading for the native music player."""
from collections import OrderedDict
import json
from pathlib import Path
import re
import time

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QSize, Qt, QUrl, QUrlQuery, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


def remember(cache, key, value, limit=12):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)


class RemoteContent(QObject):
    def __init__(self, parent=None, limit=1024 * 1024):
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self.reply = None
        self.limit = limit

    def cancel(self):
        reply, self.reply = self.reply, None
        if reply is not None:
            reply.abort()

    def fetch(self, url, callback):
        self.cancel()
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(10000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        request.setRawHeader(b"User-Agent", b"Saar-Fighters/0.2 (https://github.com/0Inexis0/saar-fighters)")
        reply = self.network.get(request)
        self.reply = reply
        reply.setReadBufferSize(self.limit + 1)

        def bound():
            if reply.bytesAvailable() > self.limit:
                reply.abort()

        def finished():
            current = self.reply is reply
            if current:
                self.reply = None
                status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                ok = reply.error() == QNetworkReply.NetworkError.NoError and status == 200
                data = bytes(reply.readAll()) if ok else b""
                callback(data if len(data) <= self.limit else b"", status)
            reply.deleteLater()

        reply.readyRead.connect(bound)
        reply.finished.connect(finished)


def read_cover(data):
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 40_000_000:
        return QPixmap()
    reader.setAutoTransform(True)
    reader.setScaledSize(size.scaled(QSize(1024, 1024), Qt.AspectRatioMode.KeepAspectRatio))
    return QPixmap.fromImage(reader.read())


class ArtworkLoader(RemoteContent):
    changed = Signal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent, 5 * 1024 * 1024)
        self.cache = OrderedDict()
        self.url = None
        self.pixmap = QPixmap()
        self.retry_at = 0

    def load(self, url):
        url = url if isinstance(url, str) else ""
        if url == self.url and (self.reply is not None or not self.pixmap.isNull() or time.monotonic() < self.retry_at):
            return
        self.cancel()
        self.url = url
        self.pixmap = self.cache.get(url, QPixmap())
        self.changed.emit(self.pixmap)
        self.retry_at = time.monotonic() + 60
        if not url or not self.pixmap.isNull():
            return
        uri = QUrl(url)
        if uri.isLocalFile() and not uri.host():
            try:
                path = Path(uri.toLocalFile())
                if path.is_file() and path.stat().st_size <= self.limit:
                    self.received(path.read_bytes(), 200)
            except OSError:
                pass
        elif uri.scheme() in ("https", "http") and uri.host() and not uri.userInfo():
            self.fetch(url, self.received)

    def received(self, data, status):
        self.pixmap = read_cover(data) if data else QPixmap()
        if not self.pixmap.isNull():
            remember(self.cache, self.url, self.pixmap)
        self.changed.emit(self.pixmap)


TIMESTAMP = re.compile(r"\[(\d{1,3}):([0-5]\d)(?:[.:](\d{1,3}))?\]")


def parse_lrc(text):
    if not isinstance(text, str):
        return []
    text = text[:100000]
    offset = re.search(r"\[offset:([+-]?\d+)\]", text, re.I)
    shift = int(offset[1]) / 1000 if offset else 0
    lines = []
    for line in text.splitlines()[:1500]:
        stamps = list(TIMESTAMP.finditer(line))
        if not stamps:
            continue
        words = TIMESTAMP.sub("", line).strip()
        # Enhanced LRC word markers are not part of the visible lyric text.
        words = re.sub(r"<\d{1,3}:\d{2}\.\d{1,3}>", "", words)
        for stamp in stamps:
            seconds = int(stamp[1]) * 60 + int(stamp[2]) + float("0." + (stamp[3] or "0"))
            lines.append((max(0, seconds + shift), words))
    return sorted(lines, key=lambda line: line[0])[:1500]


def lyrics_result(payload):
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Lyrics konnten nicht geladen werden."}
    if payload.get("instrumental") is True:
        return {"status": "empty", "message": "Instrumental · Dieser Titel hat keinen Gesang."}
    timed = parse_lrc(payload.get("syncedLyrics"))
    plain = payload.get("plainLyrics")
    if timed:
        return {"status": "ready", "lines": timed, "synced": True}
    if isinstance(plain, str) and plain.strip():
        return {"status": "ready", "lines": [(None, line.strip()) for line in plain[:100000].splitlines()[:1500]
                                                if line.strip()], "synced": False}
    return {"status": "empty", "message": "Für diesen Titel sind noch keine Lyrics verfügbar."}


class LyricsLoader(RemoteContent):
    changed = Signal(dict)

    def __init__(self, parent=None, preview=False):
        super().__init__(parent)
        self.preview = preview
        self.key = None
        self.cache = OrderedDict()

    def load(self, state, force=False):
        key = tuple(state.get(name) for name in ("title", "artist", "album", "duration", "lyrics"))
        if key == self.key and not force:
            return
        self.cancel()
        self.key = key
        if not force and key in self.cache:
            self.changed.emit(self.cache[key])
            return
        if state.get("lyrics"):
            result = lyrics_result({"syncedLyrics": state["lyrics"], "plainLyrics": state["lyrics"]})
            self.changed.emit(dict(result, source="Vom Player"))
            return
        if self.preview:
            self.changed.emit({"status": "empty", "message": "Vorschau · Lyrics erscheinen hier beim Abspielen eines Titels."})
            return
        if not state.get("player") or not state.get("title") or not state.get("artist"):
            self.changed.emit({"status": "empty", "message": "Lyrics erscheinen, sobald Titel und Interpret verfügbar sind."})
            return
        self.changed.emit({"status": "loading", "message": "Lyrics werden geladen …"})
        query = QUrlQuery()
        query.addQueryItem("track_name", state["title"])
        query.addQueryItem("artist_name", state["artist"])
        if state.get("album"):
            query.addQueryItem("album_name", state["album"])
        if 1 <= state.get("duration", 0) <= 3600:
            query.addQueryItem("duration", str(round(state["duration"], 3)))
        url = QUrl("https://lrclib.net/api/get")
        url.setQuery(query)
        self.fetch(url, self.received)

    def received(self, data, status):
        if status == 404:
            result = {"status": "empty", "message": "Für diesen Titel sind noch keine Lyrics verfügbar."}
        elif not data:
            result = {"status": "error", "message": "Lyrics gerade nicht erreichbar. Bitte die Internetverbindung prüfen."}
        else:
            try:
                result = lyrics_result(json.loads(data))
            except (ValueError, UnicodeError):
                result = {"status": "error", "message": "Lyrics konnten nicht geladen werden."}
        result["source"] = "LRCLIB"
        if result["status"] != "error":
            remember(self.cache, self.key, result, 24)
        self.changed.emit(result)
