"""Combined Eyes settings panel.

Everything related to "seeing" lives here: the animation actions students can
trigger by hand, the autonomous-idle toggle, the live camera preview, and the
object-detection controls. The Camera and Vision tabs from the original
layout have been folded in as sections of this panel.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
    QSlider,
    QListWidget,
    QFrame,
)

from ..eye_widget import EyeWidget
from ...modules.camera_backend import CameraBackend
from ...modules.vision_backend import VisionBackend


# ---- Action buttons -----------------------------------------------------

#: (method name on robot.eyes / EyesBackend, German label)
MOVEMENT_ACTIONS = [
    ("look_up",    "Look up"),
    ("look_down",  "Look down"),
    ("look_left",  "Look left"),
    ("look_right", "Look right"),
    ("blink",      "Blink"),
]
EXPRESSION_ACTIONS = [
    ("happy",     "Happy"),
    ("angry",     "Angry"),
    ("surprised", "Surprised"),
    ("tired",     "Tired"),
    ("idle",      "Neutral"),
]


# ---- Live preview helper ------------------------------------------------

class _PreviewLabel(QLabel):
    """Renders RGB camera frames with optional detection-box overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#111; color:#888;")
        self.setText("Camera off")
        self._overlay: list[dict] = []

    def set_overlay(self, detections: list[dict]):
        self._overlay = detections or []

    def show_frame(self, rgb):
        if rgb is None:
            return
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        if self._overlay:
            self._paint_overlay(img)
        pix = QPixmap.fromImage(img).scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pix)

    def _paint_overlay(self, img: QImage):
        p = QPainter(img)
        pen = QPen(QColor(255, 200, 0))
        pen.setWidth(2)
        p.setPen(pen)
        for d in self._overlay:
            x1, y1, x2, y2 = d.get("box", (0, 0, 0, 0))
            p.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
            label = f"{d.get('label', '?')} {d.get('confidence', 0):.2f}"
            p.fillRect(int(x1), int(y1) - 16, len(label) * 8, 16, QColor(0, 0, 0, 160))
            p.drawText(int(x1) + 2, int(y1) - 4, label)
        p.end()


# ---- Combined panel -----------------------------------------------------

class EyesSettingsPanel(QWidget):
    def __init__(self, eye_widget: EyeWidget, camera: CameraBackend,
                 vision: VisionBackend, parent=None):
        super().__init__(parent)
        self._eye = eye_widget
        self._camera = camera
        self._vision = vision

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ------------- Section: Actions -----------------------------------
        root.addWidget(self._section_header("Actions"))

        actions_grid = QGridLayout()
        actions_grid.setSpacing(4)
        for col, (method, label) in enumerate(MOVEMENT_ACTIONS):
            btn = self._make_action_button(label, method)
            actions_grid.addWidget(btn, 0, col)
        for col, (method, label) in enumerate(EXPRESSION_ACTIONS):
            btn = self._make_action_button(label, method)
            actions_grid.addWidget(btn, 1, col)
        root.addLayout(actions_grid)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Current:"))
        self._state_label = QLabel(self._eye.state.name)
        self._state_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self._state_label)
        status_row.addStretch(1)
        self._idle_check = QCheckBox("Autonomous idle animation")
        self._idle_check.setChecked(True)
        self._idle_check.toggled.connect(self._eye.set_idle_animation)
        status_row.addWidget(self._idle_check)
        root.addLayout(status_row)
        self._eye.state_changed.connect(
            lambda s: self._state_label.setText(s.name)
        )

        root.addWidget(self._separator())

        # ------------- Section: Camera ------------------------------------
        root.addWidget(self._section_header("Camera"))

        if not self._camera.is_available():
            root.addWidget(QLabel("OpenCV is not installed — preview disabled."))
        else:
            cam_controls = QHBoxLayout()
            self._cam_on_btn = QPushButton("Turn on")
            self._cam_on_btn.clicked.connect(self._start_camera)
            cam_controls.addWidget(self._cam_on_btn)

            self._cam_off_btn = QPushButton("Turn off")
            self._cam_off_btn.clicked.connect(self._stop_camera)
            self._cam_off_btn.setEnabled(False)
            cam_controls.addWidget(self._cam_off_btn)

            cam_controls.addWidget(QLabel("Device:"))
            self._device = QComboBox()
            for index, name in CameraBackend.list_camera_devices():
                self._device.addItem(f"{index}: {name}", index)
            if self._device.count() == 0:
                self._device.addItem("No camera found", 0)
            self._device.currentIndexChanged.connect(self._on_device_changed)
            cam_controls.addWidget(self._device)

            self._overlay_check = QCheckBox("Show detection overlay")
            self._overlay_check.setChecked(True)
            cam_controls.addWidget(self._overlay_check)
            cam_controls.addStretch(1)
            root.addLayout(cam_controls)

            self._preview = _PreviewLabel()
            root.addWidget(self._preview)
            self._camera.frame_ready.connect(self._on_frame)
            self._start_camera()

        root.addWidget(self._separator())

        # ------------- Section: Detection ---------------------------------
        root.addWidget(self._section_header("Detection"))

        if not self._vision.is_available():
            reason = getattr(self._vision, "import_error", "") \
                or "ultralytics is not available."
            label = QLabel(f"Object detection off: {reason}")
            label.setWordWrap(True)
            root.addWidget(label)
        else:
            conf_row = QHBoxLayout()
            conf_row.addWidget(QLabel("Confidence:"))
            self._conf = QSlider(Qt.Orientation.Horizontal)
            self._conf.setRange(10, 95)
            self._conf.setValue(45)
            self._conf_label = QLabel("0.45")
            self._conf.valueChanged.connect(self._on_conf_changed)
            conf_row.addWidget(self._conf, 1)
            conf_row.addWidget(self._conf_label)
            root.addLayout(conf_row)

            self._detect_btn = QPushButton("Run detection now")
            self._detect_btn.clicked.connect(self._run_detection)
            root.addWidget(self._detect_btn)

            self._results = QListWidget()
            self._results.setMaximumHeight(120)
            root.addWidget(self._results)

        root.addStretch(1)

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _section_header(text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setStyleSheet("color: #ddd; font-size: 13px;")
        return lbl

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #444;")
        return sep

    def _make_action_button(self, label: str, method: str) -> QPushButton:
        btn = QPushButton(label)
        btn.clicked.connect(lambda _checked=False, m=method: self._trigger(m))
        return btn

    def _trigger(self, method: str):
        """Invoke an EyeWidget animation by name. Falls back to set_eye_state
        for the few methods that aren't direct EyeWidget attributes."""
        from ...modules.eye_states import EyeState
        state_map = {
            "look_up":    EyeState.LOOK_UP,
            "look_down":  EyeState.LOOK_DOWN,
            "look_left":  EyeState.LOOK_LEFT,
            "look_right": EyeState.LOOK_RIGHT,
            "blink":      EyeState.BLINK,
            "happy":      EyeState.HAPPY,
            "angry":      EyeState.ANGRY,
            "surprised":  EyeState.SURPRISED,
            "tired":      EyeState.TIRED,
            "idle":       EyeState.IDLE,
        }
        state = state_map.get(method)
        if state is not None:
            self._eye.set_eye_state(state)

    # ---- camera section -----------------------------------------------

    def _start_camera(self):
        try:
            self._camera.start()
            self._cam_on_btn.setEnabled(False)
            self._cam_off_btn.setEnabled(True)
        except Exception as exc:
            self._preview.setText(f"Camera error: {exc}")

    def _on_device_changed(self, index: int):
        device_index = self._device.itemData(index)
        if device_index is not None:
            self._camera.set_device(device_index)

    def _stop_camera(self):
        self._camera.stop()
        self._cam_on_btn.setEnabled(True)
        self._cam_off_btn.setEnabled(False)
        self._preview.clear()
        self._preview.setText("Camera off")

    def _on_frame(self, rgb):
        if self._vision is not None and getattr(self, "_overlay_check", None) is not None \
                and self._overlay_check.isChecked():
            self._preview.set_overlay(self._vision.last_detections)
        else:
            self._preview.set_overlay([])
        self._preview.show_frame(rgb)

    # ---- vision section -----------------------------------------------

    def _on_conf_changed(self, v: int):
        c = v / 100.0
        self._vision.set_confidence(c)
        self._conf_label.setText(f"{c:.2f}")

    def _run_detection(self):
        self._results.clear()
        for d in self._vision.detect():
            self._results.addItem(f"{d['label']}  ({d['confidence']:.2f})")
        if self._results.count() == 0:
            self._results.addItem("(nothing detected)")
