"""Backend for `robot.ui` — student-created tabs and elements.

Operates on the taskbar. Element events (button clicks, slider changes…) are
forwarded back to the client as `ui.event` messages over IPC.
"""

from __future__ import annotations

from typing import Callable

from .base import ModuleBase
from ..ui.elements import ELEMENT_TYPES
from ..ui.taskbar import Taskbar


class UiBackend(ModuleBase):
    name = "ui"

    def __init__(self, taskbar: Taskbar, send_event: Callable[[str, dict], None]):
        self._taskbar = taskbar
        self._send_event = send_event
        self._elements: dict[str, object] = {}
        self._tab_elements: dict[str, list[str]] = {}

    def create_tab(self, name: str):
        self._taskbar.add_custom_tab(str(name))
        self._tab_elements.setdefault(str(name), [])

    def clear_tab(self, name: str):
        name = str(name)
        self._taskbar.clear_custom_tab(name)
        for eid in self._tab_elements.get(name, []):
            self._elements.pop(eid, None)
        self._tab_elements[name] = []

    def add_element(self, tab: str, element_type: str,
                    element_id: str, options: dict | None = None):
        cls = ELEMENT_TYPES.get(str(element_type))
        if cls is None:
            raise ValueError(f"unknown element type: {element_type}")

        def on_event(eid, ev, value):
            # Hop GUI-thread → IPC out. Plain socket write, no extra locking.
            self._send_event("ui.event", {
                "element_id": eid, "event": ev, "value": value,
            })

        elem = cls(str(element_id), on_event, **(options or {}))
        self._elements[str(element_id)] = elem
        self._tab_elements.setdefault(str(tab), []).append(str(element_id))
        self._taskbar.add_element(str(tab), elem.widget)

    def set_element(self, element_id: str, value):
        e = self._elements.get(str(element_id))
        if e is not None:
            e.set(value)
