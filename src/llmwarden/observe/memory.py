"""``MemorySink``: the last N records, for ``report``.

``MemorySink(limit=10_000)`` is a ring buffer (``collections.deque``) installed
by default at import of ``observe``. ``records(since=None)`` returns a list
snapshot. ``clear()`` empties it; tests call this between cases.

Depends on: observe.records.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

from llmwarden.observe.records import AttemptRecord


class MemorySink:
    def __init__(self, limit: int = 10_000) -> None:
        self._buf: deque[AttemptRecord] = deque(maxlen=limit)
        self._lock = threading.Lock()

    def __call__(self, record: AttemptRecord) -> None:
        with self._lock:
            self._buf.append(record)

    def records(self, since: datetime | None = None) -> list[AttemptRecord]:
        with self._lock:
            items = list(self._buf)
        return [r for r in items if since is None or r.started >= since]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


default_sink = MemorySink()
