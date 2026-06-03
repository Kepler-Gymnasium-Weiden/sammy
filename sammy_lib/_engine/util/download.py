"""Streamed HTTP download with a progress callback.

Used by the ears (Vosk models) and mouth (Piper voices) backends so the
settings UI can show a progress bar instead of a frozen window during a
multi-hundred-MB first-time fetch.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable, Optional

# (bytes_done, total_bytes). total is -1 when the server didn't send Content-Length.
ProgressCallback = Callable[[int, int], None]


def format_bytes(n: int) -> str:
    """Human-readable byte count. Uses GB once we're past 1024 MB."""
    if n < 0:
        return "?"
    mb = n / (1024 * 1024)
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"


def download_with_progress(
    url: str,
    dest: Path,
    on_progress: Optional[ProgressCallback] = None,
    chunk_size: int = 64 * 1024,
) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "pib-eyes/1.0"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length") or 0) or -1
        done = 0
        if on_progress:
            on_progress(0, total)
        with open(dest, "wb") as f:
            while True:
                buf = resp.read(chunk_size)
                if not buf:
                    break
                f.write(buf)
                done += len(buf)
                if on_progress:
                    on_progress(done, total)
