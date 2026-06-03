"""Body backend — the robot's arms / hands / head, driven by the **pib-sdk**.

This is the *only* file in sammy_lib that knows the pib-sdk exists. Everything
else (the `robot.body.*` facade, the settings panel) is generic: it renders
whatever `describe()` reports and forwards commands by name. That is what lets
the body grow with the SDK — when pib-sdk adds a motor group, it shows up as a
new `robot.body.<part>` automatically, with no code change here beyond bumping
the dependency.

How it stays SDK-agnostic
-------------------------
The SDK's own tables are the source of truth:

  * ``_groups()`` reads the motor-group map (right_arm → [shoulder…, elbow…]).
  * ``_tokens()`` reads the module-level command tokens (``All``,
    ``open_left_hand``, …) by *type*, so new tokens are discovered too.

`describe()` turns those into a plain JSON-friendly capability map; `move` /
`set` / `preset` translate a part name back into the matching SDK token (or fall
back to raw motor names) and call ``Write``.

Threading / connection
-----------------------
``pib_sdk.control.Write()`` opens a rosbridge connection and *blocks up to 5 s*,
raising if the robot isn't reachable — so we connect on a background thread at
startup and never block engine boot. Each SDK call then runs on a short-lived
worker ``QThread`` while the GUI thread waits in a nested ``QEventLoop`` (the
same trick `mouth_backend.py` uses for speech), so a slow ROS service call never
freezes the robot face. A lock serialises access to the single ``Write``.

Part *discovery* (`describe`) needs only that the SDK is importable — no robot.
Actual motion needs a live connection; without one, commands raise
``RobotNotConnected`` (the name is matched client-side and re-raised as
``sammy_lib.RobotNotConnected``).
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from PyQt6.QtCore import QEventLoop, QThread

from .base import ModuleBase

# pib-sdk control is light to import (just roslibpy); guard it like the other
# optional backends (see vision_backend.py). Kinematics is imported lazily in
# `_kin()` because it pulls in heavy numeric deps (roboticstoolbox/scipy).
try:
    import pib_sdk.control as _pibctl  # type: ignore
    _HAVE_SDK = True
    _IMPORT_ERROR = ""
except Exception as _exc:  # pragma: no cover - depends on the environment
    _pibctl = None  # type: ignore
    _HAVE_SDK = False
    _IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"


# Degrees the SDK accepts on every joint.
_DEG_MIN = -90.0
_DEG_MAX = 90.0


class RobotNotConnected(RuntimeError):
    """Raised engine-side when a command needs a live ROS connection.

    The class *name* travels back to the client as the error type, where the
    facade re-raises it as the public ``sammy_lib.RobotNotConnected``.
    """


class _Job(QThread):
    """Runs one callable off the GUI thread; stashes its result or exception."""

    def __init__(self, fn: Callable[[], Any], parent=None):
        super().__init__(parent)
        self._fn = fn
        self.result: Any = None
        self.error: Optional[BaseException] = None

    def run(self):
        try:
            self.result = self._fn()
        except BaseException as exc:  # re-raised on the GUI thread by _run_blocking
            self.error = exc


class BodyBackend(ModuleBase):
    name = "body"

    def __init__(self, host: str = "localhost", port: int = 9090):
        self._host = str(host)
        self._port = int(port)
        self._write = None              # pib_sdk.control.Write once connected
        self._connected = False
        self._conn_error = ""
        self._import_error = _IMPORT_ERROR
        self._sdk_lock = threading.Lock()
        self._kinmod = None             # lazily-imported pib_sdk.kinematics

        if _HAVE_SDK:
            # Connect without blocking engine startup; the robot may not be up
            # yet (or ever, in a face-only classroom demo).
            threading.Thread(target=self._do_connect, name="pib-body-connect",
                             daemon=True).start()

    # ---- capability checks ------------------------------------------------

    def is_available(self) -> bool:
        """True if the pib-sdk is importable (independent of a live robot)."""
        return _HAVE_SDK

    def is_connected(self) -> bool:
        return bool(self._connected)

    def connection_info(self) -> dict:
        return {
            "host": self._host,
            "port": self._port,
            "available": _HAVE_SDK,
            "connected": self._connected,
            "error": self._conn_error or self._import_error,
        }

    # ---- introspection: the single point of pib-sdk coupling --------------

    @staticmethod
    def _groups() -> dict:
        """{group_name: [motor_name, ...]} straight from the SDK.

        Prefers a public table if the SDK ever exposes one, else the current
        private ``_STATIC_GROUPS``. Everything downstream is derived from this.
        """
        if not _HAVE_SDK:
            return {}
        for attr in ("STATIC_GROUPS", "GROUPS", "_STATIC_GROUPS"):
            table = getattr(_pibctl, attr, None)
            if isinstance(table, dict) and table:
                return table
        return {}

    @staticmethod
    def _tokens() -> dict:
        """{token_name: token} for every module-level command token.

        Discovered by *type* (``_Token``) so new tokens (groups, hand presets,
        whatever the SDK adds) are picked up without naming them here.
        """
        if not _HAVE_SDK:
            return {}
        token_cls = getattr(_pibctl, "_Token", None)
        if token_cls is None:
            return {}
        return {n: o for n, o in vars(_pibctl).items() if isinstance(o, token_cls)}

    def describe(self) -> dict:
        """JSON-safe capability map. Works with no robot connected."""
        if not _HAVE_SDK:
            return {
                "available": False,
                "connected": False,
                "parts": {},
                "globals": [],
                "limits": {"degree_min": _DEG_MIN, "degree_max": _DEG_MAX},
                "kinematics": {"sides": [], "available": False},
                "connection": {"host": self._host, "port": self._port},
                "error": self._import_error,
            }

        groups = self._groups()
        tokens = self._tokens()
        parts: dict[str, dict] = {}
        for gname, motors in groups.items():
            parts[gname] = {
                "kind": _classify(gname),
                "joints": list(motors),
                # hand-style presets exposed only when the matching tokens exist
                "presets": [a for a in ("open", "close")
                            if f"{a}_{gname}" in tokens],
            }
        return {
            "available": True,
            "connected": self._connected,   # a snapshot; clients poll is_connected()
            "parts": parts,
            "globals": [n for n in tokens if n == "All"],
            "limits": {"degree_min": _DEG_MIN, "degree_max": _DEG_MAX},
            "kinematics": {"sides": ["right", "left"], "available": True},
            "connection": {"host": self._host, "port": self._port},
        }

    # ---- movement / settings / presets ------------------------------------

    def move(self, target: Any, degrees: list) -> bool:
        """Move a part/group/motor. One angle = uniform; N angles = per-joint."""
        degs = [self._check_deg(d) for d in (degrees or [])]
        if not degs:
            raise ValueError("move() needs at least one angle")

        def work():
            with self._sdk_lock:
                w = self._require_write()
                return self._do_move(w, target, degs)

        return bool(self._run_blocking(work))

    def set(self, target: Any, settings: dict) -> bool:
        """Apply motor settings (velocity, acceleration, default preset, …)."""
        settings = dict(settings or {})

        def work():
            with self._sdk_lock:
                w = self._require_write()
                spec = self._token_or_name(target)
                if spec is not None:
                    return bool(w.set(spec, **settings))
                motors = self._groups().get(target, [target])
                return bool(w.set(*motors, **settings))

        return bool(self._run_blocking(work))

    def preset(self, name: str) -> bool:
        """Run a named SDK action token, e.g. ``open_left_hand``."""
        def work():
            with self._sdk_lock:
                w = self._require_write()
                token = self._tokens().get(name)
                if token is None:
                    raise ValueError(f"unknown preset '{name}'")
                return bool(w.move(token))

        return bool(self._run_blocking(work))

    # ---- kinematics (pure compute; no robot needed) -----------------------

    def ik(self, side: str, xyz: list, rpy_deg: Optional[list] = None,
           **kwargs) -> list:
        """Inverse kinematics → list of joint angles in degrees."""
        def work():
            kin = self._kin()
            q = kin.ik(side, xyz=list(xyz),
                       rpy_deg=(list(rpy_deg) if rpy_deg is not None else None),
                       **kwargs)
            return [float(v) for v in q]

        return self._run_blocking(work)

    def fk(self, side: str, q_deg: list) -> dict:
        """Forward kinematics → {xyz (mm), rpy_deg, matrix (4×4)}."""
        def work():
            kin = self._kin()
            pose = kin.fk(side, [float(v) for v in q_deg])
            matrix = [[float(c) for c in row] for row in pose.A]
            try:
                rpy = [float(v) for v in pose.rpy(unit="deg")]
            except Exception:
                rpy = None
            return {
                "xyz": [matrix[0][3], matrix[1][3], matrix[2][3]],
                "rpy_deg": rpy,
                "matrix": matrix,
            }

        return self._run_blocking(work)

    # ---- connection management --------------------------------------------

    def reconnect(self, host: Optional[str] = None,
                  port: Optional[int] = None) -> bool:
        """(Re)connect to the robot, optionally pointing at a new host/port."""
        if host is not None:
            self._host = str(host)
        if port is not None:
            self._port = int(port)
        if not _HAVE_SDK:
            raise RobotNotConnected(self._import_error or "pib-sdk is not installed")
        return bool(self._run_blocking(self._do_connect))

    def _do_connect(self) -> bool:
        """Open a fresh ``Write``. Blocks up to ~5 s; safe off the GUI thread."""
        if not _HAVE_SDK:
            return False
        with self._sdk_lock:
            self._teardown_locked()
            try:
                self._write = _pibctl.Write(host=self._host, port=self._port)
                self._connected = True
                self._conn_error = ""
                print(f"[body] connected to robot at {self._host}:{self._port}",
                      flush=True)
                return True
            except Exception as exc:
                self._write = None
                self._connected = False
                self._conn_error = f"{type(exc).__name__}: {exc}"
                print(f"[body] not connected ({self._host}:{self._port}): "
                      f"{self._conn_error}", flush=True)
                return False

    def _teardown_locked(self):
        w, self._write, self._connected = self._write, None, False
        if w is not None:
            try:
                ros = getattr(w, "ros", None)
                if ros is not None and getattr(ros, "is_connected", False):
                    ros.terminate()
            except Exception:
                pass

    # ---- internals --------------------------------------------------------

    def _require_write(self):
        if not _HAVE_SDK:
            raise RobotNotConnected(self._import_error or "pib-sdk is not installed")
        if not self._connected or self._write is None:
            detail = f" ({self._conn_error})" if self._conn_error else ""
            raise RobotNotConnected(
                f"robot not connected at {self._host}:{self._port}{detail}")
        return self._write

    def _do_move(self, w, target: Any, degrees: list) -> bool:
        spec = self._token_or_name(target)
        if spec is not None:
            # Write.move(token_or_name, d)           → uniform
            # Write.move(token_or_name, d1, …, dN)   → per-joint vector
            return bool(w.move(spec, *degrees))
        # Group known in the table but without a module-level token: expand to
        # explicit (motor, degree) pairs, which Write.move also accepts.
        motors = self._groups().get(target, [target])
        if len(degrees) == 1:
            degrees = degrees * len(motors)
        if len(degrees) != len(motors):
            raise ValueError(
                f"{target}: expected 1 or {len(motors)} angle(s), got {len(degrees)}")
        pairs: list = []
        for motor, deg in zip(motors, degrees):
            pairs.extend([motor, deg])
        return bool(w.move(*pairs))

    @classmethod
    def _token_or_name(cls, target: Any):
        """A group/token name → its SDK token object; a motor name → the string.

        Returns ``None`` only for a group that's in the table but has no
        module-level token (caller then falls back to motor-name pairs).
        """
        if not isinstance(target, str):
            return target
        if target in cls._groups() or target == "All" or target in cls._tokens():
            return getattr(_pibctl, target, None)
        return target  # a bare motor name like "elbow_right"

    def _kin(self):
        if self._kinmod is None:
            import pib_sdk.kinematics as kin  # heavy import, done on demand
            self._kinmod = kin
        return self._kinmod

    @staticmethod
    def _check_deg(value) -> float:
        d = float(value)
        if not _DEG_MIN <= d <= _DEG_MAX:
            raise ValueError(
                f"angle must be between {_DEG_MIN:.0f} and {_DEG_MAX:.0f} (got {d})")
        return d

    def _run_blocking(self, fn: Callable[[], Any]) -> Any:
        """Run ``fn`` on a worker thread, keeping the GUI event loop alive.

        Mirrors the speech worker in ``mouth_backend.py``: the face keeps
        animating while a (possibly slow) ROS call runs.
        """
        job = _Job(fn)
        loop = QEventLoop()
        job.finished.connect(loop.quit)
        job.start()
        loop.exec()
        job.wait()
        if job.error is not None:
            raise job.error
        return job.result


def _classify(group_name: str) -> str:
    """Best-effort body-part category from a group name (for the UI only)."""
    name = group_name.lower()
    if "hand" in name or "finger" in name:
        return "hand"
    if "head" in name or "neck" in name:
        return "head"
    if "arm" in name:
        return "arm"
    return "group"
