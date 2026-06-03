"""Qt widgets that back the student-facing `robot.ui` element types."""

from .button import ButtonElement
from .label import LabelElement
from .slider import SliderElement
from .toggle import ToggleElement
from .text_input import TextInputElement
from .dropdown import DropdownElement

ELEMENT_TYPES = {
    "button": ButtonElement,
    "label": LabelElement,
    "slider": SliderElement,
    "toggle": ToggleElement,
    "text_input": TextInputElement,
    "dropdown": DropdownElement,
}

__all__ = ["ELEMENT_TYPES", "ButtonElement", "LabelElement", "SliderElement",
           "ToggleElement", "TextInputElement", "DropdownElement"]
