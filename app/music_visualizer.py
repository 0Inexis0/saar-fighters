"""Local output-monitor analysis. Never records a microphone or writes audio to disk."""
import math
import shutil
import struct
import sys
import time

from PySide6.QtCore import QObject, QProcess, Signal


FREQUENCIES = (60, 100, 160, 250, 400, 630, 1000, 1600, 2500, 3500)


def spectrum(data):
    """Goertzel bands from a 64 ms mono s16le window at 8 kHz."""
    samples = struct.unpack('<512h', data)
    window = [sample / 32768 * (.5 - .5 * math.cos(2 * math.pi * i / 511))
              for i, sample in enumerate(samples)]
    bands = []
    for frequency in FREQUENCIES:
        coefficient = 2 * math.cos(2 * math.pi * frequency / 8000)
        a = b = 0.0
        for sample in window:
            value = sample + coefficient * a - b
            b, a = a, value
        power = max(0, a * a + b * b - coefficient * a * b)
        bands.append(min(1, math.sqrt(power) / 512 * 12))
    return bands


class OutputMonitor(QObject):
    changed = Signal(list)

    def __init__(self, parent=None, preview=False):
        super().__init__(parent)
        self.preview = preview
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.process.readAllStandardError)
        self.buffer = b''
        self.last_sample = 0
        self.failed = False
        self.process.errorOccurred.connect(self.failure)

    def failure(self, *_):
        self.failed = True

    def start(self):
        if (self.preview or self.failed or sys.platform != 'linux'
                or self.process.state() != QProcess.ProcessState.NotRunning):
            return
        executable = shutil.which('parec')
        if executable:
            self.process.start(executable, ['--device=@DEFAULT_MONITOR@', '--format=s16le',
                                           '--rate=8000', '--channels=1', '--latency-msec=64'])

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        count = len(self.buffer) // 1024
        if count:
            block = self.buffer[(count - 1) * 1024:count * 1024]
            self.buffer = self.buffer[count * 1024:]
            self.last_sample = time.monotonic()
            self.changed.emit(spectrum(block))

    def stop(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(500)
        self.buffer = b''
        self.last_sample = 0
        self.changed.emit([0.] * len(FREQUENCIES))
