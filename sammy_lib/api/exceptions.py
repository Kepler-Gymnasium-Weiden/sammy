"""Exceptions raised by the `sammy_lib` student-facing API."""


class PibError(Exception):
    """Base class for everything the library raises at student code."""


class ScriptStopped(PibError):
    """Raised inside the student script when the user presses Stop in the taskbar.

    Catch it at the top of your program if you want a custom shutdown, e.g.:

        from sammy_lib import robot, ScriptStopped
        try:
            ...
            robot.run()
        except ScriptStopped:
            print("script stopped")
    """


class EngineUnavailable(PibError):
    """The robot engine could not be started or has gone away."""


class EngineCallError(PibError):
    """The engine reported an error executing a method call."""

    def __init__(self, message: str, *, remote_type: str = "Error",
                 trace: str = ""):
        super().__init__(message)
        self.remote_type = remote_type
        self.remote_trace = trace


class RobotNotConnected(PibError):
    """A body command needed the physical robot, but no ROS bridge is connected.

    Movement, settings and hand presets (`robot.body.*`) all require a live
    connection to the robot's rosbridge. Part *discovery* (e.g.
    `robot.body.parts`) works offline, so this is only raised when you try to
    actually move something with no robot reachable. Check the Body tab in the
    robot window, or call `robot.body.reconnect()` once the robot is up.
    """
