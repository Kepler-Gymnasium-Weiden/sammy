"""`robot.ui` — student-defined tabs with simple UI elements.

Usage in a student program::

    tab = robot.ui.tab("Tricks")
    tab.button("Wave", on_click=do_wave)
    speed = tab.slider("Speed", 0, 100, initial=50, on_change=set_speed)
    status = tab.label("Status", "idle")
    status.set("running")

Tabs are remembered by name within a single program run. Calling
`robot.ui.tab("X")` a second time returns the existing handle without
recreating the panel.
"""

from __future__ import annotations

import itertools
from typing import Callable, Optional

from . import _runtime


_element_counter = itertools.count(1)


def _new_id(kind: str) -> str:
    return f"{kind}_{next(_element_counter)}"


class _ElementHandle:
    """Returned from `tab.button(...)` etc. Lets the student update the element."""

    def __init__(self, element_id: str):
        self._id = element_id

    @property
    def id(self) -> str:
        return self._id

    def set(self, value):
        """Update the element's value (label text, slider position, etc.)."""
        _runtime.transport().call("ui", "set_element", [self._id, value])


class Tab:
    def __init__(self, name: str):
        self._name = str(name)
        self._elements: dict[str, _ElementHandle] = {}
        _runtime.transport().call("ui", "create_tab", [self._name])

    @property
    def name(self) -> str:
        return self._name

    # ---- element constructors ----------------------------------------

    def button(self, label: str, on_click: Callable[[], None]) -> _ElementHandle:
        eid = _new_id("button")
        _runtime.transport().register_event_handler(eid, on_click)
        _runtime.transport().call(
            "ui", "add_element",
            [self._name, "button", eid, {"label": str(label)}],
        )
        return self._track(eid)

    def label(self, name: str, text: str = "") -> _ElementHandle:
        eid = _new_id(f"label_{name}")
        _runtime.transport().call(
            "ui", "add_element",
            [self._name, "label", eid, {"text": str(text)}],
        )
        return self._track(eid, key=name)

    def slider(self, label: str, minimum: int, maximum: int,
               *, initial: int = 0,
               on_change: Optional[Callable[[int], None]] = None) -> _ElementHandle:
        eid = _new_id("slider")
        if on_change is not None:
            _runtime.transport().register_event_handler(eid, on_change)
        _runtime.transport().call(
            "ui", "add_element",
            [self._name, "slider", eid, {
                "label": str(label),
                "minimum": int(minimum),
                "maximum": int(maximum),
                "initial": int(initial),
            }],
        )
        return self._track(eid)

    def toggle(self, label: str, *, initial: bool = False,
               on_change: Optional[Callable[[bool], None]] = None) -> _ElementHandle:
        eid = _new_id("toggle")
        if on_change is not None:
            _runtime.transport().register_event_handler(eid, on_change)
        _runtime.transport().call(
            "ui", "add_element",
            [self._name, "toggle", eid, {
                "label": str(label),
                "initial": bool(initial),
            }],
        )
        return self._track(eid)

    def text_input(self, label: str = "", *, initial: str = "",
                   placeholder: str = "",
                   on_submit: Optional[Callable[[str], None]] = None
                   ) -> _ElementHandle:
        eid = _new_id("text_input")
        if on_submit is not None:
            _runtime.transport().register_event_handler(eid, on_submit)
        _runtime.transport().call(
            "ui", "add_element",
            [self._name, "text_input", eid, {
                "label": str(label),
                "initial": str(initial),
                "placeholder": str(placeholder),
            }],
        )
        return self._track(eid)

    def dropdown(self, label: str, options: list,
                 *, initial: Optional[str] = None,
                 on_change: Optional[Callable[[str], None]] = None
                 ) -> _ElementHandle:
        eid = _new_id("dropdown")
        if on_change is not None:
            _runtime.transport().register_event_handler(eid, on_change)
        _runtime.transport().call(
            "ui", "add_element",
            [self._name, "dropdown", eid, {
                "label": str(label),
                "options": [str(o) for o in options],
                "initial": None if initial is None else str(initial),
            }],
        )
        return self._track(eid)

    # ---- helpers -----------------------------------------------------

    def _track(self, eid: str, key: str | None = None) -> _ElementHandle:
        handle = _ElementHandle(eid)
        self._elements[key or eid] = handle
        return handle


class Ui:
    """Top-level UI namespace (`robot.ui`)."""

    def __init__(self):
        self._tabs: dict[str, Tab] = {}

    def tab(self, name: str) -> Tab:
        """Return the existing tab with this name or create a new one."""
        name = str(name)
        if name not in self._tabs:
            self._tabs[name] = Tab(name)
        return self._tabs[name]
