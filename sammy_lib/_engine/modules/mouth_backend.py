"""Mouth (text-to-speech) backend, powered by Piper.

Piper is a fully offline neural TTS engine. We pick a default voice the first
time we run; the ~60 MB model is downloaded from Hugging Face into the user's
home directory and cached forever after. No text or audio leaves the machine
— required by the school's information-security policy.

Synthesis runs on a short-lived worker QThread; the GUI thread waits for it
inside a nested QEventLoop, so the eyes keep animating while the robot speaks.
"""

from __future__ import annotations

import io
import os
import sys
import wave
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QEventLoop, QThread

from .base import ModuleBase
from ..util.download import download_with_progress

try:
    from piper import PiperVoice  # type: ignore
    _HAVE_PIPER = True
except Exception:
    PiperVoice = None  # type: ignore
    _HAVE_PIPER = False


# ---- Voice catalogue --------------------------------------------------------

#: Curated list of Piper voices exposed in the Mouth settings tab.
#: (voice_id, human-readable label). Ordered: German first, then English.
CURATED_VOICES: list[tuple[str, str]] = [
    ("de_DE-thorsten-medium", "German — Thorsten (male)"),
    ("de_DE-thorsten-high",   "German — Thorsten HD (male)"),
    ("de_DE-eva_k-x_low",     "German — Eva K. (female, fast)"),
    ("de_DE-kerstin-low",     "German — Kerstin (female)"),
    ("de_DE-pavoque-low",     "German — Pavoque (male)"),
    ("en_US-lessac-medium",   "English (US) — Lessac (female)"),
    ("en_US-ryan-medium",     "English (US) — Ryan (male)"),
    ("en_GB-alan-medium",     "English (UK) — Alan (male)"),
]

DEFAULT_VOICE = "de_DE-thorsten-medium"
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def label_for_voice(voice_id: str) -> str:
    for vid, label in CURATED_VOICES:
        if vid == voice_id:
            return label
    return voice_id


def _voice_subdir(name: str) -> str:
    """`en_US-lessac-medium` → `en/en_US/lessac/medium`."""
    locale, speaker, quality = name.split("-", 2)
    lang = locale.split("_", 1)[0]
    return f"{lang}/{locale}/{speaker}/{quality}"


def _voices_dir() -> Path:
    root = Path(os.environ.get("PIB_VOICES_DIR", "")) if os.environ.get("PIB_VOICES_DIR") else \
        Path.home() / ".pib" / "voices"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_voice(
    name: str,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Path:
    """Download a voice's `.onnx` and `.onnx.json` if missing; return the .onnx path.

    `on_progress(filename, bytes_done, total_bytes)` is called while streaming
    the .onnx model (the big file). The accompanying .onnx.json is tiny so we
    don't bother reporting its progress.
    """
    voices = _voices_dir()
    onnx = voices / f"{name}.onnx"
    cfg = voices / f"{name}.onnx.json"
    if onnx.exists() and cfg.exists():
        return onnx
    sub = _voice_subdir(name)
    for filename in (f"{name}.onnx", f"{name}.onnx.json"):
        target = voices / filename
        if target.exists():
            continue
        url = f"{HF_BASE}/{sub}/{filename}"
        print(f"[mouth] downloading voice asset: {filename} (one-time)…", flush=True)
        cb = None
        if on_progress and filename.endswith(".onnx"):
            cb = lambda d, t, f=filename: on_progress(f, d, t)
        download_with_progress(url, target, cb)
    return onnx


# ---- Worker thread ----------------------------------------------------------

class _SpeechThread(QThread):
    """Runs Piper synthesis + audio playback off the GUI thread."""

    def __init__(self, voice, text: str, length_scale: float, parent=None):
        super().__init__(parent)
        self._voice = voice
        self._text = text
        self._length_scale = length_scale
        self.error: Optional[Exception] = None

    def run(self):
        try:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                # piper-tts 1.4+: synthesize_wav writes a complete RIFF/WAV
                # to the file object. SynthesisConfig is optional but lets us
                # control speech speed via length_scale.
                try:
                    from piper import SynthesisConfig  # type: ignore
                    cfg = SynthesisConfig(length_scale=self._length_scale)
                    self._voice.synthesize_wav(self._text, wav_file, syn_config=cfg)
                except (ImportError, TypeError):
                    self._voice.synthesize_wav(self._text, wav_file)

            wav_bytes = buf.getvalue()
            self._play(wav_bytes)
        except Exception as exc:
            self.error = exc

    @staticmethod
    def _play(wav_bytes: bytes):
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            return
        # Cross-platform fallback: write a temp wav and let the OS play it.
        import tempfile
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            path = tmp.name
        try:
            if sys.platform == "darwin":
                subprocess.run(["afplay", path], check=False)
            else:
                subprocess.run(["aplay", "-q", path], check=False)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


# ---- Backend ----------------------------------------------------------------

class MouthBackend(ModuleBase):
    name = "mouth"

    def __init__(self, voice_name: str = DEFAULT_VOICE):
        self._available = _HAVE_PIPER
        self._voice = None
        self._voice_name = voice_name
        # length_scale 1.0 = nominal speed; <1 faster, >1 slower.
        self._length_scale = 1.0
        self._volume_dummy = 1.0   # stored only; Piper has no volume knob

        if not _HAVE_PIPER:
            return
        try:
            onnx_path = _ensure_voice(self._voice_name)
            self._voice = PiperVoice.load(str(onnx_path))
        except Exception as exc:
            print(f"[mouth] piper init failed ({exc!r}); falling back to print stub")
            self._available = False
            self._voice = None

    def is_available(self) -> bool:
        return self._available and self._voice is not None

    @property
    def current_voice(self) -> str:
        return self._voice_name

    def say(self, text: str):
        text = str(text)
        if not self.is_available():
            print(f"[mouth.say (stub)] {text}")
            return

        thread = _SpeechThread(self._voice, text, self._length_scale)
        loop = QEventLoop()
        thread.finished.connect(loop.quit)
        thread.start()
        loop.exec()             # GUI keeps animating while speech plays
        thread.wait()
        if thread.error is not None:
            print(f"[mouth.say error] {thread.error!r} — text was: {text!r}")

    def set_rate(self, words_per_minute: int):
        """Roughly: 175 wpm = normal. Piper uses length_scale (inverse of speed)."""
        wpm = max(60, min(400, int(words_per_minute)))
        self._length_scale = 175.0 / wpm

    def set_volume(self, value: float):
        # Piper itself has no volume control; rely on system volume.
        self._volume_dummy = max(0.0, min(1.0, float(value)))

    def set_voice(
        self,
        voice_name: str,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ):
        """Switch to a different Piper voice. Triggers a download if not cached.

        `on_progress(filename, bytes_done, total_bytes)` is invoked during the
        one-time .onnx fetch — the settings panel uses it to drive a progress
        bar.
        """
        if not _HAVE_PIPER:
            return
        try:
            onnx_path = _ensure_voice(voice_name, on_progress)
            self._voice = PiperVoice.load(str(onnx_path))
            self._voice_name = voice_name
            self._available = True
        except Exception as exc:
            print(f"[mouth] could not switch to {voice_name}: {exc!r}")
