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

    # 1. Bind the listening socket BEFORE Qt starts, so we can announce the
    #    port to the spawning runtime and block until a client connects.
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind(("127.0.0.1", args.port))
    listen.listen(1)
    port = listen.getsockname()[1]
    print(f"PORT={port}", flush=True)

    # 2. Qt setup.
    app = QApplication(sys.argv)

    # 3. Module backends.
    camera = CameraBackend()
    vision = VisionBackend(camera) if camera.is_available() else VisionBackend(camera)
    mouth = MouthBackend()
    ears = EarsBackend()
    body = BodyBackend(host=args.robot_host, port=args.robot_port)

    window = MainWindow(
        camera=camera, vision=vision, mouth=mouth, ears=ears, body=body,
        fullscreen=args.fullscreen,
    )

    eyes = EyesBackend(window.eye_widget, camera=camera, vision=vision)

    # 4. IPC server (dispatcher routes module.method calls; events go back via the same server).
    server = IPCServer(listen)
    ui = UiBackend(window.taskbar, send_event=server.send_event)
    dispatcher = Dispatcher({
        "eyes": eyes,
        "mouth": mouth,
        "ears": ears,
        "body": body,
        "ui": ui,
    })
    server.set_dispatcher(dispatcher)

    # 5. Stop button in the taskbar → tell client to abort the running script.
    window.stop_requested.connect(lambda: server.send_event("script.stop", {}))

    # 6. When the GUI closes, drop the client cleanly.
    app.aboutToQuit.connect(server.shutdown)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
