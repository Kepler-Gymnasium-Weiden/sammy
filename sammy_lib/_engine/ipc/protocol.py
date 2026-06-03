"""JSON message schema shared between client (sammy_lib/api) and engine (sammy_lib/_engine).

Each message is a single line of UTF-8 JSON terminated by a newline. Three
message types travel over the socket:

    call      client → engine    invoke a method on a module
    reply     engine → client    result or error for a previous call
    event     engine → client    asynchronous notification (e.g. button click)

Frames from the camera are *not* part of this protocol — they go through
shared memory (see _frames.py / frame_server.py). Image payloads returned
from `eyes.see()` etc. are base64-encoded inside the regular reply.
"""

from __future__ import annotations

import json
from typing import Any


MSG_CALL = "call"
MSG_REPLY = "reply"
MSG_EVENT = "event"


def make_call(call_id: str, module: str, method: str,
              args: list | None = None, kwargs: dict | None = None) -> dict:
    return {
        "type": MSG_CALL,
        "id": call_id,
        "module": module,
        "method": method,
        "args": args or [],
        "kwargs": kwargs or {},
    }


def make_reply(call_id: str, ok: bool, result: Any = None,
               error: dict | None = None) -> dict:
    msg: dict = {"type": MSG_REPLY, "id": call_id, "ok": ok}
    if ok:
        msg["result"] = result
    else:
        msg["error"] = error or {"type": "Error", "message": ""}
    return msg


def make_event(name: str, payload: dict | None = None) -> dict:
    """Generic engine→client event. `name` namespaces it (e.g. 'ui.click')."""
    return {"type": MSG_EVENT, "name": name, "payload": payload or {}}


def encode(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line: bytes) -> dict:
    return json.loads(line.decode("utf-8"))
