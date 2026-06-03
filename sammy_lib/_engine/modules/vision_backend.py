"""Object-detection backend.

Runs YOLOv8n locally via the `ultralytics` package on the engine machine. If
`ultralytics` is not installed, the backend reports `is_available()` as False
and `detect_labels()` returns an empty list — useful for development where
ML deps aren't set up.

No image data ever leaves the machine. This is a hard requirement for the
educational deployment context (children's faces, GDPR, EU AI Act).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject

from .camera_backend import CameraBackend

try:
    from ultralytics import YOLO  # type: ignore
    _HAVE_YOLO = True
except Exception:
    YOLO = None  # type: ignore
    _HAVE_YOLO = False


class VisionBackend(QObject):
    name = "vision"

    def __init__(self, camera: CameraBackend, model_name: str = "yolov8n.pt",
                 confidence: float = 0.45, parent=None):
        super().__init__(parent)
        self._camera = camera
        self._model_name = model_name
        self._confidence = confidence
        self._model: Optional[object] = None
        self._last_detections: list[dict] = []

    def is_available(self) -> bool:
        return _HAVE_YOLO

    def set_confidence(self, value: float):
        self._confidence = max(0.0, min(1.0, float(value)))

    def _ensure_model(self):
        if self._model is None and _HAVE_YOLO:
            # First call may download the weights (~6 MB for yolov8n).
            self._model = YOLO(self._model_name)

    def detect(self) -> list[dict]:
        """Return rich detection dicts: [{label, confidence, box=(x1,y1,x2,y2)}, ...]."""
        if not _HAVE_YOLO:
            return []
        frame = self._camera.latest_frame()
        if frame is None:
            return []
        self._ensure_model()
        results = self._model(frame, conf=self._confidence, verbose=False)  # type: ignore
        detections: list[dict] = []
        if results:
            r = results[0]
            names = r.names if hasattr(r, "names") else {}
            for box in (r.boxes or []):
                cls_id = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
                conf = float(box.conf.item()) if hasattr(box.conf, "item") else float(box.conf)
                xyxy = box.xyxy[0].tolist() if hasattr(box.xyxy, "tolist") else list(box.xyxy[0])
                detections.append({
                    "label": names.get(cls_id, str(cls_id)),
                    "confidence": conf,
                    "box": [float(v) for v in xyxy],
                })
        self._last_detections = detections
        return detections

    def detect_labels(self) -> list[str]:
        """Convenience: just the label strings, de-duplicated."""
        seen: list[str] = []
        for d in self.detect():
            if d["label"] not in seen:
                seen.append(d["label"])
        return seen

    @property
    def last_detections(self) -> list[dict]:
        return self._last_detections
