"""Backend for `robot.eyes` — drives the EyeWidget and waits for animations.

Synchronous-feeling API: each method starts the animation, then blocks the
calling thread (the GUI thread, called from the dispatcher slot) inside a
nested QEventLoop for the animation's known duration. The Qt event loop keeps
running, so the GUI stays responsive and other queued signals get processed.
"""

from __future__ import annotations

from PyQt6.QtCore import QEventLoop, QTimer

from .base import ModuleBase
from .eye_states import EyeState
from ..ui.eye_widget import EyeWidget


class EyesBackend(ModuleBase):
    name = "eyes"

    def __init__(self, widget: EyeWidget, camera=None, vision=None):
        self.widget = widget
        self._camera = camera   # CameraBackend or None
        self._vision = vision   # VisionBackend or None

    # ---- core movement / expressions -----------------------------------

    def look_left(self):
        self._run(EyeState.LOOK_LEFT)

    def look_right(self):
        self._run(EyeState.LOOK_RIGHT)

    def look_up(self):
        self._run(EyeState.LOOK_UP)

    def look_down(self):
        self._run(EyeState.LOOK_DOWN)

    def blink(self):
        self._run(EyeState.BLINK)

    def happy(self):
        self._run(EyeState.HAPPY)

    def angry(self):
        self._run(EyeState.ANGRY)

    def surprised(self):
        self._run(EyeState.SURPRISED)

    def tired(self):
        self._run(EyeState.TIRED)

    def idle(self):
        self._run(EyeState.IDLE)

    def set_idle_animation(self, enabled: bool):
        self.widget.set_idle_animation(bool(enabled))

    # ---- vision-side methods (delegate to camera + vision backends) ----

    def camera_on(self):
        if self._camera is None:
            raise RuntimeError("camera module unavailable")
        self._camera.start()

    def camera_off(self):
        if self._camera is None:
            return
        self._camera.stop()

    def what_do_you_see(self) -> list[str]:
        """Return a list of labels for objects currently visible."""
        if self._vision is None:
            return []
        if self._camera is None or not self._camera.is_running():
            self.camera_on()
        return self._vision.detect_labels()

    def can_see(self, label: str) -> bool:
        return label.lower() in {l.lower() for l in self.what_do_you_see()}

    # ---- internal helpers ---------------------------------------------

    def _run(self, state: EyeState):
        duration = self.widget.set_eye_state(state)
        self._wait_ms(duration)

    def _wait_ms(self, ms: int):
        if ms <= 0:
            return
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
