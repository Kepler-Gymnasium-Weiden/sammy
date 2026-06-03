"""sammy_lib — programmable robot for the classroom.

Students only need:

    from sammy_lib import robot
    robot.eyes.look_left()
    robot.run()
"""

from .api import Robot, PibError, ScriptStopped, EngineUnavailable, EngineCallError

#: Module-level singleton. Students never instantiate `Robot` themselves.
robot = Robot()

__all__ = ["robot", "Robot", "PibError", "ScriptStopped",
           "EngineUnavailable", "EngineCallError"]
