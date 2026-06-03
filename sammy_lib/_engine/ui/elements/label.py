"""Label element. Read-only text; updated via .set(text)."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QLabel


class LabelElement:
    type_name = "label"

    def __init__(self, element_id: str, on_event: Callable[[str, str, object], None],
                 *, text: str = ""):
        self.element_id = element_id
        self.on_event = on_event  # unused, kept for symmetry
        self.widget = QLabel(str(text))

    def set(self, value):
        self.widget.setText(str(value))
