# Transport

## Wire format

A loopback TCP socket carries newline-delimited JSON. Three message types
travel in both directions; schemas are defined in
`pib/_engine/ipc/protocol.py`.

### Client → engine

```json
{
  "type": "call",
  "id":   "<uuid hex>",
  "module": "eyes",
  "method": "look_left",
  "args":   [],
  "kwargs": {}
}
```

### Engine → client (one of)

```json
{ "type": "reply", "id": "<uuid hex>", "ok": true,  "result": null }
{ "type": "reply", "id": "<uuid hex>", "ok": false,
  "error": { "type": "AttributeError", "message": "...", "trace": "..." } }
{ "type": "event", "name": "ui.event",
  "payload": { "element_id": "button_3", "event": "click", "value": null } }
{ "type": "event", "name": "script.stop", "payload": {} }
```

Every reply matches a call by `id`. Events are unsolicited and carry no `id`.

The protocol is intentionally tiny — adding a new message type is a half-hour
job. There is no version negotiation; client and engine ship together so they
always agree on the schema.

## Threading — client side (`pib/api/_transport.py`)

```
       student's main thread
              │
              ├── robot.eyes.look_left()
              ▼
        Transport.call()
              │  put pending[id] event, write JSON
              │  block on event.wait()
              │
   ┌──────────┴────────────────────────────────────────┐
   │                                                   │
 reader thread (daemon)                          worker pool (ThreadPoolExecutor)
   │                                                   │
   │  for line in socket:                              │  for each UI event:
   │      msg = json.loads(line)                       │      handler(value)
   │      if reply → results[id] = msg; ev.set()       │      (errors are caught)
   │      if event → submit task to worker pool        │
   ▼                                                   ▼
```

Replies and events arrive on the same socket. The reader thread classifies
them and routes:

- **Replies** are stored in `_results[id]` and the corresponding
  `threading.Event` is set, which wakes the call-site.
- **Events** (UI clicks, slider changes, Stop) are pushed into a small
  `ThreadPoolExecutor`. A slow UI handler can therefore never delay reply
  delivery, and multiple handlers can run concurrently.

Writes are protected by `_write_lock` because the worker-pool threads might
make API calls during a handler. Only one writer at a time touches the socket.

## Threading — engine side (`pib/_engine/ipc/server.py`)

```
   client → socket
                │
                ▼
       _ReaderThread (QThread)
                │  for line in socket:
                │      emit request_received(msg)   ← QueuedConnection
                ▼
       IPCServer._on_request   (Qt main thread)
                │
                ▼
       dispatcher(module, method, args, kwargs)
                │
                ▼
       module backend method
                │  may run nested QEventLoop for animation timing
                ▼
       socket.sendall(reply)                       (still Qt main thread)
```

The reader is a `QThread` that just reads and re-emits. The actual call
runs on the Qt main thread because backends touch Qt widgets directly. The
nested `QEventLoop` inside `EyesBackend._wait_ms` is a standard Qt pattern —
the loop keeps processing GUI events (so animations keep updating) while the
caller waits for a known duration.

Reply writes happen on the Qt main thread; no write-lock is needed because
events sent back to the client (button clicks etc.) also originate on the Qt
main thread. Single-writer-by-construction.

## Cancellation (Stop button)

When the user presses **Stop** in the taskbar, the engine sends
`{"type":"event","name":"script.stop"}`. The client's reader thread sets
`_stop_flag` and wakes every pending caller. Each waiting `call()` then
notices `_stop_flag` is set and raises `ScriptStopped`.

Cancellation is **cooperative**: a student loop that doesn't call any
`robot.*` method will not be interrupted. The first API call after Stop will
raise `ScriptStopped`, which unwinds back through the student's code. For
classroom safety we considered injecting an exception into the main thread
via `ctypes.pythonapi.PyThreadState_SetAsyncExc`, but that is officially
unsupported and breaks too many invariants — cooperative cancellation is
simpler and sufficient.

## Engine startup handshake

`pib/api/_runtime.py:Runtime._read_port()` performs a single-step handshake:

1. The runtime spawns the engine with `--port 0` (let the OS pick a port).
2. The engine binds, gets its actual port, and prints `PORT=<n>\n` to stdout
   *before* calling `app.exec()`.
3. The runtime reads stdout line by line. The first `PORT=` line is parsed;
   everything else is forwarded to the runtime's stderr for debugging.
4. The runtime opens a TCP connection to that port and the system is live.

If the engine dies during startup (e.g. PyQt6 not installed), the runtime
raises `EngineUnavailable` immediately rather than blocking forever.
