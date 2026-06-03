"""The `robot` singleton — the only object students interact with.

    from pib import robot

    robot.eyes.look_left()
    robot.mouth.say("hello")

    @robot.ui.tab("Tricks").button("Wave")
    def wave():
        robot.eyes.happy()

    robot.run()
"""

from __future__ import annotations

from . import _runtime
from .eyes import Eyes
from .mouth import Mouth
from .ears import Ears
from .ui import Ui
from .exceptions import ScriptStopped


class Robot:
    def __init__(self):
        self.eyes = Eyes()
        self.mouth = Mouth()
        self.ears = Ears()
        self.ui = Ui()

    def configure(self, *, fullscreen: bool = True):
        """Tweak engine startup options. Call BEFORE any other robot.* method."""
        _runtime.configure(fullscreen=fullscreen)

    def start(self):
        """Explicitly start the engine. Optional — the first API call also starts it."""
        _runtime.transport()

    def run(self):
        """Block until the user closes the window or presses Stop in the taskbar.

        Put this at the end of your program if you want the window to stay
        open after your code has finished setting things up (e.g. for
        button-driven scripts).
        """
        t = _runtime.transport()
        try:
            t.wait_until_closed()
        except KeyboardInterrupt:
            pass
        if t.is_stopped():
            raise ScriptStopped()
