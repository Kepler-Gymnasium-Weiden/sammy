# Custom Tabs (`robot.ui`)

Students can extend the taskbar with their own tabs. The mechanism is the
same one used internally for the Eyes / Camera / Vision / Mouth / Ears tabs:
register a tab by name, attach widgets to it, and listen for events.

## Student-facing API

```python
tab = robot.ui.tab("Tricks")

# Six element types:
btn   = tab.button("Wave", on_click=wave)
lbl   = tab.label("status", "ready")
sld   = tab.slider("Speed", 0, 100, initial=50, on_change=on_speed)
tog   = tab.toggle("Lights", initial=False, on_change=on_lights)
inp   = tab.text_input("Say:", placeholder="type here", on_submit=on_say)
drop  = tab.dropdown("Mood", ["happy", "tired", "angry"], on_change=on_mood)

# Update an element later:
lbl.set("running")
sld.set(75)
```

`tab(name)` is idempotent within one run — a second call returns the same
handle. Two student programs never see each other's tabs because the engine
is restarted per program.

## How a registration flows

```
student code                        client transport               engine dispatcher           taskbar
────────────                        ────────────────               ─────────────────           ───────
tab = robot.ui.tab("Tricks")
  └─ call("ui","create_tab",["Tricks"])  ──►  send JSON  ──►  ui.create_tab("Tricks")  ──►  add_custom_tab
                                       ◄──  reply ok   ◄──

tab.button("Wave", wave)
  ├─ eid = "button_3"
  ├─ register_event_handler(eid, wave)        (client-side map)
  └─ call("ui","add_element",[ "Tricks",
                               "button",
                               "button_3",
                               {"label":"Wave"}])  ──►  ui.add_element(...)  ──►  taskbar.add_element
                                                  ◄──  reply ok
```

The element ID (`button_3`) is generated on the client side from a process-
local counter. It's used as the routing key for events.

## How an event flows back

```
user clicks "Wave"
        │
        ▼  Qt signal
QPushButton.clicked
        │
        ▼  lambda in ButtonElement
on_event("button_3", "click", None)        (UiBackend's send_event callback)
        │
        ▼  socket.sendall(JSON)
            {"type":"event","name":"ui.event",
             "payload":{"element_id":"button_3","event":"click","value":null}}
        │
        ▼  reader thread on client
Transport._handle_event
        │
        ▼  ThreadPoolExecutor.submit
worker thread runs wave()
```

The button's callback runs on a worker thread in the **student's** process,
not on the engine's GUI thread. That means:

- Calling `robot.eyes.blink()` from a callback works exactly like calling it
  from `main()` — it sends an IPC call and blocks the worker until the
  animation completes.
- Multiple clicks can run their callbacks in parallel (the executor has 4
  workers). If a callback wants to be exclusive, use a `threading.Lock`.
- An exception in a callback is caught and printed to stderr; it never kills
  the executor or the engine.

## Element types and event shapes

| Type         | Created with                                       | Event sent back               |
|--------------|----------------------------------------------------|-------------------------------|
| `button`     | `tab.button(label, on_click)`                      | `{event:"click", value:null}` |
| `label`      | `tab.label(key, text)`                             | (none — read-only)            |
| `slider`     | `tab.slider(label, min, max, initial, on_change)`  | `{event:"change", value:int}` |
| `toggle`     | `tab.toggle(label, initial, on_change)`            | `{event:"change", value:bool}`|
| `text_input` | `tab.text_input(label, initial, placeholder, on_submit)` | `{event:"submit", value:str}` |
| `dropdown`   | `tab.dropdown(label, options, initial, on_change)` | `{event:"change", value:str}` |

Adding a new element type means:

1. Add a class in `pib/_engine/ui/elements/`. It must have `widget`,
   `element_id`, `on_event`, and a `set(value)` method.
2. Register it in `pib/_engine/ui/elements/__init__.py:ELEMENT_TYPES`.
3. Add a constructor method on `Tab` in `pib/api/ui.py` that emits the right
   `add_element` call.

No transport or dispatcher changes needed — they handle the new type
transparently.
