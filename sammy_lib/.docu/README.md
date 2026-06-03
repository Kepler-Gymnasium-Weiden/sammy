# pib — Technical Documentation

This directory holds the **internal** architecture notes for the whole `pib`
package — both the `api/` surface and the `_engine/` runtime. It documents
how things are wired up, not how to *use* them. For usage, see the top-level
`README.md` and the files in `examples/`.

The student-facing surface is intentionally tiny: students do

```python
from pib import robot
robot.eyes.look_left()
```

Everything below that line is described here.

## Index

1. [`concept.md`](concept.md) — design goals, package layout, two-process model.
2. [`transport.md`](transport.md) — IPC protocol, threading model, cancellation.
3. [`custom_tabs.md`](custom_tabs.md) — how `robot.ui.tab(...)` and UI elements work.
4. [`vision.md`](vision.md) — camera + object detection pipeline, privacy notes.
5. [`extending.md`](extending.md) — adding a new module (e.g. `robot.arm`).

## At a glance

```
┌─────────────────────────────┐   subprocess + TCP socket   ┌──────────────────────────────┐
│  student program            │  ◄────── JSON messages ─────►│  pib._engine (Qt GUI)        │
│  (their own .py file)       │                              │                              │
│                             │                              │  ┌────────────────────────┐  │
│  from pib import robot      │                              │  │ EyeWidget (fullscreen) │  │
│  robot.eyes.look_left()     │                              │  ├────────────────────────┤  │
│  robot.ui.tab(...).button() │                              │  │ Taskbar (tabs + Stop)  │  │
│  robot.run()                │                              │  └────────────────────────┘  │
└─────────────────────────────┘                              └──────────────────────────────┘
       pib/                                                          pib/_engine/
```

The student never imports anything from `pib._engine`; the leading underscore
marks it as private.
