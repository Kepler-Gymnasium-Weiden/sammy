"""`robot.mouth` — text-to-speech facade."""

from __future__ import annotations

from . import _runtime


class Mouth:
    def say(self, text: str):
        _runtime.transport().call("mouth", "say", [str(text)])

    def set_rate(self, words_per_minute: int):
        _runtime.transport().call("mouth", "set_rate", [int(words_per_minute)])

    def set_volume(self, value: float):
        _runtime.transport().call("mouth", "set_volume", [float(value)])

    def set_voice(self, voice_name: str):
        """Switch to a different Piper voice (e.g. 'de_DE-thorsten-medium').

        Triggers a one-time ~60 MB download if the voice isn't already cached
        in `~/.pib/voices/`. Browse the catalogue at
        https://huggingface.co/rhasspy/piper-voices.
        """
        _runtime.transport().call("mouth", "set_voice", [str(voice_name)])
