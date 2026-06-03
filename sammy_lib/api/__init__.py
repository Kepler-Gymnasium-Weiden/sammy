"""Public API surface for pib. Students import via the package root:

    from pib import robot

Direct imports from `pib.api.*` work but aren't part of the supported surface.
"""

from .robot import Robot
from .exceptions import (
    PibError,
    ScriptStopped,
    EngineUnavailable,
    EngineCallError,
)

__all__ = ["Robot", "PibError", "ScriptStopped",
           "EngineUnavailable", "EngineCallError"]
