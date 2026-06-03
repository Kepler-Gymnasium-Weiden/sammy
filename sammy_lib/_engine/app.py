"""Engine bootstrap.

Run either as a subprocess of the student program (the normal case — launched
by `sammy_lib/api/_runtime.py`) or standalone for development:

    python -m sammy_lib._engine                    # windowed dev mode, port 7311
    python -m sammy_lib._engine --fullscreen       # fullscreen
    python -m sammy_lib._engine --port 0           # pick a free port, print PORT=<n>

On startup the engine binds a TCP listening socket on 127.0.0.1, prints
`PORT=<n>\\n` to stdout (so the spawning runtime can connect), then enters the
Qt event loop. Exactly one client connects at a time.
"""

from __future__ import annotations

import argparse
import socket
import sys
import traceback

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QApplication

from .ipc.server import IPCServer
from .modules.camera_backend import CameraBackend
from .modules.vision_backend import VisionBackend
from .modules.eyes_backend import EyesBackend
from .modules.mouth_backend import MouthBackend
from .modules.ears_backend import EarsBackend
from .modules.body_backend import BodyBackend
from .modules.ui_backend import UiBackend
from .ui.main_window import MainWindow


class Dispatcher(QObject):
    """Routes incoming IPC calls to the right module backend, on the GUI thread."""

    def __init__(self, backends: dict, parent=None):
        super().__init__(parent)
        self._backends = backends

    def __call__(self, module: str, method: str, args: list, kwargs: dict):
        backend = self._backends.get(module)
        if backend is None:
            raise AttributeError(f"unknown module '{module}'")
        return backend.dispatch(method, args, kwargs)


def _safe_backend(label: str, factory):
    """Construct an optional backend, disabling just it if construction fails.

    The face (eyes) is the core of the robot; a flaky optional subsystem —
    speech, hearing, the ROS body link — must never take the whole engine down
    with it. On failure we log the traceback and return ``None``; the window and
    dispatcher already treat a missing backend as "feature unavailable".
    """
    try:
        return factory()
    except Exception:
        traceback.print_exc()
        print(f"[engine] '{label}' backend disabled (init failed); "
              f"the rest of the robot will still run", flush=True)
        return None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sammy_lib._engine")
    parser.add_argument("--port", type=int, default=0,
                        help="TCP port to listen on; 0 = pick any free port")
    parser.add_argument("--fullscreen", action="store_true",
                        help="Start in fullscreen mode")
    parser.add_argument("--robot-host", type=str, default="localhost",
                        help="rosbridge host for the body module (robot.body.*)")
    parser.add_argument("--robot-port", type=int, default=9090,
                        help="rosbridge port for the body module")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    # 0. A diagnostic print must never be able to kill the engine. On a non-UTF-8
    #    locale (e.g. ISO-8859-15), printing a character like "…" raises
    #    UnicodeEncodeError, which would otherwise abort startup. Force UTF-8 on
    #    our stdio and never raise on an un-encodable character.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    # 1. Bind the listening socket up front so we know the port number, but do
    #    NOT announce it yet. The OS accepts a client's connection into the
    #    listen backlog the moment we listen(), so if we printed PORT= here and
    #    then crashed during GUI setup, the client would connect successfully and
    #    only discover the failure as a dropped call. Announcing PORT= only after
    #    startup fully succeeds (step 7) makes startup failures fail fast and
    #    clearly, at connect time.
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listen.bind(("127.0.0.1", args.port))
        listen.listen(1)
    except OSError as exc:
        print(f"ENGINE_START_ERROR: could not bind 127.0.0.1:{args.port}: {exc}",
              flush=True)
        return 1
    port = listen.getsockname()[1]

    try:
        # 2. Qt setup.
        app = QApplication(sys.argv)

        # 3. Module backends. The eyes/face are core; the rest are optional and
        #    fail soft (a disabled subsystem must not brick the whole engine).
        camera = CameraBackend()
        vision = VisionBackend(camera)
        mouth = _safe_backend("mouth", MouthBackend)
        ears = _safe_backend("ears", EarsBackend)
        body = _safe_backend(
            "body", lambda: BodyBackend(host=args.robot_host, port=args.robot_port))

        window = MainWindow(
            camera=camera, vision=vision, mouth=mouth, ears=ears, body=body,
            fullscreen=args.fullscreen,
        )

        eyes = EyesBackend(window.eye_widget, camera=camera, vision=vision)

        # 4. IPC server (dispatcher routes module.method calls; events go back via the same server).
        server = IPCServer(listen)
        ui = UiBackend(window.taskbar, send_event=server.send_event)

        # 5. Register only the backends that actually came up. A call to a
        #    disabled module then returns a clean "unknown module" error to the
        #    student instead of crashing anything.
        backends = {"eyes": eyes, "ui": ui}
        for name, backend in (("mouth", mouth), ("ears", ears), ("body", body)):
            if backend is not None:
                backends[name] = backend
        server.set_dispatcher(Dispatcher(backends))

        # 6. Wiring: Stop button aborts the script; closing the GUI drops the client.
        window.stop_requested.connect(lambda: server.send_event("script.stop", {}))
        app.aboutToQuit.connect(server.shutdown)
    except Exception as exc:
        # Startup failed before we ever announced the port — report it clearly
        # (the runtime turns ENGINE_START_ERROR into a readable EngineUnavailable)
        # and exit non-zero rather than leaving a half-built engine running.
        traceback.print_exc()
        print(f"ENGINE_START_ERROR: {type(exc).__name__}: {exc}", flush=True)
        try:
            listen.close()
        except OSError:
            pass
        return 1

    # 7. Startup fully succeeded — only now is it safe for the client to connect.
    print(f"PORT={port}", flush=True)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
