"""Ears (STT) settings panel: start/stop, mic picker, live transcript."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QListWidget,
    QProgressBar,
)

from ...modules.ears_backend import EarsBackend, AVAILABLE_MODELS, DEFAULT_MODEL
from ...util.download import format_bytes


class EarsSettingsPanel(QWidget):
    def __init__(self, ears: EarsBackend, parent=None):
        super().__init__(parent)
        self._ears = ears

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addWidget(QLabel("<b>Ears</b>"))

        if not self._ears.is_available():
            reason = self._ears.import_error
            if "portaudio" in reason.lower():
                detail = ("PortAudio is missing — install it with "
                          "'sudo apt install libportaudio2'.")
            elif reason:
                detail = reason
            else:
                detail = "vosk + sounddevice are unavailable."
            label = QLabel(f"Speech recognition off: {detail}\n"
                           f"heard() always returns False.")
            label.setWordWrap(True)
            root.addWidget(label)
            root.addStretch(1)
            return

        # --- Model picker --------------------------------------------------
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox()
        default_idx = 0
        for i, (label, name) in enumerate(AVAILABLE_MODELS):
            self._model_combo.addItem(label, name)
            if name == DEFAULT_MODEL:
                default_idx = i
        self._model_combo.setCurrentIndex(default_idx)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(self._model_combo, 1)
        root.addLayout(model_row)

        # --- Mic picker ----------------------------------------------------
        mic_row = QHBoxLayout()
        mic_row.addWidget(QLabel("Microphone:"))
        self._mic_combo = QComboBox()
        self._mic_combo.addItem("Default device", None)
        for index, name in EarsBackend.list_input_devices():
            self._mic_combo.addItem(f"{index}: {name}", index)
        self._mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        mic_row.addWidget(self._mic_combo, 1)
        root.addLayout(mic_row)

        # --- Start / stop --------------------------------------------------
        controls = QHBoxLayout()
        self._toggle_btn = QPushButton("Start listening")
        self._toggle_btn.clicked.connect(self._on_toggle)
        controls.addWidget(self._toggle_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self._status_label = QLabel("Status: stopped")
        self._status_label.setStyleSheet("color: #aaa; font-style: italic;")
        root.addWidget(self._status_label)

        # Hidden until a download/extract starts.
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # --- Live transcript ----------------------------------------------
        root.addWidget(QLabel("Recognised:"))
        self._log = QListWidget()
        self._log.setMaximumHeight(180)
        root.addWidget(self._log, 1)

        # Backend signals → UI updates
        self._ears.text_recognized.connect(self._on_text)
        self._ears.status_changed.connect(self._on_status)
        self._ears.download_progress.connect(self._on_download_progress)

    # ---- toggle ---------------------------------------------------------

    def _on_toggle(self):
        if self._ears.is_listening:
            self._ears.stop_listening()
        else:
            self._ears.start_listening()
        self._refresh_toggle()

    def _refresh_toggle(self):
        if self._ears.is_listening:
            self._toggle_btn.setText("Stop listening")
        else:
            self._toggle_btn.setText("Start listening")

    # ---- mic picker -----------------------------------------------------

    def _on_mic_changed(self, index: int):
        device_index = self._mic_combo.itemData(index)
        self._ears.set_device(device_index)

    # ---- model picker ---------------------------------------------------

    def _on_model_changed(self, index: int):
        model_name = self._model_combo.itemData(index)
        if model_name:
            self._ears.set_model(model_name)

    # ---- backend signal handlers ---------------------------------------

    def _on_text(self, phrase: str):
        self._log.addItem(phrase)
        # Keep the log short so it doesn't grow forever.
        while self._log.count() > 25:
            self._log.takeItem(0)
        self._log.scrollToBottom()

    def _on_status(self, status: str):
        labels = {
            "loading": "Status: loading model…",
            "listening": "Status: listening",
            "stopped": "Status: stopped",
        }
        if status.startswith("error"):
            self._status_label.setText(f"Status: error — {status[6:].strip(': ')}")
        else:
            self._status_label.setText(labels.get(status, f"Status: {status}"))
        # Hide the progress bar once we've left the loading/downloading phase.
        if status != "loading":
            self._progress.setVisible(False)
        self._refresh_toggle()

    def _on_download_progress(self, phase: str, done: int, total: int):
        self._progress.setVisible(True)
        if phase == "extract":
            # Unzip step — we don't get byte-level progress, so use the
            # indeterminate "busy" animation.
            self._progress.setRange(0, 0)
            self._progress.setFormat("Extracting…")
            return
        if total > 0:
            self._progress.setRange(0, 100)
            pct = int(done * 100 / total)
            self._progress.setValue(pct)
            self._progress.setFormat(
                f"Downloading model: {format_bytes(done)} / {format_bytes(total)}"
            )
        else:
            self._progress.setRange(0, 0)
            self._progress.setFormat(f"Downloading model: {format_bytes(done)}")
