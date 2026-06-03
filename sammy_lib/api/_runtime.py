"""Engine lifecycle: spawn the GUI subprocess and connect to it.

The student program imports `sammy_lib` and accesses `sammy_lib.robot`. On the very first
API call, `Runtime.ensure_started()` is invoked, which:

  1. Spawns `python -m sammy_lib._engine --fullscreen` as a subprocess.
  2. Reads `PORT=<n>` from its stdout to learn which TCP port to dial.
  3. Opens a `Transport` to that port.

An `atexit` hook closes the transport cleanly when the student program exits,
which causes the engine to drop the client and close the window.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
import threading
from typing import Optional

from ._transport import Transport
from .exceptions import EngineUnavailable


class Runtime:
    """Owns the engine subprocess + the IPC transport. One per student program."""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._transport: Optional[Transport] = None
        self._lock = threading.Lock()
        self._fullscreen = True
        self._robot_host = "localhost"
        self._robot_port = 9090
        atexit.register(self._shutdown)

    # ---- configuration -------------------------------------------------

    def configure(self, *, fullscreen: bool = True,
                  robot_host: str = "localhost", robot_port: int = 9090):
        """Adjust startup options. Must be called before the first API call."""
        with self._lock:
            if self._transport is not None:
                return  # already running, ignore
            self._fullscreen = fullscreen
            self._robot_host = robot_host
            self._robot_port = robot_port

    # ---- startup -------------------------------------------------------

    def ensure_started(self) -> Transport:
        with self._lock:
            if self._transport is not None:
                return self._transport
            self._transport = self._start_engine()
            return self._transport

    def _start_engine(self) -> Transport:
        cmd = [sys.executable, "-m", "sammy_lib._engine", "--port", "0",
               "--robot-host", str(self._robot_host),
               "--robot-port", str(self._robot_port)]
        if self._fullscreen:
            cmd.append("--fullscreen")
        env = dict(os.environ)
        # Force unbuffered stdout in the child so `PORT=` arrives immediately.
        env.setdefault("PYTHONUNBUFFERED", "1")
        # Force the child's stdio to UTF-8 regardless of the system locale, so a
        # log line with a non-ASCII character can't raise UnicodeEncodeError and
        # crash the engine (a non-UTF-8 locale like ISO-8859-15 otherwise does).
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, text=True, bufsize=1,
                encoding="utf-8", errors="backslashreplace",
            )
        except OSError as exc:
            raise EngineUnavailable(f"could not launch engine: {exc}") from exc

        port = self._read_port()
        # Keep draining the child's stdout/stderr (merged) AFTER the port is
        # announced. Otherwise a crash during GUI startup — which happens after
        # `PORT=` is printed and the OS has already accepted our connection into
        # the listen backlog — is invisible, and the first call just fails with
        # the opaque "engine closed before reply arrived". Forwarding the output
        # lets the engine's real traceback reach the student's terminal.
        drain = threading.Thread(target=self._drain_output,
                                 name="pib-engine-log", daemon=True)
        drain.start()
        return Transport("127.0.0.1", port)

    def _drain_output(self):
        """Forward the engine's post-startup output to stderr for debugging."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line:
                    print(f"[engine] {line}", file=sys.stderr)
        except (OSError, ValueError):
            pass
        rc = proc.poll()
        if rc not in (0, None):
            print(f"[engine] subprocess exited with code {rc}", file=sys.stderr)

    def _read_port(self) -> int:
        """Block until the child writes `PORT=<n>` on its first line of stdout."""
        assert self._proc is not None and self._proc.stdout is not None
        for _ in range(200):  # ~20 s worst case at 0.1 s per line
            line = self._proc.stdout.readline()
            if not line:
                rc = self._proc.poll()
                raise EngineUnavailable(
                    f"engine exited before reporting a port (exit code {rc})"
                )
            line = line.strip()
            if line.startswith("PORT="):
                try:
                    return int(line.split("=", 1)[1])
                except ValueError:
                    pass
            elif line.startswith("ENGINE_START_ERROR:"):
                # The engine reports it failed to start (before announcing a
                # port). Any traceback it printed has already been forwarded
                # above; surface a clean message instead of a generic timeout.
                detail = line.split(":", 1)[1].strip()
                raise EngineUnavailable(f"engine failed to start: {detail}")
            # Anything else is engine log output; forward to stderr for debugging.
            print(f"[engine] {line}", file=sys.stderr)
        raise EngineUnavailable("engine never reported a port")

    # ---- shutdown ------------------------------------------------------

    def _shutdown(self):
        try:
            if self._transport is not None:
                self._transport.close()
        except Exception:
            pass
        try:
            if self._proc is not None and self._proc.poll() is None:
                # Give the engine a moment to close its window after EOF.
                try:
                    self._proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
        except Exception:
            pass

    # ---- convenience ---------------------------------------------------

    @property
    def transport(self) -> Optional[Transport]:
        return self._transport


# Module-level singleton — there is only ever one engine per student program.
_runtime = Runtime()


def transport() -> Transport:
    return _runtime.ensure_started()


def configure(*, fullscreen: bool = True,
              robot_host: str = "localhost", robot_port: int = 9090):
    _runtime.configure(fullscreen=fullscreen,
                       robot_host=robot_host, robot_port=robot_port)
