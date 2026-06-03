"""Mouth (TTS) settings panel — voice picker, speed, volume, test phrase."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QLineEdit,
    QComboBox,
    QProgressBar,
)

from ...modules.mouth_backend import (
    MouthBackend,
    CURATED_VOICES,
    label_for_voice,
)
from ...util.download import format_bytes


class _VoiceSwitchThread(QThread):
    """Runs `mouth.set_voice` off the GUI thread so a first-time download
    (~60 MB) doesn't freeze the window."""

    failed = pyqtSignal(str)
    # (filename, bytes_done, total_bytes)
    progress = pyqtSignal(str, int, int)

    def __init__(self, mouth: MouthBackend, voice_id: str, parent=None):
        super().__init__(parent)
        self._mouth = mouth
        self._voice_id = voice_id

    def run(self):
        try:
            self._mouth.set_voice(self._voice_id, self.progress.emit)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MouthSettingsPanel(QWidget):
    def __init__(self, mouth: MouthBackend, parent=None):
        super().__init__(parent)
        self._mouth = mouth
        self._switch_thread: _VoiceSwitchThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addWidget(QLabel("<b>Mouth</b>"))

        if not self._mouth.is_available():
            root.addWidget(QLabel("piper-tts not available — say() prints to console."))

        # --- Voice picker ---------------------------------------------------
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice:"))
        self._voice_combo = QComboBox()
        for vid, label in CURATED_VOICES:
            self._voice_combo.addItem(label, vid)
        # Select current voice
        current = self._mouth.current_voice
        for i in range(self._voice_combo.count()):
            if self._voice_combo.itemData(i) == current:
                self._voice_combo.setCurrentIndex(i)
                break
        # Connect AFTER setting initial index so we don't fire on first paint.
        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        voice_row.addWidget(self._voice_combo, 1)
        root.addLayout(voice_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #aaa; font-style: italic;")
        root.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # --- Rate / volume sliders -----------------------------------------
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Rate:"))
        self._rate = QSlider(Qt.Orientation.Horizontal)
        self._rate.setRange(80, 280)
        self._rate.setValue(175)
        self._rate.valueChanged.connect(self._mouth.set_rate)
        rate_row.addWidget(self._rate, 1)
        root.addLayout(rate_row)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume:"))
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setRange(0, 100)
        self._vol.setValue(100)
        self._vol.valueChanged.connect(lambda v: self._mouth.set_volume(v / 100.0))
        vol_row.addWidget(self._vol, 1)
        root.addLayout(vol_row)

        # --- Test phrase ---------------------------------------------------
        test_row = QHBoxLayout()
        self._test_text = QLineEdit("Hello, I am the robot.")
        test_row.addWidget(self._test_text, 1)
        self._test_btn = QPushButton("Speak")
        self._test_btn.clicked.connect(lambda: self._mouth.say(self._test_text.text()))
        test_row.addWidget(self._test_btn)
        root.addLayout(test_row)

        root.addStretch(1)

    # ---- voice switching ----------------------------------------------

    def _on_voice_changed(self, index: int):
        voice_id = self._voice_combo.itemData(index)
        if not voice_id or voice_id == self._mouth.current_voice:
            return
        label = label_for_voice(voice_id)
        self._status.setText(f"Loading voice “{label}” …")
        self._voice_combo.setEnabled(False)
        self._test_btn.setEnabled(False)

        self._switch_thread = _VoiceSwitchThread(self._mouth, voice_id, self)
        self._switch_thread.failed.connect(self._on_switch_failed)
        self._switch_thread.progress.connect(self._on_switch_progress)
        self._switch_thread.finished.connect(self._on_switch_finished)
        self._switch_thread.start()

    def _on_switch_failed(self, message: str):
        self._status.setText(f"Error: {message}")

    def _on_switch_progress(self, filename: str, done: int, total: int):
        self._progress.setVisible(True)
        if total > 0:
            self._progress.setRange(0, 100)
            pct = int(done * 100 / total)
            self._progress.setValue(pct)
            self._progress.setFormat(
                f"Downloading voice: {format_bytes(done)} / {format_bytes(total)}"
            )
        else:
            self._progress.setRange(0, 0)
            self._progress.setFormat(f"Downloading voice: {format_bytes(done)}")

    def _on_switch_finished(self):
        # If `_on_switch_failed` already wrote a message, leave it.
        if not self._status.text().startswith("Error"):
            self._status.setText(f"Active voice: {label_for_voice(self._mouth.current_voice)}")
        self._progress.setVisible(False)
        self._voice_combo.setEnabled(True)
        self._test_btn.setEnabled(True)
        self._switch_thread = None
