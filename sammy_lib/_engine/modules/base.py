"""Base class for engine-side modules.

Each module exposes a set of *commands* — methods callable by name from the
client over IPC. The dispatcher resolves `module.method(args, kwargs)` to a
plain function call on the GUI thread.

Subclasses just declare normal Python methods. Anything starting with an
underscore is considered private and not exposed.
"""

from __future__ import annotations

from typing import Any


class ModuleBase:
    """Lightweight base; mostly a marker + dispatcher helper."""

    #: Module name as seen by clients (`robot.<name>`). Override in subclass.
    name: str = ""

    def dispatch(self, method: str, args: list, kwargs: dict) -> Any:
        if method.startswith("_"):
            raise AttributeError(f"private method '{method}' not callable")
        fn = getattr(self, method, None)
        if fn is None or not callable(fn):
            raise AttributeError(f"{self.name}.{method} does not exist")
        return fn(*args, **kwargs)
