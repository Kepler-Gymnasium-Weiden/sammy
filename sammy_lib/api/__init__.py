"""Public API surface for sammy_lib. Students import via the package root:

    from sammy_lib import robot

Direct imports from `sammy_lib.api.*` work but aren't part of the supported surface.
"""

from .robot import Robot
from .exceptions import (
    PibError,
    ScriptStopped,
    EngineUnavailable,
    EngineCallError,
    RobotNotConnected,
)

__all__ = ["Robot", "PibError", "ScriptStopped",
           "EngineUnavailable", "EngineCallError", "RobotNotConnected"]
