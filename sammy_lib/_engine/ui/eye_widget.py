"""Animated robot-eye widget. Re-used from the original prototype, with one
addition: each high-level state transition reports its animation duration so
the engine-side backend can wait synchronously before sending an IPC reply.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QVariantAnimation,
    QEasingCurve,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QBrush, QColor, QPen, QPainterPath, QPainter
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
)

from ..modules.eye_states import EyeState


BG_COLOR = QColor(18, 22, 32)
SCLERA_COLOR = QColor(245, 245, 245)
IRIS_COLOR = QColor(60, 170, 230)
PUPIL_COLOR = QColor(10, 10, 10)
LID_COLOR = BG_COLOR

SCENE_W = 800
SCENE_H = 480
EYE_RADIUS = 110

NEUTRAL = {
    "gaze_x": 0.0,
    "gaze_y": 0.0,
    "upper_lid_coverage": 0.05,
    "lower_lid_coverage": 0.05,
    "upper_lid_tilt": 0.0,
    "lower_lid_curve": 0.0,
    "pupil_scale": 1.0,
}


class Eye:
    """One eye: sclera, iris, pupil, upper-lid path, lower-lid path."""

    def __init__(self, scene: QGraphicsScene, center: QPointF,
                 radius: float, inner_side: int):
        self.scene = scene
        self.center = center
        self.radius = radius
        self.iris_radius = radius * 0.55
        self.pupil_radius = radius * 0.28
        self.inner_side = inner_side

        self.gaze_x = 0.0
        self.gaze_y = 0.0
        self.upper_lid_coverage = NEUTRAL["upper_lid_coverage"]
        self.lower_lid_coverage = NEUTRAL["lower_lid_coverage"]
        self.upper_lid_tilt = 0.0
        self.lower_lid_curve = 0.0
        self.pupil_scale = 1.0

        self._build()

    def _build(self):
        cx, cy = self.center.x(), self.center.y()
        r = self.radius
        no_pen = QPen(Qt.PenStyle.NoPen)

        self.sclera = QGraphicsEllipseItem(cx - r, cy - r, 2 * r, 2 * r)
        self.sclera.setBrush(QBrush(SCLERA_COLOR))
        self.sclera.setPen(no_pen)
        self.scene.addItem(self.sclera)

        ir = self.iris_radius
        self.iris = QGraphicsEllipseItem(cx - ir, cy - ir, 2 * ir, 2 * ir)
        self.iris.setBrush(QBrush(IRIS_COLOR))
        self.iris.setPen(no_pen)
        self.scene.addItem(self.iris)

        pr = self.pupil_radius
        self.pupil = QGraphicsEllipseItem(cx - pr, cy - pr, 2 * pr, 2 * pr)
        self.pupil.setBrush(QBrush(PUPIL_COLOR))
        self.pupil.setPen(no_pen)
        self.scene.addItem(self.pupil)

        self.upper_lid = QGraphicsPathItem()
        self.upper_lid.setBrush(QBrush(LID_COLOR))
        self.upper_lid.setPen(no_pen)
        self.scene.addItem(self.upper_lid)

        self.lower_lid = QGraphicsPathItem()
        self.lower_lid.setBrush(QBrush(LID_COLOR))
        self.lower_lid.setPen(no_pen)
        self.scene.addItem(self.lower_lid)

        self.update_geometry()

    def update_geometry(self):
        cx, cy = self.center.x(), self.center.y()
        r = self.radius
        max_off = r - self.iris_radius - 2
        ox = max(-max_off, min(max_off, self.gaze_x))
        oy = max(-max_off, min(max_off, self.gaze_y))

        ir = self.iris_radius
        self.iris.setRect(cx + ox - ir, cy + oy - ir, 2 * ir, 2 * ir)
        pr = self.pupil_radius * self.pupil_scale
        self.pupil.setRect(cx + ox - pr, cy + oy - pr, 2 * pr, 2 * pr)
        self.upper_lid.setPath(self._upper_lid_path())
        self.lower_lid.setPath(self._lower_lid_path())

    def _upper_lid_path(self) -> QPainterPath:
        cx, cy = self.center.x(), self.center.y()
        r = self.radius
        pad = r * 0.6
        cov = self.upper_lid_coverage
        full_top = cy - r - pad
        full_bottom = cy + r + pad
        y_center = full_top + cov * (full_bottom - full_top)
        tilt = self.upper_lid_tilt * r * 0.55
        y_right = y_center + tilt * self.inner_side
        y_left = y_center - tilt * self.inner_side

        path = QPainterPath()
        left_x = cx - r - pad
        right_x = cx + r + pad
        top_y = cy - r - pad - 5
        path.moveTo(left_x, top_y)
        path.lineTo(right_x, top_y)
        path.lineTo(right_x, y_right)
        path.lineTo(left_x, y_left)
        path.closeSubpath()
        return path

    def _lower_lid_path(self) -> QPainterPath:
        cx, cy = self.center.x(), self.center.y()
        r = self.radius
        pad = r * 0.6
        cov = self.lower_lid_coverage
        full_bottom = cy + r + pad
        full_top = cy - r - pad
        y_edge = full_bottom - cov * (full_bottom - full_top)
        curve = self.lower_lid_curve * r * 0.8

        path = QPainterPath()
        left_x = cx - r - pad
        right_x = cx + r + pad
        bottom_y = cy + r + pad + 5
        path.moveTo(left_x, bottom_y)
        path.lineTo(right_x, bottom_y)
        path.lineTo(right_x, y_edge)
        path.quadTo(cx, y_edge - curve, left_x, y_edge)
        path.closeSubpath()
        return path


class EyeWidget(QGraphicsView):
    """QGraphicsView showing two animated eyes.

    `set_eye_state` returns the animation duration in ms so the IPC backend
    can wait for completion before replying to a blocking client call.
    """

    state_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._scene.setBackgroundBrush(QBrush(BG_COLOR))
        self._scene.setSceneRect(0, 0, SCENE_W, SCENE_H)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

        spacing = SCENE_W * 0.18
        cy = SCENE_H * 0.5
        self.left_eye = Eye(self._scene,
                            QPointF(SCENE_W / 2 - spacing - EYE_RADIUS * 0.5, cy),
                            EYE_RADIUS, inner_side=+1)
        self.right_eye = Eye(self._scene,
                             QPointF(SCENE_W / 2 + spacing + EYE_RADIUS * 0.5, cy),
                             EYE_RADIUS, inner_side=-1)
        self.eyes = (self.left_eye, self.right_eye)

        self._state: EyeState = EyeState.IDLE
        self._active_anims: list[QVariantAnimation] = []

        self._idle_enabled = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._idle_blink_tick)
        self._drift_timer = QTimer(self)
        self._drift_timer.setSingleShot(True)
        self._drift_timer.timeout.connect(self._idle_drift_tick)
        self._schedule_idle_blink()
        self._schedule_idle_drift()

    # ---- public API ----------------------------------------------------

    def set_eye_state(self, state: EyeState) -> int:
        """Switch state, kick off the animation, return the chain duration in ms."""
        if not isinstance(state, EyeState):
            return 0
        self._state = state
        self._stop_active_anims()

        if state == EyeState.IDLE:
            duration = self._go_neutral()
        elif state == EyeState.BLINK:
            duration = self._do_blink()
        elif state == EyeState.LOOK_LEFT:
            duration = self._do_look(-1.0, 0.0)
        elif state == EyeState.LOOK_RIGHT:
            duration = self._do_look(+1.0, 0.0)
        elif state == EyeState.LOOK_UP:
            duration = self._do_look(0.0, -1.0)
        elif state == EyeState.LOOK_DOWN:
            duration = self._do_look(0.0, +1.0)
        elif state == EyeState.HAPPY:
            duration = self._do_happy()
        elif state == EyeState.ANGRY:
            duration = self._do_angry()
        elif state == EyeState.SURPRISED:
            duration = self._do_surprised()
        elif state == EyeState.TIRED:
            duration = self._do_tired()
        else:
            duration = 0

        self.state_changed.emit(state)
        return duration

    def set_idle_animation(self, enabled: bool):
        self._idle_enabled = enabled
        if enabled:
            self._schedule_idle_blink()
            self._schedule_idle_drift()
        else:
            self._blink_timer.stop()
            self._drift_timer.stop()

    @property
    def state(self) -> EyeState:
        return self._state

    # ---- view scaling --------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ---- animation primitives -----------------------------------------

    def _stop_active_anims(self):
        for a in self._active_anims:
            a.stop()
        self._active_anims.clear()

    def _animate(self, targets: dict, duration_ms: int,
                 on_finish: Optional[Callable] = None,
                 easing: QEasingCurve.Type = QEasingCurve.Type.InOutQuad
                 ) -> QVariantAnimation:
        starts = [{k: getattr(eye, k) for k in targets} for eye in self.eyes]

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(easing)

        def on_value(t):
            t = float(t)
            for eye, start in zip(self.eyes, starts):
                for k, end in targets.items():
                    setattr(eye, k, start[k] + (end - start[k]) * t)
                eye.update_geometry()

        anim.valueChanged.connect(on_value)

        def cleanup():
            if anim in self._active_anims:
                self._active_anims.remove(anim)
            if on_finish:
                on_finish()

        anim.finished.connect(cleanup)
        self._active_anims.append(anim)
        anim.start()
        return anim

    # ---- per-state handlers (each returns chain duration in ms) -------

    def _go_neutral(self, duration: int = 250) -> int:
        self._animate(dict(NEUTRAL), duration)
        return duration

    def _do_blink(self) -> int:
        def reopen():
            self._animate(
                {"upper_lid_coverage": NEUTRAL["upper_lid_coverage"],
                 "lower_lid_coverage": NEUTRAL["lower_lid_coverage"]},
                75,
            )
        self._animate(
            {"upper_lid_coverage": 0.55, "lower_lid_coverage": 0.55},
            75, on_finish=reopen,
        )
        return 150

    def _do_look(self, dx: float, dy: float) -> int:
        max_off = EYE_RADIUS - EYE_RADIUS * 0.55 - 2
        self._animate({
            "gaze_x": dx * max_off, "gaze_y": dy * max_off,
            "upper_lid_coverage": NEUTRAL["upper_lid_coverage"],
            "lower_lid_coverage": NEUTRAL["lower_lid_coverage"],
            "upper_lid_tilt": 0.0, "lower_lid_curve": 0.0,
            "pupil_scale": 1.0,
        }, 220)
        return 220

    def _do_happy(self) -> int:
        self._animate({
            "upper_lid_coverage": 0.15, "lower_lid_coverage": 0.45,
            "lower_lid_curve": 1.0, "upper_lid_tilt": 0.0,
            "gaze_x": 0.0, "gaze_y": 0.0, "pupil_scale": 1.0,
        }, 300)
        return 300

    def _do_angry(self) -> int:
        self._animate({
            "upper_lid_coverage": 0.45, "upper_lid_tilt": 1.0,
            "lower_lid_coverage": NEUTRAL["lower_lid_coverage"],
            "lower_lid_curve": 0.0,
            "gaze_x": 0.0, "gaze_y": 0.0, "pupil_scale": 0.95,
        }, 250)
        return 250

    def _do_surprised(self) -> int:
        self._animate({
            "upper_lid_coverage": 0.0, "lower_lid_coverage": 0.0,
            "upper_lid_tilt": 0.0, "lower_lid_curve": 0.0,
            "gaze_x": 0.0, "gaze_y": 0.0, "pupil_scale": 0.5,
        }, 180, easing=QEasingCurve.Type.OutBack)
        return 180

    def _do_tired(self) -> int:
        self._animate({
            "upper_lid_coverage": 0.6, "lower_lid_coverage": 0.1,
            "upper_lid_tilt": 0.0, "lower_lid_curve": 0.0,
            "gaze_x": 0.0, "gaze_y": 0.06 * EYE_RADIUS, "pupil_scale": 1.0,
        }, 350)
        return 350

    # ---- autonomous idle -----------------------------------------------

    def _schedule_idle_blink(self):
        if self._idle_enabled:
            self._blink_timer.start(random.randint(3000, 6000))

    def _schedule_idle_drift(self):
        if self._idle_enabled:
            self._drift_timer.start(random.randint(800, 2200))

    def _idle_blink_tick(self):
        if self._idle_enabled and self._state == EyeState.IDLE:
            self._do_blink()
        self._schedule_idle_blink()

    def _idle_drift_tick(self):
        if self._idle_enabled and self._state == EyeState.IDLE:
            max_drift = EYE_RADIUS * 0.12
            self._animate({"gaze_x": random.uniform(-max_drift, max_drift),
                           "gaze_y": random.uniform(-max_drift, max_drift)}, 600)
        self._schedule_idle_drift()
