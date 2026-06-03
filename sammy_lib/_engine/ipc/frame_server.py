"""Placeholder for a future shared-memory frame publisher.

For v1, frames stay inside the engine process (consumed by the camera preview
and by the vision backend in-process). When `robot.eyes.see()` is wired up,
this module will publish frames via `multiprocessing.shared_memory` so the
client can read them without going through JSON.
"""

from __future__ import annotations


class FrameServer:
    def __init__(self):
        pass

    def publish(self, rgb):
        # No-op for v1.
        return

    def shutdown(self):
        return
