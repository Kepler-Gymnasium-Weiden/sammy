"""`robot.eyes` — the student-facing facade for the eyes module."""

from __future__ import annotations

from . import _runtime


class Eyes:
    """All methods block until the eye animation finishes."""

    # ---- movement ------------------------------------------------------

    def look_left(self):
        _runtime.transport().call("eyes", "look_left")

    def look_right(self):
        _runtime.transport().call("eyes", "look_right")

    def look_up(self):
        _runtime.transport().call("eyes", "look_up")

    def look_down(self):
        _runtime.transport().call("eyes", "look_down")

    def blink(self):
        _runtime.transport().call("eyes", "blink")

    # ---- expressions ---------------------------------------------------

    def happy(self):
        _runtime.transport().call("eyes", "happy")

    def angry(self):
        _runtime.transport().call("eyes", "angry")

    def surprised(self):
        _runtime.transport().call("eyes", "surprised")

    def tired(self):
        _runtime.transport().call("eyes", "tired")

    def idle(self):
        _runtime.transport().call("eyes", "idle")

    def set_idle_animation(self, enabled: bool):
        _runtime.transport().call("eyes", "set_idle_animation", [bool(enabled)])

    # ---- vision (camera + recognition) --------------------------------

    def camera_on(self):
        _runtime.transport().call("eyes", "camera_on")

    def camera_off(self):
        _runtime.transport().call("eyes", "camera_off")

    def what_do_you_see(self) -> list[str]:
        """Return a list of recognised object labels (e.g. ['person', 'cup'])."""
        return _runtime.transport().call("eyes", "what_do_you_see") or []

    def can_see(self, label: str) -> bool:
        return bool(_runtime.transport().call("eyes", "can_see", [str(label)]))
