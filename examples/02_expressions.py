"""Cycle through every expression. Good test of the animation system."""

import time

from pib import robot

for state in ("happy", "angry", "surprised", "tired", "idle"):
    getattr(robot.eyes, state)()
    time.sleep(1.0)

robot.run()
