# Adding a new module

Suppose you want to add `robot.arm.wave()`. There are three files plus one
line in the dispatcher.

## 1. Engine-side backend

`sammy_lib/_engine/modules/arm_backend.py`:

```python
from .base import ModuleBase


class ArmBackend(ModuleBase):
    name = "arm"

    def __init__(self, controller):
        self._controller = controller     # whatever drives the real hardware

    def wave(self):
        self._controller.wave()           # may block; that's fine on GUI thread

    def raise_left(self):
        self._controller.move("left", up=True)

    def raise_right(self):
        self._controller.move("right", up=True)
```

`ModuleBase.dispatch()` handles routing — anything without a leading
underscore is callable from the client.

## 2. Client-side facade

`sammy_lib/api/arm.py`:

```python
from . import _runtime


class Arm:
    def wave(self):
        _runtime.transport().call("arm", "wave")

    def raise_left(self):
        _runtime.transport().call("arm", "raise_left")

    def raise_right(self):
        _runtime.transport().call("arm", "raise_right")
```

## 3. Optional settings panel

`sammy_lib/_engine/ui/settings/arm_settings.py` — a `QWidget` with whatever
controls you want exposed (speed slider, emergency-stop, calibration).

## 4. Wire it up

In `sammy_lib/_engine/app.py`:

```python
from .modules.arm_backend import ArmBackend
from .ui.settings.arm_settings import ArmSettingsPanel

arm_controller = ...                       # however you build the hardware controller
arm = ArmBackend(arm_controller)
window.taskbar.add_tab("Arm", ArmSettingsPanel(arm))

dispatcher = Dispatcher({
    "eyes": eyes,
    "arm":  arm,                           # ← new
    "mouth": mouth,
    "ears": ears,
    "ui": ui,
})
```

In `sammy_lib/api/robot.py`:

```python
from .arm import Arm

class Robot:
    def __init__(self):
        self.eyes = Eyes()
        self.arm  = Arm()                  # ← new
        ...
```

Students can now write:

```python
from sammy_lib import robot
robot.eyes.happy()
robot.arm.wave()
robot.run()
```

That's the whole pattern. Modules share zero state apart from the engine
window they live in.
