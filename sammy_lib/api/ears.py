"""`robot.ears` — speech-recognition facade (stub for v1)."""

from __future__ import annotations

from . import _runtime


class Ears:
    def heard(self, phrase: str) -> bool:
        return bool(_runtime.transport().call("ears", "heard", [str(phrase)]))

    def start_listening(self):
        _runtime.transport().call("ears", "start_listening")

    def stop_listening(self):
        _runtime.transport().call("ears", "stop_listening")
