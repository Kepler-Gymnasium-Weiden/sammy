"""Engine-side IPC server.

Architecture:

    [client socket]
          │
          ▼ (one Python thread, blocking reads)
    ReaderThread.run() ─── emits  request_received(dict) ───► dispatcher slot
                                                              (GUI thread)
                                                                    │
                                                                    ▼
                                                              module method
                                                                    │
                                                                    ▼
                                                              encode reply
                                                                    │
                                                                    ▼
                                                              socket.sendall()
                                                              (still GUI thread)

Replies and events are always written to the socket from the GUI thread, so
no write-side mutex is needed. The single client model means we don't deal
with multiplexing — exactly one student program connects at a time.
"""

from __future__ import annotations

import socket
import traceback
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from . import protocol


class _ReaderThread(QThread):
    """Reads newline-delimited JSON from the client; emits each as a dict."""

    request_received = pyqtSignal(dict)
    client_disconnected = pyqtSignal()

    def __init__(self, conn: socket.socket, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._file = conn.makefile("rb")
        self._running = True

    def run(self):
        try:
            for line in self._file:
                if not self._running:
                    break
                if not line.strip():
                    continue
                try:
                    msg = protocol.decode(line)
                except Exception:
                    # bad line — skip rather than die
                    continue
                self.request_received.emit(msg)
        finally:
            self.client_disconnected.emit()

    def stop(self):
        self._running = False
        try:
            self._conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class IPCServer(QObject):
    """Owns the listening socket and the dispatcher.

    `set_dispatcher(callable)` registers the function that turns a request
    dict into a result (or raises). The function runs on the GUI thread.
    """

    client_connected = pyqtSignal()
    client_disconnected = pyqtSignal()

    def __init__(self, listen_sock: socket.socket, parent=None):
        super().__init__(parent)
        self._listen_sock = listen_sock
        self._conn: Optional[socket.socket] = None
        self._reader: Optional[_ReaderThread] = None
        self._dispatcher: Optional[Callable[[str, str, list, dict], object]] = None
        self._accept_thread = QThread(self)
        self._accept_thread.run = self._accept_loop  # type: ignore[assignment]
        self._accept_thread.start()

    def set_dispatcher(self, fn: Callable[[str, str, list, dict], object]):
        """fn(module, method, args, kwargs) -> result (sync on GUI thread)."""
        self._dispatcher = fn

    # ---- accept ---------------------------------------------------------

    def _accept_loop(self):
        # Blocks until a client connects. Only one client at a time.
        try:
            self._conn, _ = self._listen_sock.accept()
        except OSError:
            return
        self._reader = _ReaderThread(self._conn)
        self._reader.request_received.connect(self._on_request)
        self._reader.client_disconnected.connect(self._on_disconnect)
        self._reader.start()
        self.client_connected.emit()

    # ---- request dispatch (runs on GUI thread via queued signal) -------

    @pyqtSlot(dict)
    def _on_request(self, msg: dict):
        if msg.get("type") != protocol.MSG_CALL:
            return
        call_id = msg.get("id", "")
        try:
            if self._dispatcher is None:
                raise RuntimeError("no dispatcher registered")
            result = self._dispatcher(
                msg.get("module", ""),
                msg.get("method", ""),
                msg.get("args", []) or [],
                msg.get("kwargs", {}) or {},
            )
            reply = protocol.make_reply(call_id, ok=True, result=result)
        except Exception as exc:
            reply = protocol.make_reply(call_id, ok=False, error={
                "type": type(exc).__name__,
                "message": str(exc),
                "trace": traceback.format_exc(limit=4),
            })
        self._send(reply)

    # ---- outbound -------------------------------------------------------

    def send_event(self, name: str, payload: dict | None = None):
        """Push an asynchronous event (e.g. UI click) to the client."""
        self._send(protocol.make_event(name, payload))

    def _send(self, msg: dict):
        if self._conn is None:
            return
        try:
            self._conn.sendall(protocol.encode(msg))
        except OSError:
            pass

    # ---- lifecycle ------------------------------------------------------

    def _on_disconnect(self):
        self.client_disconnected.emit()
        self._conn = None
        self._reader = None

    def shutdown(self):
        if self._reader:
            self._reader.stop()
        try:
            self._listen_sock.close()
        except OSError:
            pass
        if self._conn:
            try:
                self._conn.close()
            except OSError:
                pass
