# Sammy software verwenden

1. sicherstellen, dass python 3.9.x installiert ist [link](https://github.com/pib-rocks/pib-sdk/tree/PR-978#installing-a-compatible-python-version-alongside-your-current-one-in-pi-os)
2. virtual environement erstellen
    a. `python3.9 -m venv .venv`
    b. `source .venv/bin/activate`
3. bibliotheken installieren `pip install -e .`
    a. `sudo apt install -y libportaudio2`
4. in src ordner navigieren `cd src`
5. software ausühren `python3.9 main.py`

---

# Den Roboter programmieren

Du steuerst den Roboter immer nach dem gleichen Muster: `robot.<teil>.<aktion>()`.

```python
from sammy_lib import robot

robot.eyes.happy()
robot.mouth.say("Hallo, ich bin pib!")

robot.run()   # hält das Roboter-Fenster offen, bis du es schließt
```

`robot.run()` gehört ans Ende deines Programms, wenn das Fenster offen bleiben
soll (zum Beispiel, wenn du eigene Knöpfe benutzt).

---

# Augen (`robot.eyes`)

Die Augen werden im Roboter-Gesicht gezeigt. Jede Methode wartet, bis die
Animation fertig ist.

**Schauen & Blinzeln**

- `robot.eyes.look_left()` – nach links schauen
- `robot.eyes.look_right()` – nach rechts schauen
- `robot.eyes.look_up()` – nach oben schauen
- `robot.eyes.look_down()` – nach unten schauen
- `robot.eyes.blink()` – einmal blinzeln

**Gefühle zeigen**

- `robot.eyes.happy()` – fröhlich
- `robot.eyes.angry()` – wütend
- `robot.eyes.surprised()` – überrascht
- `robot.eyes.tired()` – müde
- `robot.eyes.idle()` – neutraler Blick (Ruhezustand)
- `robot.eyes.set_idle_animation(True)` – kleine Leerlauf-Bewegung an- (`True`) oder ausschalten (`False`)

**Sehen (Kamera)**

- `robot.eyes.camera_on()` / `robot.eyes.camera_off()` – Kamera ein- oder ausschalten
- `robot.eyes.what_do_you_see()` – gibt eine Liste der erkannten Dinge zurück, z. B. `['person', 'cup']`
- `robot.eyes.can_see("person")` – `True`, wenn gerade eine Person zu sehen ist

> Die erkannten Begriffe sind auf Englisch (`person`, `cat`, `cup`, …).

```python
robot.eyes.look_left()
robot.eyes.blink()
if robot.eyes.can_see("person"):
    robot.eyes.happy()

robot.run()
```

---

# Mund (`robot.mouth`)

Der Roboter spricht – komplett offline, ohne Internet.

- `robot.mouth.say("Text")` – spricht den Text laut aus (wartet, bis er fertig ist)
- `robot.mouth.set_rate(175)` – Sprechtempo in Wörtern pro Minute (ca. `175` = normal)
- `robot.mouth.set_volume(0.8)` – Lautstärke von `0.0` (leise) bis `1.0` (laut)
- `robot.mouth.set_voice("de_DE-thorsten-medium")` – eine andere Stimme wählen
  (wird beim ersten Mal automatisch heruntergeladen)

```python
robot.mouth.set_rate(150)
robot.mouth.say("Hallo! Schön, dass du da bist.")
```

---

# Ohren (`robot.ears`)

Der Roboter hört über das Mikrofon zu – ebenfalls komplett offline.

- `robot.ears.heard("hallo")` – `True`, wenn das Wort gerade gehört wurde.
  Das Zuhören startet beim ersten Aufruf automatisch.
- `robot.ears.what_did_you_hear()` – gibt den zuletzt gehörten Text als String zurück.
- `robot.ears.start_listening()` – das Zuhören von Hand starten
- `robot.ears.stop_listening()` – das Zuhören stoppen
- `robot.ears.pause_listening()` – das Zuhören pausieren, ohne das Modell zu
  verwerfen. Der Roboter hört nichts Neues mehr und vergisst das bisher Gehörte.
  Nützlich, während er selbst spricht (damit er sich nicht selbst hört).
- `robot.ears.resume_listening()` – nach dem Pausieren weiterhören. Startet
  sofort, weil das Modell geladen bleibt (kein erneutes Laden).

```python
robot.ears.start_listening()
while True:
    if robot.ears.heard("hallo"):
        robot.ears.pause_listening()   # nicht sich selbst hören
        robot.mouth.say("Hallo!")
        robot.ears.resume_listening()  # sofort wieder da, kein Neuladen
        robot.eyes.happy()
```

---

# Körperteile bewegen (Arme, Hände, Kopf)

Mit `robot.body` steuerst du die echten Körperteile des Roboters. Welche Teile
es gibt, kommt direkt aus der pib-Bibliothek – du musst nichts selbst anlegen.

```python
from sammy_lib import robot

# Einmal ganz am Anfang: dem Programm sagen, wo der Roboter steht.
# Läuft dein Programm auf dem Roboter selbst, kannst du das weglassen.
robot.configure(robot_host="192.168.0.42")   # IP-Adresse deines Roboters

# Welche Teile hat der Roboter?
print(robot.body.parts)             # z. B. ['left_arm', 'right_arm', 'left_hand', 'right_hand', 'head']
print(robot.body.left_arm.joints)   # die einzelnen Gelenke des linken Arms

robot.run()
```

## Bewegen

Winkel sind immer in **Grad** und müssen zwischen **-90 und 90** liegen.

```python
robot.body.left_arm.move(-30)       # den ganzen Arm auf -30°
robot.body.left_arm.elbow.move(20)  # nur ein einzelnes Gelenk (hier: Ellbogen)
robot.body.head.move(15)            # den Kopf drehen / neigen
robot.body.move("All", 0)           # alles auf 0° (Grundstellung)
```

Du kannst auch jedem Gelenk einen eigenen Winkel geben – ein Wert pro Gelenk,
in der Reihenfolge von `robot.body.left_arm.joints`:

```python
robot.body.left_arm.move(-30, 0, 10, 5, 0, 0)
```

## Hände öffnen und schließen

```python
robot.body.left_hand.open()
robot.body.right_hand.close()
```

## Wenn kein Roboter verbunden ist

Die Liste der Teile (`robot.body.parts`) geht immer, auch ohne Roboter. Eine
echte Bewegung braucht aber einen verbundenen Roboter – sonst gibt es einen
`RobotNotConnected`-Fehler:

```python
from sammy_lib import robot, RobotNotConnected

try:
    robot.body.left_arm.move(-30)
except RobotNotConnected:
    print("Kein Roboter verbunden!")
```

Ob der Roboter verbunden ist, siehst du auch im Roboter-Fenster unten im
Reiter **Body** – dort kannst du dich auch neu verbinden.

---

# Eigene Bedienelemente (`robot.ui`)

Du kannst eigene Reiter mit Knöpfen, Reglern und mehr bauen.
`robot.ui.tab("Name")` erstellt einen Reiter (oder holt einen vorhandenen).

- `tab.button("Text", on_click=funktion)` – ein Knopf, der `funktion()` aufruft
- `tab.label("name", "Text")` – ein Textfeld; mit `.set("neuer Text")` änderst du es später
- `tab.slider("Tempo", 0, 100, initial=50, on_change=funktion)` – ein Schieberegler (gibt den Wert an `funktion` weiter)
- `tab.toggle("An/Aus", initial=False, on_change=funktion)` – ein Schalter (gibt `True`/`False` weiter)
- `tab.text_input("Name", placeholder="...", on_submit=funktion)` – ein Eingabefeld (gibt den Text weiter)
- `tab.dropdown("Farbe", ["rot", "grün"], on_change=funktion)` – ein Auswahlmenü (gibt die Auswahl weiter)

Jedes Element kannst du einer Variablen geben, um es später mit `.set(...)` zu ändern.

```python
from sammy_lib import robot

tricks = robot.ui.tab("Tricks")
status = tricks.label("status", "bereit")

def winken():
    status.set("winke ...")
    robot.eyes.look_left()
    robot.eyes.look_right()
    status.set("bereit")

tricks.button("Winken", on_click=winken)
tricks.slider("Tempo", 0, 100, initial=50, on_change=lambda v: status.set(f"Tempo {v}"))

robot.run()
```

---

# Fehler abfangen

Manchmal löst der Roboter einen Fehler aus, den du abfangen kannst:

- `ScriptStopped` – jemand hat im Roboter-Fenster auf **Stop** gedrückt
- `RobotNotConnected` – eine Körper-Bewegung wurde versucht, ohne dass ein Roboter verbunden ist
- `PibError` – die Oberklasse aller dieser Fehler

```python
from sammy_lib import robot, ScriptStopped

try:
    robot.eyes.happy()
    robot.run()
except ScriptStopped:
    print("Programm wurde gestoppt.")
```

---

# Einstellungen (`robot.configure`)

Ganz am Anfang – **vor** dem ersten `robot.*`-Aufruf – kannst du ein paar Dinge
einstellen:

- `robot.configure(fullscreen=False)` – das Roboter-Fenster nicht im Vollbild starten
- `robot.configure(robot_host="192.168.0.42")` – die IP-Adresse deines Roboters
  (für `robot.body`; Standard ist `localhost`)
