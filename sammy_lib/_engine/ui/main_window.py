"""Main window: fullscreen eye display with the taskbar overlaid at the bottom."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence, QPalette, QColor, QCursor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
)

from .eye_widget import EyeWidget
from .taskbar import Taskbar
from .settings.eyes_settings import EyesSettingsPanel
from .settings.mouth_settings import MouthSettingsPanel
from .settings.ears_settings import EarsSettingsPanel


class MainWindow(QMainWindow):
    stop_requested = pyqtSignal()

    def __init__(self, *, camera=None, vision=None, mouth=None, ears=None,
                 fullscreen: bool = True):
        super().__init__()
        self.setWindowTitle("pib robot")
        self.resize(1100, 620)

        # Dark background — the eye widget's scene already matches this.
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(18, 22, 32))
        self.setPalette(pal)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.eye_widget = EyeWidget()
        layout.addWidget(self.eye_widget, 1)

        self.taskbar = Taskbar()
        layout.addWidget(self.taskbar, 0)

        # Built-in settings tabs — order = order in the bar.
        # Camera + vision controls are folded into the Eyes tab since they all
        # represent "what the eyes can see".
        self.taskbar.add_tab(
            "Eyes",
            EyesSettingsPanel(self.eye_widget, camera, vision),
        )
        if mouth is not None:
            self.taskbar.add_tab("Mouth", MouthSettingsPanel(mouth))
        if ears is not None:
            self.taskbar.add_tab("Ears", EarsSettingsPanel(ears))

        self.taskbar.stop_clicked.connect(self.stop_requested)

        # Auto-hide: when the taskbar is not pinned, hide it unless the cursor
        # is in the bottom peek zone or a panel is currently open. We poll the
        # global cursor position with a cheap QTimer because Qt's hover events
        # don't fire on a hidden widget — we need to detect *re-entry*.
        self._pinned = self.taskbar.is_pinned()
        self.taskbar.pin_changed.connect(self._on_pin_changed)

        self._peek_timer = QTimer(self)
        self._peek_timer.setInterval(80)  # ~12 Hz; light on the CPU
        self._peek_timer.timeout.connect(self._update_taskbar_visibility)
        self._peek_timer.start()

        # F11 / Esc for fullscreen toggle. Useful for dev; in deployment the
        # window starts fullscreen and stays there.
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self._leave_fullscreen)

        if fullscreen:
            self.showFullScreen()
        else:
            self.show()

    def _on_pin_changed(self, pinned: bool):
        self._pinned = pinned
        # When unpinning we leave the bar visible until the cursor moves
        # away — the polling timer will hide it on the next tick if needed.

    def _update_taskbar_visibility(self):
        # Always-on cases: pinned, or a panel is open above the bar.
        if self._pinned or self.taskbar.has_active_panel():
            if not self.taskbar.isVisible():
                self.taskbar.setVisible(True)
            return

        pos = self.mapFromGlobal(QCursor.pos())
        # Don't react when the mouse is outside our window.
        if pos.x() < 0 or pos.x() > self.width() or pos.y() < 0 or pos.y() > self.height():
            if self.taskbar.isVisible():
                self.taskbar.setVisible(False)
            return

        # Peek zone: when bar is hidden, a thin 24-px strip along the bottom
        # triggers reveal. When bar is visible, the whole bar height counts as
        # "in the bar" so it doesn't flicker as the cursor enters its chips.
        peek_strip = 24
        threshold = max(peek_strip, self.taskbar.height() if self.taskbar.isVisible() else 0)
        in_peek_zone = pos.y() >= self.height() - threshold
        if in_peek_zone and not self.taskbar.isVisible():
            self.taskbar.setVisible(True)
        elif not in_peek_zone and self.taskbar.isVisible():
            self.taskbar.setVisible(False)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _leave_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
