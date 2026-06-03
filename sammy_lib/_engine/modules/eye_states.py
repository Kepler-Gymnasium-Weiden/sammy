"""Internal enum of eye-animation states. Not part of the student API."""

from enum import Enum, auto


class EyeState(Enum):
    IDLE = auto()
    BLINK = auto()
    LOOK_LEFT = auto()
    LOOK_RIGHT = auto()
    LOOK_UP = auto()
    LOOK_DOWN = auto()
    HAPPY = auto()
    ANGRY = auto()
    SURPRISED = auto()
    TIRED = auto()
