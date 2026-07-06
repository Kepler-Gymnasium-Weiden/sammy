"""Camera capture backend.

Wraps OpenCV's VideoCapture in a QThread. The thread continuously grabs
frames and stores the most recent one as a numpy array; consumers (the
preview widget, the vision backend, `eyes.see()`) read that frame on demand.

OpenCV is an optional dependency: if it isn't installed, the backend
degrades gracefully — `start()` raises with a clear message instead of
crashing the engine.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _HAVE_OPENCV = True
except Exception:
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _HAVE_OPENCV = False


def _capture_backend() -> int:
    # CAP_DSHOW exists as a constant on all platforms, so hasattr() is
    # not a Windows check — select by platform instead.
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY


class _CaptureThread(QThread):
    frame_ready = pyqtSignal(object)  # latest numpy frame (RGB)

    def __init__(self, device_index: int = 0, target_fps: int = 15, parent=None):
        super().__init__(parent)
        self._device_index = device_index
        self._target_fps = target_fps
        self._running = False
        self._lock = threading.Lock()
        self._latest = None

    def run(self):
        cap = cv2.VideoCapture(self._device_index, _capture_backend())
        if not cap.isOpened():
            return
        self._running = True
        interval = 1.0 / max(1, self._target_fps)
        try:
            while self._running:
                ok, frame_bgr = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                with self._lock:
                    self._latest = frame_rgb
                self.frame_ready.emit(frame_rgb)
                time.sleep(interval)
        finally:
            cap.release()

    def stop(self):
        self._running = False
        self.wait(1500)

    def latest(self):
        with self._lock:
            return self._latest


class CameraBackend(QObject):
    """Public facade over the capture thread."""

    name = "camera"
    frame_ready = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[_CaptureThread] = None
        self._device_index = 0
        self._fps = 15

    def is_available(self) -> bool:
        return _HAVE_OPENCV

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self):
        if not _HAVE_OPENCV:
            raise RuntimeError(
                "Camera unavailable: install opencv-python to enable vision features"
            )
        if self.is_running():
            return
        self._thread = _CaptureThread(self._device_index, self._fps)
        self._thread.frame_ready.connect(self.frame_ready)
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return
        self._thread.stop()
        self._thread = None

    def latest_frame(self):
        """Return the most recent RGB frame as a numpy array, or None."""
        if self._thread is None:
            return None
        return self._thread.latest()

    def set_device(self, index: int):
        was_running = self.is_running()
        self.stop()
        self._device_index = int(index)
        if was_running:
            self.start()

    @staticmethod
    def list_camera_devices(max_probe: int = 8) -> list[tuple[int, str]]:
        """Probe camera indices and return the ones that open.

        OpenCV has no enumeration API, so we open each index in turn and
        keep those that respond. Returns ``[(index, friendly_name), ...]``.
        """
        if not _HAVE_OPENCV:
            return []
        backend = _capture_backend()
        result = []
        for i in range(max_probe):
            cap = cv2.VideoCapture(i, backend)
            try:
                if cap.isOpened():
                    result.append((i, f"Camera {i}"))
            finally:
                cap.release()
        return result
