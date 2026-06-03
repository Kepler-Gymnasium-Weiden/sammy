from sammy_lib import robot

robot.configure(fullscreen=False)

robot.eyes.look_left()
robot.eyes.look_right()
robot.eyes.blink()
robot.mouth.say("Hello, I am the robot.")
robot.eyes.happy()

# Keep the window open until the user closes it or presses Stop.
robot.run()