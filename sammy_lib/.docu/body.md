# `robot.body` — arms, hands and head (pib-sdk)

`robot.body` drives the **physical** robot — its arms, hands and head — through
the [pib-sdk](https://github.com/pib-rocks/pib-sdk). Unlike the eyes / mouth /
ears (which are simulated in the robot-face window), the body talks to the
robot's ROS bridge.

```python
from sammy_lib import robot

robot.configure(robot_host="192.168.0.42")   # the robot's IP; default localhost:9090

robot.body.left_arm.move(-30)                 # whole arm to -30°
robot.body.left_arm.move(-30, 0, 10, 5, 0, 0) # one angle per joint (see .joints)
robot.body.left_arm.elbow.move(20)            # one joint, by short name
robot.body.head.move(15)
robot.body.left_hand.open()                   # hand preset
robot.body.right_hand.close()

robot.body.set("left_arm", velocity=6000)     # motor settings (pib-sdk passthrough)
robot.body.move("All", 0)                     # any part / token / motor by name

q = robot.body.ik("right", [150, 0, 350])     # inverse kinematics → joint degrees
robot.body.right_arm.reach(150, 0, 350)       # IK + move, in one call
pose = robot.body.fk("right", q)              # forward kinematics → {xyz, rpy_deg, matrix}
```

Angles are degrees in **−90…90** (the SDK's range). One angle = the same value
for every joint in the group; N angles = one per joint, in `.joints` order.

## Discovery vs. connection

* **Discovery is offline.** `robot.body.parts`, `robot.body.left_arm.joints`
  and the auto-built jog sliders in the **Body** taskbar tab work even with no
  robot — they only need the pib-sdk installed.
* **Movement needs the robot.** `move` / `set` / `open` / `close` / `reach`
  require a live connection. Without one they raise `RobotNotConnected`. Check
  `robot.body.is_connected()`, or reconnect from the Body tab (or
  `robot.body.reconnect(host, port)`).

```python
from sammy_lib import robot, RobotNotConnected
try:
    robot.body.left_arm.move(-30)
except RobotNotConnected:
    print("robot offline")
```

## Why there's no wrapper to maintain

The headline design goal: **when the pib-sdk adds a motor group, you bump the
dependency and it just appears as `robot.body.<new_part>` — no code to write.**

That works because nothing in sammy_lib enumerates parts, motors or actions:

```
robot.body.left_arm.move(-30)
        │   (api/body.py — 100% generic; renders a description, forwards by name)
        ▼  transport.call("body", "move", ["left_arm", [-30]])
   BodyBackend            (_engine/modules/body_backend.py — the ONLY SDK-aware file)
     ├─ describe()        introspects the SDK's own group/token tables
     └─ move/set/preset   maps a name back to the SDK token, calls pib_sdk Write
```

* `BodyBackend.describe()` reads the SDK's **own** group table (`_groups()`) and
  command tokens (`_tokens()`, discovered by type) and returns a plain
  capability map.
* `api/body.py` builds `robot.body.<part>` purely from that map and forwards
  every command **by name**. It imports nothing from the pib-sdk.

So the only place that knows the SDK exists is two tiny introspection helpers in
`body_backend.py`, written defensively (public-name-first, private fallback). A
new arm, a new finger, a new `head_2` — all flow straight through. This is
deliberately the opposite of the hand-written recipe in
[`extending.md`](extending.md), which still applies to *simulated* modules.

## Configuration

`robot.configure(robot_host="…", robot_port=…)` must be called **before** the
first `robot.*` call (it's baked into how the engine subprocess is launched).
Defaults: `localhost:9090` — correct when the program runs on the robot itself.
