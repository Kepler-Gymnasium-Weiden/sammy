"""Build a custom 'Tricks' tab with buttons, a slider and a status label."""

from sammy_lib import robot

tricks = robot.ui.tab("Tricks")

status = tricks.label("status", "ready")


def wave():
    status.set("waving")
    robot.eyes.look_left()
    robot.eyes.look_right()
    robot.eyes.look_left()
    robot.eyes.look_right()
    robot.eyes.idle()
    status.set("ready")


def be_happy():
    status.set("happy!")
    robot.eyes.happy()
    robot.mouth.say("Yay")
    status.set("ready")


def speed_changed(value: int):
    status.set(f"speed = {value}")


tricks.button("Wave", on_click=wave)
tricks.button("Be Happy", on_click=be_happy)
tricks.slider("Speed", 0, 100, initial=50, on_change=speed_changed)

robot.run()
