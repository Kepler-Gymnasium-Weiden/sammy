"""Client-side IPC: a JSON-over-TCP transport with synchronous calls.

Threading model
---------------

The student's program runs on its main Python thread. Each `call()` writes a
message and blocks on a `threading.Event` until the matching reply arrives —
so from the student's perspective `robot.eyes.blink()` looks fully synchronous
even though the work happens in the engine subprocess.

A daemon **reader thread** owns the socket: it reads newline-delimited JSON,
fans replies to their waiting callers and dispatches events (UI clicks, slider
changes, Stop button) into a small **ThreadPoolExecutor** so a slow callback
can't stall reply delivery.

Cancellation
------------

When the engine sends `script.stop` (Stop button), `_stop_flag` is set. Every
subsequent `call()` and every event-handler invocation checks this flag at its
boundary and raises `ScriptStopped`. We use cooperative cancellation rather
than `_async_raise` because injecting exceptions into running threads is
fragile and unsupported.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from .exceptions import EngineCallError, EngineUnavailable, ScriptStopped


_TYPE_REPLY = "reply"
_TYPE_EVENT = "event"


class Transport:
    def __init__(self, host: str, port: int):
        try:
            self._sock = socket.create_connection((host, port), timeout=5.0)
        except OSError as exc:
            raise EngineUnavailable(f"could not connect to engine: {exc}") from exc
        self._sock.settimeout(None)
        self._file = self._sock.makefile("rb")

        self._pending: dict[str, threading.Event] = {}
        self._results: dict[str, dict] = {}
        self._event_handlers: dict[str, Callable] = {}
        self._stop_flag = threading.Event()
        self._closed = threading.Event()

        self._write_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4,
                                            thread_name_prefix="pib-ui-cb")
        self._reader = threading.Thread(target=self._read_loop,
                                        name="pib-reader", daemon=True)
        self._reader.start()

    # ---- public API ---------------------------------------------------

    def call(self, module: str, method: str,
             args: list | None = None, kwargs: dict | None = None) -> Any:
        """Send a call message and block until the reply arrives."""
        if self._stop_flag.is_set():
            raise ScriptStopped()
        if self._closed.is_set():
            raise EngineUnavailable("engine has disconnected")

        call_id = uuid.uuid4().hex
        msg = {
            "type": "call",
            "id": call_id,
            "module": module,
            "method": method,
            "args": list(args or []),
            "kwargs": dict(kwargs or {}),
        }
        event = threading.Event()
        self._pending[call_id] = event
        try:
            self._send(msg)
            event.wait()
        finally:
            self._pending.pop(call_id, None)

        if self._stop_flag.is_set() and call_id not in self._results:
            raise ScriptStopped()
        reply = self._results.pop(call_id, None)
        if reply is None:
            raise EngineUnavailable("engine closed before reply arrived")
        if not reply.get("ok", False):
            err = reply.get("error") or {}
            raise EngineCallError(
                err.get("message", "engine error"),
                remote_type=err.get("type", "Error"),
                trace=err.get("trace", ""),
            )
        return reply.get("result")

    def register_event_handler(self, element_id: str, callback: Callable):
        self._event_handlers[element_id] = callback

    def unregister_event_handler(self, element_id: str):
        self._event_handlers.pop(element_id, None)

    def wait_until_closed(self):
        """Block until the engine disconnects or stop is signalled."""
        while not self._closed.is_set() and not self._stop_flag.is_set():
            # Wake periodically so KeyboardInterrupt can break out.
            self._closed.wait(0.25)

    def is_stopped(self) -> bool:
        return self._stop_flag.is_set()

    def close(self):
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        self._closed.set()
        # Wake any waiting callers so they don't hang forever.
        for ev in list(self._pending.values()):
            ev.set()

    # ---- read loop ----------------------------------------------------

    def _read_loop(self):
        try:
            for line in self._file:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                self._handle(msg)
        except OSError:
            pass
        finally:
            self._closed.set()
            for ev in list(self._pending.values()):
                ev.set()

    def _handle(self, msg: dict):
        t = msg.get("type")
        if t == _TYPE_REPLY:
            rid = msg.get("id", "")
            self._results[rid] = msg
            ev = self._pending.get(rid)
            if ev is not None:
                ev.set()
        elif t == _TYPE_EVENT:
            self._handle_event(msg)

    def _handle_event(self, msg: dict):
        name = msg.get("name", "")
        payload = msg.get("payload") or {}
        if name == "script.stop":
            self._stop_flag.set()
            # Wake every blocked caller so they can raise ScriptStopped.
            for ev in list(self._pending.values()):
                ev.set()
            return
        if name == "ui.event":
            eid = payload.get("element_id")
            cb = self._event_handlers.get(eid)
            if cb is None:
                return
            self._executor.submit(self._safe_invoke, cb, payload)

    def _safe_invoke(self, cb: Callable, payload: dict):
        if self._stop_flag.is_set():
            return
        try:
            event_kind = payload.get("event")
            value = payload.get("value")
            if event_kind == "click":
                cb()
            elif event_kind in ("change", "submit"):
                cb(value)
        except ScriptStopped:
            pass
        except Exception as exc:  # don't let a buggy handler kill the executor
            print(f"[pib] error in UI handler: {exc!r}", file=sys.stderr)

    # ---- low-level send ----------------------------------------------

    def _send(self, msg: dict):
        data = (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")
        with self._write_lock:
            try:
                self._sock.sendall(data)
            except OSError as exc:
                self._closed.set()
                raise EngineUnavailable(f"send failed: {exc}") from exc
