"""Text input element. Return key → event 'submit' with current text."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel


class TextInputElement:
    type_name = "text_input"

    def __init__(self, element_id: str, on_event: Callable[[str, str, object], None],
                 *, label: str = "", initial: str = "", placeholder: str = ""):
        self.element_id = element_id
        self.on_event = on_event
        self.widget = QWidget()
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        if label:
            layout.addWidget(QLabel(str(label)))
        self._edit = QLineEdit(str(initial))
        if placeholder:
            self._edit.setPlaceholderText(str(placeholder))
        self._edit.returnPressed.connect(
            lambda: on_event(element_id, "submit", self._edit.text())
        )
        layout.addWidget(self._edit, 1)

    def set(self, value):
        self._edit.setText(str(value))
