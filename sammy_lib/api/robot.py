"""The `robot` singleton — the only object students interact with.

    from sammy_lib import robot

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
from .body import Body
from .ui import Ui
from .exceptions import ScriptStopped


class Robot:
    def __init__(self):
        self.eyes = Eyes()
        self.mouth = Mouth()
        self.ears = Ears()
        self.body = Body()
        self.ui = Ui()

    def configure(self, *, fullscreen: bool = True,
                  robot_host: str = "localhost", robot_port: int = 9090):
        """Tweak engine startup options. Call BEFORE any other robot.* method.

        `robot_host` / `robot_port` point the body module (`robot.body.*`) at the
        robot's rosbridge. The default `localhost:9090` is right when the code
        runs on the robot itself; use the robot's IP to drive it from another
        machine.
        """
        _runtime.configure(fullscreen=fullscreen,
                           robot_host=robot_host, robot_port=robot_port)

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
