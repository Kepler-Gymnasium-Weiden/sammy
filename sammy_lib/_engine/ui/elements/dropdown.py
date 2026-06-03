"""Dropdown (combo box) element. Selection change → event 'change' with str."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel


class DropdownElement:
    type_name = "dropdown"

    def __init__(self, element_id: str, on_event: Callable[[str, str, object], None],
                 *, label: str = "", options: list | None = None,
                 initial: str | None = None):
        self.element_id = element_id
        self.on_event = on_event
        options = [str(o) for o in (options or [])]
        self.widget = QWidget()
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        if label:
            layout.addWidget(QLabel(str(label)))
        self._combo = QComboBox()
        self._combo.addItems(options)
        if initial is not None and str(initial) in options:
            self._combo.setCurrentText(str(initial))
        # connect AFTER addItems so the initial fill doesn't fire the callback
        self._combo.currentTextChanged.connect(
            lambda text: on_event(element_id, "change", str(text))
        )
        layout.addWidget(self._combo, 1)

    def set(self, value):
        self._combo.setCurrentText(str(value))
