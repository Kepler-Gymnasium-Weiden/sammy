"""`robot.ears` — speech-recognition facade (stub for v1)."""

from __future__ import annotations

from . import _runtime


class Ears:
    def heard(self, phrase: str) -> bool:
        return bool(_runtime.transport().call("ears", "heard", [str(phrase)]))

    def what_did_you_hear(self) -> str:
        """Return the recently recognised speech as one string."""
        return str(_runtime.transport().call("ears", "what_did_you_hear") or "")

    def start_listening(self):
        _runtime.transport().call("ears", "start_listening")

    def stop_listening(self):
        _runtime.transport().call("ears", "stop_listening")
