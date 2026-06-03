"""Placeholder for a future shared-memory frame reader.

Pair with `pib/_engine/ipc/frame_server.py`. For v1 the client doesn't pull
raw frames; vision results come back as label lists over the regular IPC
channel.
"""

from __future__ import annotations


class FrameReader:
    def __init__(self):
        pass

    def latest(self):
        return None

    def close(self):
        return
