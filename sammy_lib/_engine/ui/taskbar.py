"""Taskbar with built-in and student tabs.

The bar sits at the bottom of the window. Clicking a tab chip toggles a
panel that appears just above the bar. The right edge holds the Run / Stop
controls (Stop is the only one that's wired to anything for v1; Run is a
placeholder for a future script-launcher).

Student tabs are added at runtime via `add_custom_tab(name)`, then populated
with elements via `add_element(tab_name, element)`.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QFrame,
    QScrollArea,
    QLabel,
)


class _TabPanel(QFrame):
    """Container for one tab's controls. Sits above the taskbar when shown."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("tabPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(30, 34, 44, 235))
        self.setPalette(pal)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)
        header = QLabel(f"<b>{title}</b>")
        header.setStyleSheet("color: #ddd;")
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(6)
        self._body_layout.addStretch(1)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

    def add_widget(self, w: QWidget):
        self._body_layout.insertWidget(self._body_layout.count() - 1, w)

    def clear(self):
        # Remove every widget except the trailing stretch.
        while self._body_layout.count() > 1:
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)


class Taskbar(QWidget):
    """Bottom bar of tab chips + the panel that pops up above them."""

    stop_clicked = pyqtSignal()
    pin_changed = pyqtSignal(bool)   # True = pinned (always visible)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(24, 28, 38))
        self.setPalette(pal)

        self._panels: dict[str, _TabPanel] = {}
        self._buttons: dict[str, QPushButton] = {}
        self._active: Optional[str] = None
        self._pinned: bool = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Panel host above the bar. Hidden until a tab is clicked.
        self._panel_host = QFrame()
        self._panel_host.setVisible(False)
        self._panel_host.setMinimumHeight(280)
        self._panel_host_layout = QVBoxLayout(self._panel_host)
        self._panel_host_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel_host)

        # The chip strip itself.
        self._bar = QWidget()
        self._bar.setFixedHeight(44)
        self._bar_layout = QHBoxLayout(self._bar)
        self._bar_layout.setContentsMargins(8, 4, 8, 4)
        self._bar_layout.setSpacing(6)
        outer.addWidget(self._bar)

        # Right-side fixed controls (Pin, Stop).
        self._bar_layout.addStretch(1)

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(True)
        self._pin_btn.setToolTip("Pin taskbar (keep it visible)")
        self._pin_btn.setStyleSheet(self._chip_style(active=True))
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        self._bar_layout.addWidget(self._pin_btn)

        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setStyleSheet(self._chip_style(active=False))
        self._stop_btn.clicked.connect(self.stop_clicked)
        self._bar_layout.addWidget(self._stop_btn)

    # ---- tab management ------------------------------------------------

    def add_tab(self, name: str, panel_widget: QWidget):
        """Register a panel under `name`. Adds a chip on the left side."""
        panel = _TabPanel(name)
        panel.add_widget(panel_widget)
        self._panels[name] = panel

        btn = QPushButton(name)
        btn.setStyleSheet(self._chip_style(active=False))
        btn.clicked.connect(lambda _checked=False, n=name: self.toggle(n))
        self._buttons[name] = btn
        # Insert before the stretch (which sits at index = total - 2).
        insert_at = self._bar_layout.count() - 2
        self._bar_layout.insertWidget(max(0, insert_at), btn)

    def add_custom_tab(self, name: str):
        """Register an empty student tab. Elements come in via add_element."""
        if name in self._panels:
            self._panels[name].clear()
            return
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)
        host_layout.addStretch(1)
        # Store the inner host so we can append elements later.
        host._inner_layout = host_layout  # type: ignore[attr-defined]
        self.add_tab(name, host)
        # We need to find the panel & remember the host inside it.
        panel = self._panels[name]
        panel._student_host = host  # type: ignore[attr-defined]

    def add_element(self, tab_name: str, widget: QWidget):
        """Add a Qt widget into an existing custom tab."""
        panel = self._panels.get(tab_name)
        if panel is None:
            self.add_custom_tab(tab_name)
            panel = self._panels[tab_name]
        host = getattr(panel, "_student_host", None)
        if host is None:
            panel.add_widget(widget)
            return
        layout: QVBoxLayout = host._inner_layout  # type: ignore[attr-defined]
        layout.insertWidget(layout.count() - 1, widget)

    def clear_custom_tab(self, name: str):
        panel = self._panels.get(name)
        if panel is None:
            return
        host = getattr(panel, "_student_host", None)
        if host is None:
            return
        layout: QVBoxLayout = host._inner_layout  # type: ignore[attr-defined]
        while layout.count() > 1:
            it = layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)

    def remove_tab(self, name: str):
        panel = self._panels.pop(name, None)
        btn = self._buttons.pop(name, None)
        if btn is not None:
            btn.setParent(None)
        if panel is not None and panel.parent() is self._panel_host:
            self._panel_host_layout.removeWidget(panel)
            panel.setParent(None)
        if self._active == name:
            self._active = None
            self._panel_host.setVisible(False)

    # ---- panel show/hide ----------------------------------------------

    def toggle(self, name: str):
        if self._active == name:
            self._hide_panel()
            return
        self._show_panel(name)

    def _show_panel(self, name: str):
        panel = self._panels.get(name)
        if panel is None:
            return
        # Detach previously shown panel.
        for p in self._panels.values():
            if p.parent() is self._panel_host:
                self._panel_host_layout.removeWidget(p)
                p.setParent(None)
        self._panel_host_layout.addWidget(panel)
        self._panel_host.setVisible(True)
        # Highlight active chip.
        for n, b in self._buttons.items():
            b.setStyleSheet(self._chip_style(active=(n == name)))
        self._active = name

    def _hide_panel(self):
        for p in self._panels.values():
            if p.parent() is self._panel_host:
                self._panel_host_layout.removeWidget(p)
                p.setParent(None)
        self._panel_host.setVisible(False)
        for b in self._buttons.values():
            b.setStyleSheet(self._chip_style(active=False))
        self._active = None

    # ---- pin / panel-state queries ------------------------------------

    def is_pinned(self) -> bool:
        return self._pinned

    def has_active_panel(self) -> bool:
        return self._active is not None

    def bar_height(self) -> int:
        """Height of the always-on chip strip (excludes any open panel)."""
        return self._bar.height() or self._bar.sizeHint().height()

    def _on_pin_toggled(self, checked: bool):
        self._pinned = bool(checked)
        self._pin_btn.setStyleSheet(self._chip_style(active=self._pinned))
        self.pin_changed.emit(self._pinned)

    def _chip_style(self, active: bool) -> str:
        if active:
            return (
                "QPushButton { background:#4a90e2; color:white; border:none;"
                " padding:6px 14px; border-radius:4px; }"
            )
        return (
            "QPushButton { background:#2c313c; color:#ddd; border:none;"
            " padding:6px 14px; border-radius:4px; }"
            "QPushButton:hover { background:#3a3f4b; }"
        )
