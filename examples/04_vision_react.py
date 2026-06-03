"""React when the camera sees something. Requires opencv-python + ultralytics.

The camera starts on the first call to robot.eyes.what_do_you_see().
Press Stop in the taskbar to halt the loop.
"""

import time

from pib import robot, ScriptStopped


def main():
    robot.eyes.camera_on()
    seen_before: set[str] = set()
    try:
        while True:
            labels = robot.eyes.what_do_you_see()
            new = [l for l in labels if l not in seen_before]
            seen_before.update(labels)

            if "person" in new:
                robot.eyes.surprised()
                robot.mouth.say("Hello there")
            if "cup" in new:
                robot.eyes.happy()
                robot.mouth.say("Nice cup")
            if "cat" in new or "dog" in new:
                robot.eyes.happy()
                robot.mouth.say("An animal")

            time.sleep(1.0)
    except ScriptStopped:
        pass


if __name__ == "__main__":
    main()
    robot.run()
