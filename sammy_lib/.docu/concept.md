# Concept

## Goals

1. **Teach beginners to "program" with a tiny, friendly API** — `robot.eyes.look_left()`, `robot.mouth.say("hi")`, `robot.ui.tab(...).button(...)`. No Qt, no threads, no async.
2. **The robot face is its own program** — the GUI always runs fullscreen, with a taskbar for module settings and any custom tabs the student adds. Students never have to know it's a separate process.
3. **A buggy student program must not take down the robot face.** A classroom of children writing their first loops will produce infinite recursion, exceptions, and freezes — the GUI has to keep running so the teacher can demo, intervene, or restart.
4. **Modules are pluggable.** Eyes / mouth / ears / vision share one pattern; future modules (arm, motors, lights) drop in the same way.
5. **Privacy by construction.** Any model that processes camera frames must run locally — no images go to external services. Required by GDPR, the EU AI Act, and the organisation's information-security policy.

## Two packages, one Python install

```
pib-eyes/
  pib/                    ← single installable package
    api/                  ← student-facing API surface
    _engine/              ← private GUI subprocess (leading underscore = "don't touch")
  examples/               ← teacher-facing reference programs
```

Both halves live in the same package. A single `pip install` (or PYTHONPATH
entry) is enough; `pib/api/_runtime.py` knows where to find `pib._engine`
because it imports it by name.

## Two-process model

Students write a regular Python program — for instance `examples/01_hello.py`.
Running `python 01_hello.py` does this:

1. `from pib import robot` — loads `pib/__init__.py`, which instantiates the
   `Robot` singleton. Nothing visible happens yet; the engine is **not** started.
2. The first call (e.g. `robot.eyes.look_left()`) triggers
   `pib/api/_runtime.py:Runtime.ensure_started()`, which:
   - Spawns `python -m pib._engine --port 0 --fullscreen` as a subprocess.
   - Reads `PORT=<n>` from the child's stdout to learn the TCP port.
   - Opens a `Transport` socket to `127.0.0.1:<port>`.
3. The call is serialised to JSON, sent to the engine, and the student's thread
   blocks until the engine replies. The engine runs the animation on the Qt
   thread, then sends the reply. From the student's perspective the method
   call is fully synchronous.
4. When the student program exits, an `atexit` hook in `_runtime.py` closes the
   socket. The engine sees EOF and shuts down its Qt application.

The Qt event loop lives entirely in the engine process, on its own main
thread — exactly where Qt expects it. The student's program runs on its own
main thread and uses only standard-library threading. There is no chance of a
student script crashing the GUI: process isolation does that for free.

## Module pattern

Every module follows the same three-layer recipe:

| Layer | Where | Job |
|-------|-------|-----|
| **Facade** (student-facing) | `pib/api/<name>.py` | Tiny class with one method per command; each method just calls `_runtime.transport().call(module, method, args)`. |
| **Backend** (engine-side)   | `pib/_engine/modules/<name>_backend.py` | Subclass of `ModuleBase`; implements the commands. May touch Qt widgets directly because it runs on the GUI thread. |
| **Settings panel** (optional) | `pib/_engine/ui/settings/<name>_settings.py` | A `QWidget` shown when the user clicks the module's tab in the taskbar. |

The dispatcher in `pib/_engine/app.py:Dispatcher` is the only thing that knows
about all modules — it routes `("eyes", "look_left", [], {})` to
`backends["eyes"].dispatch("look_left", [], {})`. Adding a new module means
adding three files and one entry in the dispatcher dict.

See [`extending.md`](extending.md) for a worked example.
