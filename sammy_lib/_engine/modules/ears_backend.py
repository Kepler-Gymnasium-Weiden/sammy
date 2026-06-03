"""Ears (speech recognition) backend, powered by Vosk.

Vosk is a fully offline STT engine — no audio leaves the machine. We grab
microphone samples with `sounddevice`, feed them into a Vosk recognizer on a
worker thread, and keep a small rolling buffer of recently transcribed
phrases. `robot.ears.heard(phrase)` is a non-blocking check against that
buffer — when it matches, the matching entry (and anything older) is
consumed so the same utterance doesn't fire repeatedly.

Voice models are downloaded on first use (~45 MB for the small German model)
and cached in `~/.pib/vosk-models/`.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import zipfile
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .base import ModuleBase
from ..util.download import download_with_progress

try:
    import vosk  # type: ignore
    import sounddevice as sd  # type: ignore
    _HAVE_EARS = True
    _EARS_IMPORT_ERROR = ""
except Exception as _exc:
    # NOTE: importing these can fail even when the *Python* packages are
    # installed. `sounddevice` wraps the native PortAudio library, which the
    # Linux wheel does NOT bundle — without the system package the import
    # raises `OSError: PortAudio library not found` (fix: `apt install
    # libportaudio2`). Capture the real reason rather than guessing "not
    # installed", which sends people down the wrong path.
    vosk = None  # type: ignore
    sd = None  # type: ignore
    _HAVE_EARS = False
    _EARS_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"


# Vosk prints a wall of diagnostics to stderr on model load; quiet it.
if _HAVE_EARS:
    try:
        vosk.SetLogLevel(-1)
    except Exception:
        pass


# ---- Model catalogue --------------------------------------------------------

DEFAULT_MODEL = "vosk-model-small-de-0.15"
MODEL_BASE_URL = "https://alphacephei.com/vosk/models"

# Curated list shown in the settings dropdown. (label, model_name)
# Small models are ~45 MB and load fast; large ones are far more accurate
# but several hundred MB and slow to load.
AVAILABLE_MODELS: list[tuple[str, str]] = [
    ("German — small (~45 MB)",          "vosk-model-small-de-0.15"),
    ("German — Tuda+ZA (~900 MB)",       "vosk-model-de-0.21"),
    ("German — Tuda+MLS large (~4.4 GB)", "vosk-model-de-tuda-0.6-900k"),
    ("English US — small (~40 MB)",      "vosk-model-small-en-us-0.15"),
    ("English US — generic (~1.8 GB)",   "vosk-model-en-us-0.22"),
    ("English US — lgraph (~128 MB)",    "vosk-model-en-us-0.22-lgraph"),
    ("English US — Daanzu (~1.0 GB)",    "vosk-model-en-us-daanzu-20200905"),
    ("English IN — small (~40 MB)",      "vosk-model-small-en-in-0.4"),
    ("English IN — generic (~1.0 GB)",   "vosk-model-en-in-0.5"),
]


def _models_dir() -> Path:
    env = os.environ.get("PIB_VOSK_MODELS_DIR", "")
    root = Path(env) if env else Path.home() / ".pib" / "vosk-models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_model(
    name: str,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Path:
    """Download + unzip a Vosk model if not cached. Returns its directory.

    Downloads atomically (to a `.part` file first) so an interrupted run
    can't poison the cache. If a leftover zip from a previous failed run
    turns out to be unreadable, we delete it and re-download.

    `on_progress(phase, done, total)` is called with phase="download" while
    streaming bytes, and phase="extract" once before unzip starts.
    """
    root = _models_dir()
    target = root / name
    # A loaded Vosk model directory always contains a "conf" folder.
    if target.exists() and (target / "conf").exists():
        return target

    zip_path = root / f"{name}.zip"

    for attempt in (1, 2):
        if not zip_path.exists():
            part_path = root / f"{name}.zip.part"
            # Drop any leftover .part from a previous interrupted attempt.
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass
            url = f"{MODEL_BASE_URL}/{name}.zip"
            print(f"[ears] downloading {name} (one-time)...", flush=True)
            cb = (lambda d, t: on_progress("download", d, t)) if on_progress else None
            download_with_progress(url, part_path, cb)
            part_path.rename(zip_path)

        print(f"[ears] extracting {name}...", flush=True)
        if on_progress:
            on_progress("extract", 0, 0)
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(root)
            break
        except zipfile.BadZipFile:
            # Corrupt — delete and try again exactly once.
            print(f"[ears] zip was corrupt, re-downloading...", flush=True)
            try:
                zip_path.unlink()
            except OSError:
                pass
            if attempt == 2:
                raise

    try:
        zip_path.unlink()
    except OSError:
        pass
    return target


# ---- Worker thread ----------------------------------------------------------

class _ListenerThread(QThread):
    """Captures audio + runs the Vosk recognizer; emits final-result phrases."""

    text = pyqtSignal(str)
    status = pyqtSignal(str)   # "loading", "listening", "error: …"
    # (phase, bytes_done, total_bytes). phase ∈ {"download", "extract"}.
    progress = pyqtSignal(str, int, int)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 8000

    def __init__(self, model_name: str, device: Optional[int], parent=None):
        super().__init__(parent)
        self._model_name = model_name
        self._device = device
        self._running = True

    def run(self):
        try:
            self.status.emit("loading")
            model_path = _ensure_model(self._model_name, self.progress.emit)
            model = vosk.Model(str(model_path))
            recognizer = vosk.KaldiRecognizer(model, self.SAMPLE_RATE)

            audio_q: queue.Queue[bytes] = queue.Queue()

            def callback(indata, frames, time_info, status):
                # sounddevice runs this on its own audio thread.
                audio_q.put(bytes(indata))

            with sd.RawInputStream(
                samplerate=self.SAMPLE_RATE,
                blocksize=self.BLOCK_SIZE,
                dtype="int16",
                channels=1,
                device=self._device,
                callback=callback,
            ):
                self.status.emit("listening")
                while self._running:
                    try:
                        data = audio_q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        phrase = (result.get("text") or "").strip()
                        if phrase:
                            self.text.emit(phrase)
        except Exception as exc:
            self.status.emit(f"error: {exc}")
            print(f"[ears] listener crashed: {exc!r}", flush=True)

    def stop(self):
        self._running = False
        self.wait(2500)


# ---- Backend ----------------------------------------------------------------

class EarsBackend(QObject, ModuleBase):
    name = "ears"

    # Emitted whenever a new phrase has been recognised.
    text_recognized = pyqtSignal(str)
    # Emitted on listener state transitions ("loading", "listening", "stopped",
    # "error: …"). The settings panel mirrors this to a status label.
    status_changed = pyqtSignal(str)
    # (phase, bytes_done, total_bytes) — forwarded from the listener thread
    # while it downloads/unzips a model. phase ∈ {"download", "extract"}.
    download_progress = pyqtSignal(str, int, int)

    BUFFER_LIMIT = 20

    def __init__(self):
        QObject.__init__(self)
        self._listener: Optional[_ListenerThread] = None
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self._model_name = DEFAULT_MODEL
        self._device: Optional[int] = None
        self._status = "stopped"

        if not _HAVE_EARS and _EARS_IMPORT_ERROR:
            # Surface the real reason in the engine log so a missing native
            # dependency (e.g. PortAudio) isn't mistaken for "not installed".
            print(f"[ears] speech recognition disabled: {_EARS_IMPORT_ERROR}",
                  flush=True)

    # ---- ModuleBase / capability checks -----------------------------------

    def is_available(self) -> bool:
        return _HAVE_EARS

    @property
    def import_error(self) -> str:
        """Why the ears are unavailable (empty string if they're fine)."""
        return _EARS_IMPORT_ERROR

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_listening(self) -> bool:
        return self._listener is not None and self._listener.isRunning()

    # ---- Commands callable from the student API ---------------------------

    def start_listening(self):
        if not _HAVE_EARS:
            return
        if self._listener is not None:
            return
        self._listener = _ListenerThread(self._model_name, self._device)
        self._listener.text.connect(self._on_text)
        self._listener.status.connect(self._on_status)
        self._listener.progress.connect(self.download_progress)
        self._listener.finished.connect(self._on_finished)
        self._listener.start()

    def stop_listening(self):
        if self._listener is None:
            return
        listener = self._listener
        self._listener = None
        listener.stop()
        with self._lock:
            self._buffer.clear()
        self._set_status("stopped")

    def heard(self, phrase: str) -> bool:
        """Return True if `phrase` is in the rolling buffer; consume on hit.

        Auto-starts the listener on first call so students don't need to call
        start_listening() explicitly.
        """
        if not _HAVE_EARS:
            return False
        if self._listener is None:
            self.start_listening()
        wanted = str(phrase).lower().strip()
        if not wanted:
            return False
        with self._lock:
            combined = ""
            for i, text in enumerate(self._buffer):
                combined = (combined + " " + text).strip()
                if wanted in combined:
                    # Drop everything up to and including the matching slice
                    # so the same phrase doesn't keep firing.
                    del self._buffer[: i + 1]
                    return True
        return False

    def recent_phrases(self) -> list[str]:
        with self._lock:
            return list(self._buffer)

    # ---- Configuration helpers (used by the settings tab) -----------------

    def set_device(self, device_index: Optional[int]):
        if self._device == device_index:
            return
        self._device = device_index
        if self.is_listening:
            # Hot-swap microphone: restart the listener.
            self.stop_listening()
            self.start_listening()

    def set_model(self, model_name: str):
        if self._model_name == model_name:
            return
        self._model_name = model_name
        if self.is_listening:
            self.stop_listening()
            self.start_listening()

    @staticmethod
    def list_input_devices() -> list[tuple[int, str]]:
        if not _HAVE_EARS:
            return []
        try:
            devices = sd.query_devices()
        except Exception:
            return []
        result = []
        for i, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                result.append((i, dev.get("name", f"device {i}")))
        return result

    # ---- Internal --------------------------------------------------------

    def _on_text(self, phrase: str):
        with self._lock:
            self._buffer.append(phrase.lower())
            if len(self._buffer) > self.BUFFER_LIMIT:
                self._buffer.pop(0)
        self.text_recognized.emit(phrase)

    def _on_status(self, status: str):
        self._set_status(status)

    def _on_finished(self):
        # The listener QThread ended (cleanly or via error).
        if self._listener is not None and not self._listener.isRunning():
            self._listener = None
        if self._status not in {"error", "stopped"} and not self._status.startswith("error"):
            self._set_status("stopped")

    def _set_status(self, status: str):
        self._status = status
        self.status_changed.emit(status)
