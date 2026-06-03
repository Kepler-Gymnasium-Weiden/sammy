"""Slider element. Drag → event 'change' with integer value."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLabel


class SliderElement:
    type_name = "slider"

    def __init__(self, element_id: str, on_event: Callable[[str, str, object], None],
                 *, label: str = "", minimum: int = 0, maximum: int = 100,
                 initial: int = 0):
        self.element_id = element_id
        self.on_event = on_event
        self.widget = QWidget()
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        if label:
            layout.addWidget(QLabel(str(label)))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(int(minimum), int(maximum))
        self._slider.setValue(int(initial))
        self._slider.valueChanged.connect(
            lambda v: on_event(element_id, "change", int(v))
        )
        layout.addWidget(self._slider, 1)
        self._value_label = QLabel(str(int(initial)))
        self._value_label.setMinimumWidth(36)
        self._slider.valueChanged.connect(lambda v: self._value_label.setText(str(v)))
        layout.addWidget(self._value_label)

    def set(self, value):
        self._slider.setValue(int(value))
