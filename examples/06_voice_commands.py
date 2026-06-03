"""Reagiere auf gesprochene Befehle.

Beispiel-Trigger:
    "hallo"      → freundliche Begrüßung
    "wie geht"   → kurzer Status
    "müde"       → tired-Animation + Gute-Nacht-Spruch
    "wach auf"   → überraschte Augen + Begrüßung
    "tschüss"    → Blinzeln + Verabschiedung und Skript beenden

Benötigt die ears-Extras (vosk + sounddevice):

    pip install vosk sounddevice
"""

import time

from sammy_lib import robot, ScriptStopped


# Deutsche Stimme + deutsches Sprachmodell sind beides Standard,
# wir aktivieren sie hier nur zur Verdeutlichung.
robot.mouth.set_voice("de_DE-thorsten-medium")
robot.ears.start_listening()


def main():
    # Kurze Begrüßung beim Start, damit klar ist, dass der Roboter bereit ist.
    robot.eyes.happy()
    robot.mouth.say("Ich höre zu. Sag etwas zu mir.")
    robot.eyes.idle()

    try:
        while True:
            if robot.ears.heard("hallo"):
                robot.eyes.happy()
                robot.mouth.say("Hallo! Schön, dich zu hören.")
                robot.eyes.idle()

            elif robot.ears.heard("wie geht"):
                robot.eyes.happy()
                robot.mouth.say("Mir geht es gut, danke der Nachfrage.")
                robot.eyes.idle()

            elif robot.ears.heard("müde"):
                robot.eyes.tired()
                robot.mouth.say("Ja, ich werde auch langsam müde.")
                # In tired stehen lassen, bis ein anderer Befehl kommt.

            elif robot.ears.heard("wach auf"):
                robot.eyes.surprised()
                robot.mouth.say("Ich bin wach!")
                robot.eyes.idle()

            elif robot.ears.heard("tschüss"):
                robot.eyes.blink()
                robot.mouth.say("Tschüss, bis bald.")
                break

            # Klein halten, damit die Schleife schnell auf neue Phrasen reagiert,
            # aber den CPU nicht voll auslastet.
            time.sleep(0.1)
    except ScriptStopped:
        pass


if __name__ == "__main__":
    main()
    robot.run()
