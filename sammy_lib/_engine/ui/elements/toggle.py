"""Toggle (checkbox) element. State change → event 'change' with bool value."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QCheckBox


class ToggleElement:
    type_name = "toggle"

    def __init__(self, element_id: str, on_event: Callable[[str, str, object], None],
                 *, label: str = "", initial: bool = False):
        self.element_id = element_id
        self.on_event = on_event
        self.widget = QCheckBox(str(label))
        self.widget.setChecked(bool(initial))
        self.widget.toggled.connect(
            lambda checked: on_event(element_id, "change", bool(checked))
        )

    def set(self, value):
        self.widget.setChecked(bool(value))
