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

    def pause_listening(self):
        """Stop listening but keep the model loaded so resume is instant.

        Use while the robot is talking so it doesn't hear itself. Discards any
        speech heard so far; resume_listening() picks back up with no reload.
        """
        _runtime.transport().call("ears", "pause_listening")

    def resume_listening(self):
        """Resume listening after pause_listening()."""
        _runtime.transport().call("ears", "resume_listening")
