"""Button element. Click → event 'click' (no value)."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QPushButton


class ButtonElement:
    type_name = "button"

    def __init__(self, element_id: str, on_event: Callable[[str, str, object], None],
                 *, label: str = "Button"):
        self.element_id = element_id
        self.on_event = on_event
        self.widget = QPushButton(label)
        self.widget.clicked.connect(lambda _checked=False: on_event(element_id, "click", None))

    def set(self, value):
        # For a button `value` is interpreted as the label text.
        self.widget.setText(str(value))
