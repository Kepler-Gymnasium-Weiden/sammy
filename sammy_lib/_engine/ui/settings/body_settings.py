"""Body settings panel — connection status, reconnect, and per-part jog sliders.

Everything below the connection controls is built from the backend's
`describe()` output, so the panel grows automatically when the pib-sdk gains a
new motor group — same principle as the `robot.body` facade.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QFrame,
)

from ...modules.body_backend import BodyBackend, RobotNotConnected


class BodySettingsPanel(QWidget):
    def __init__(self, body: BodyBackend, parent=None):
        super().__init__(parent)
        self._body = body

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addWidget(QLabel("<b>Body</b>"))

        if not self._body.is_available():
            info = self._body.connection_info().get("error", "")
            root.addWidget(QLabel("pib-sdk not installed — body control unavailable."))
            if info:
                note = QLabel(info)
                note.setStyleSheet("color: #c66; font-style: italic;")
                note.setWordWrap(True)
                root.addWidget(note)
            root.addStretch(1)
            return

        # --- connection row -------------------------------------------------
        conn = self._body.connection_info()
        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Robot:"))
        self._host = QLineEdit(str(conn.get("host", "localhost")))
        self._host.setFixedWidth(140)
        host_row.addWidget(self._host)
        host_row.addWidget(QLabel(":"))
        self._port = QLineEdit(str(conn.get("port", 9090)))
        self._port.setFixedWidth(64)
        host_row.addWidget(self._port)
        self._reconnect_btn = QPushButton("Reconnect")
        self._reconnect_btn.clicked.connect(self._on_reconnect)
        host_row.addWidget(self._reconnect_btn)
        host_row.addStretch(1)
        root.addLayout(host_row)

        self._status = QLabel("")
        root.addWidget(self._status)

        # --- quick actions --------------------------------------------------
        actions = QHBoxLayout()
        zero_btn = QPushButton("All → 0°")
        zero_btn.clicked.connect(lambda: self._safe(lambda: self._body.move("All", [0.0])))
        actions.addWidget(zero_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        # --- per-part jog sliders (built from describe()) -------------------
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3a3f4b;")
        root.addWidget(line)

        desc = self._body.describe()
        for part_name, info in desc.get("parts", {}).items():
            root.addWidget(self._build_part_row(part_name, info))

        root.addStretch(1)

        # Reflect the background connection attempt as it settles.
        self._refresh_status()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start()

    # ---- per-part UI ------------------------------------------------------

    def _build_part_row(self, part_name: str, info: dict) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setSpacing(6)

        title = QLabel(f"<b>{part_name}</b> <span style='color:#888'>({info.get('kind','')})</span>")
        grid.addWidget(title, 0, 0, 1, 3)

        # Whole-group jog slider (uniform angle to every joint in the group).
        grid.addWidget(QLabel("all"), 1, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-90, 90)
        slider.setValue(0)
        value_lbl = QLabel("0°")
        value_lbl.setFixedWidth(40)
        slider.valueChanged.connect(lambda v, lbl=value_lbl: lbl.setText(f"{v}°"))
        slider.sliderReleased.connect(
            lambda p=part_name, s=slider: self._safe(lambda: self._body.move(p, [float(s.value())])))
        grid.addWidget(slider, 1, 1)
        grid.addWidget(value_lbl, 1, 2)

        # Hand presets, when advertised.
        presets = info.get("presets", [])
        if presets:
            preset_row = QHBoxLayout()
            for action in presets:
                btn = QPushButton(action)
                btn.clicked.connect(
                    lambda _c=False, p=part_name, a=action:
                        self._safe(lambda: self._body.preset(f"{a}_{p}")))
                preset_row.addWidget(btn)
            preset_row.addStretch(1)
            holder = QWidget()
            holder.setLayout(preset_row)
            grid.addWidget(holder, 2, 0, 1, 3)

        return box

    # ---- connection -------------------------------------------------------

    def _on_reconnect(self):
        host = self._host.text().strip() or "localhost"
        try:
            port = int(self._port.text().strip() or "9090")
        except ValueError:
            self._status.setText("Port must be a number.")
            self._set_status_color(False)
            return
        self._reconnect_btn.setEnabled(False)
        self._status.setText(f"Connecting to {host}:{port} …")
        self._set_status_color(None)
        try:
            self._body.reconnect(host, port)   # nested event loop keeps UI alive
        except Exception as exc:
            self._status.setText(f"Reconnect failed: {exc}")
            self._set_status_color(False)
        finally:
            self._reconnect_btn.setEnabled(True)
            self._refresh_status()

    def _refresh_status(self):
        conn = self._body.connection_info()
        if conn.get("connected"):
            self._status.setText(f"● Connected to {conn['host']}:{conn['port']}")
            self._set_status_color(True)
        else:
            err = conn.get("error", "")
            tail = f" — {err}" if err else ""
            self._status.setText(f"○ Not connected ({conn['host']}:{conn['port']}){tail}")
            self._set_status_color(False)

    def _set_status_color(self, ok):
        if ok is True:
            self._status.setStyleSheet("color: #5c5;")
        elif ok is False:
            self._status.setStyleSheet("color: #c66;")
        else:
            self._status.setStyleSheet("color: #aaa; font-style: italic;")

    # ---- helpers ----------------------------------------------------------

    def _safe(self, fn):
        """Run a body command from the GUI, surfacing errors in the status line."""
        try:
            fn()
        except RobotNotConnected as exc:
            self._status.setText(f"Not connected: {exc}")
            self._set_status_color(False)
        except Exception as exc:
            self._status.setText(f"{type(exc).__name__}: {exc}")
            self._set_status_color(False)
