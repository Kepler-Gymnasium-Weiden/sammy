"""Move the robot's body: arms, hands and head, via the pib-sdk.

Movement needs a real robot (a rosbridge the pib-sdk can reach). Point the
library at it with `robot.configure(...)` BEFORE the first robot.* call — the
default `localhost:9090` is right when this runs on the robot itself. With no
robot connected, the parts still list (discovery works offline) but a `move`
raises `RobotNotConnected`.

Nothing here is hand-written per part: `robot.body.<part>` is built from
whatever the pib-sdk reports, so new SDK parts just appear.
"""

from sammy_lib import robot, RobotNotConnected

# Drive a pib on the network instead of localhost by passing its IP:
#   robot.configure(robot_host="192.168.0.42")
robot.configure(fullscreen=False)

# Discovery works with or without a robot connected.
print("Body parts:", robot.body.parts)
print("Left arm joints:", robot.body.left_arm.joints)

try:
    robot.body.set("All", default=True)        # apply the SDK's default motor settings
    robot.body.move("All", 0)                  # everything to a neutral 0°

    robot.body.left_arm.move(-30)              # whole left arm to -30°
    robot.body.right_arm.elbow.move(20)        # a single joint by short name
    robot.body.head.move(15)                   # turn/tilt the head

    robot.body.left_hand.open()                # hand preset
    robot.body.right_hand.close()

    # Inverse kinematics: reach the right hand to a point (mm), then move there.
    robot.body.right_arm.reach(150, 0, 350)

    robot.eyes.happy()
    robot.mouth.say("Look, I can move!")
except RobotNotConnected as exc:
    print("No robot connected:", exc)
    robot.mouth.say("I cannot feel my arms. Is the robot switched on?")

robot.run()
