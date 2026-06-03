"""`robot.body` — the robot's arms, hands and head, via the pib-sdk.

    from sammy_lib import robot

    robot.body.left_arm.move(-30)                 # whole arm to -30°
    robot.body.left_arm.move(-30, 0, 10, 5, 0, 0) # one angle per joint
    robot.body.left_arm.elbow.move(20)            # a single joint
    robot.body.left_hand.open()                   # hand preset
    robot.body.set("left_arm", velocity=6000)     # motor settings
    robot.body.move("All", 0)                     # everything to 0°

    q = robot.body.ik("right", [150, 0, 350])     # inverse kinematics
    robot.body.right_arm.reach(150, 0, 350)       # IK + move in one call

This facade contains **no** knowledge of which parts or motors exist — it asks
the engine (`describe()`) once and builds itself from the answer. When the
pib-sdk gains a new motor group, it appears here as a new `robot.body.<part>`
with no change to this file. See `sammy_lib/_engine/modules/body_backend.py`.

Movement requires a live connection to the robot; part *discovery*
(`robot.body.parts`, `.joints`) works offline. Commands that need the robot
while it's unreachable raise `RobotNotConnected`.
"""

from __future__ import annotations

from typing import Optional

from . import _runtime
from .exceptions import EngineCallError, RobotNotConnected


def _call(method: str, args: list | None = None,
          kwargs: dict | None = None):
    """Forward to the engine `body` backend, mapping the not-connected error."""
    try:
        return _runtime.transport().call("body", method, args, kwargs)
    except EngineCallError as exc:
        if getattr(exc, "remote_type", "") == "RobotNotConnected":
            raise RobotNotConnected(str(exc)) from None
        raise


def _side_of(part_name: str) -> str:
    return "right" if "right" in part_name else "left"


def _short_alias(motor: str) -> str:
    """`upper_arm_left_rotation` → `upper_arm_rotation` (drop side segments)."""
    return "_".join(t for t in motor.split("_") if t not in ("left", "right"))


class _Joint:
    """A single motor, e.g. `robot.body.left_arm.elbow`."""

    def __init__(self, motor_name: str):
        self._name = motor_name

    @property
    def name(self) -> str:
        return self._name

    def move(self, degree: float) -> bool:
        return _call("move", [self._name, [float(degree)]])

    def set(self, **settings) -> bool:
        return _call("set", [self._name, settings])

    def __repr__(self) -> str:
        return f"<joint {self._name}>"


class _Part:
    """One motor group, e.g. `robot.body.left_arm`. Built from `describe()`."""

    def __init__(self, name: str, info: dict):
        self._name = name
        self._kind = info.get("kind", "group")
        self._joint_names = list(info.get("joints", []))
        self._presets = set(info.get("presets", []))
        # alias → motor, for short single-joint access (skip ambiguous aliases)
        aliases: dict[str, str] = {}
        for motor in self._joint_names:
            alias = _short_alias(motor)
            aliases[alias] = "" if alias in aliases else motor
        self._aliases = {a: m for a, m in aliases.items() if m}

    # ---- introspection -------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def joints(self) -> list[str]:
        return list(self._joint_names)

    # ---- movement ------------------------------------------------------

    def move(self, *degrees: float) -> bool:
        """Move the whole group. One value = same angle for every joint;
        otherwise pass exactly one angle per joint (see `.joints`)."""
        if not degrees:
            raise ValueError("move() needs at least one angle")
        return _call("move", [self._name, [float(d) for d in degrees]])

    def set(self, **settings) -> bool:
        """Apply motor settings to every joint in the group."""
        return _call("set", [self._name, settings])

    def joint(self, name: str) -> _Joint:
        """Explicit single-joint handle by full or short name."""
        motor = self._resolve_joint(name)
        if motor is None:
            raise AttributeError(
                f"{self._name} has no joint '{name}'. "
                f"Joints: {', '.join(self._joint_names)}")
        return _Joint(motor)

    # ---- hand presets (only present on hand-like parts) ----------------

    def open(self) -> bool:
        return self._preset("open")

    def close(self) -> bool:
        return self._preset("close")

    def _preset(self, action: str) -> bool:
        if action not in self._presets:
            raise AttributeError(f"'{self._name}' has no '{action}' preset")
        return _call("preset", [f"{action}_{self._name}"])

    # ---- arm convenience: inverse kinematics then move -----------------

    def reach(self, x: float, y: float, z: float,
              rpy_deg: Optional[list] = None) -> bool:
        """Point this arm's end-effector at (x, y, z) in mm via IK, then move."""
        if self._kind != "arm":
            raise AttributeError(f"reach() is only available on arms, not '{self._name}'")
        angles = _call("ik", [_side_of(self._name), [float(x), float(y), float(z)],
                              list(rpy_deg) if rpy_deg is not None else None])
        return self.move(*angles[:len(self._joint_names)])

    # ---- short single-joint access: robot.body.left_arm.elbow ----------

    def __getattr__(self, item: str) -> _Joint:
        if item.startswith("_"):
            raise AttributeError(item)
        motor = self._resolve_joint(item)
        if motor is None:
            raise AttributeError(
                f"'{self._name}' has no joint '{item}'. "
                f"Joints: {', '.join(self._joint_names)}")
        return _Joint(motor)

    def _resolve_joint(self, name: str) -> Optional[str]:
        if name in self._joint_names:
            return name
        return self._aliases.get(name)

    def __repr__(self) -> str:
        return f"<part {self._name}: {', '.join(self._joint_names)}>"


class Body:
    """`robot.body` — auto-built from the SDK's capability description."""

    def __init__(self):
        self._desc: Optional[dict] = None
        self._parts: dict[str, _Part] = {}

    # ---- discovery -----------------------------------------------------

    def _describe(self) -> dict:
        """Fetch (and cache) the static capability map. Starts the engine."""
        if self._desc is None:
            self._desc = _runtime.transport().call("body", "describe") or {}
        return self._desc

    @property
    def parts(self) -> list[str]:
        """Names of every available part, e.g. ['left_arm', 'head', …]."""
        return list(self._describe().get("parts", {}))

    @property
    def available(self) -> bool:
        """True if the pib-sdk is installed in the engine."""
        return bool(self._describe().get("available", False))

    def is_connected(self) -> bool:
        """True if the engine currently has a live connection to the robot."""
        return bool(_call("is_connected"))

    def connection(self) -> dict:
        """{host, port, available, connected, error}."""
        return _call("connection_info") or {}

    def reconnect(self, host: Optional[str] = None,
                  port: Optional[int] = None) -> bool:
        """(Re)connect to the robot, optionally at a new host/port."""
        return bool(_call("reconnect", [host, port]))

    # ---- whole-body / by-name commands --------------------------------

    def move(self, target: str, *degrees: float) -> bool:
        """Move any part, group token ('All') or motor by name."""
        if not degrees:
            raise ValueError("move() needs at least one angle")
        return _call("move", [target, [float(d) for d in degrees]])

    def set(self, target: str, **settings) -> bool:
        """Apply motor settings to any part, token or motor by name."""
        return _call("set", [target, settings])

    def zero(self) -> bool:
        """Move every motor to 0°."""
        return _call("move", ["All", [0.0]])

    # ---- kinematics ----------------------------------------------------

    def ik(self, side: str, xyz: list, rpy_deg: Optional[list] = None,
           **kwargs) -> list:
        """Inverse kinematics for 'right'/'left' arm → joint angles (degrees)."""
        return _call("ik", [side, list(xyz),
                            list(rpy_deg) if rpy_deg is not None else None],
                     kwargs or None)

    def fk(self, side: str, q_deg: list) -> dict:
        """Forward kinematics → {xyz (mm), rpy_deg, matrix}."""
        return _call("fk", [side, [float(v) for v in q_deg]])

    # ---- dynamic part access: robot.body.left_arm ----------------------

    def __getattr__(self, name: str) -> _Part:
        # Never trigger engine start / describe() on private or dunder lookups.
        if name.startswith("_"):
            raise AttributeError(name)
        parts = self._describe().get("parts", {})
        if name in parts:
            if name not in self._parts:
                self._parts[name] = _Part(name, parts[name])
            return self._parts[name]
        raise AttributeError(
            f"robot.body has no part '{name}'. "
            f"Available: {', '.join(parts) or '(none — is the pib-sdk installed?)'}")
