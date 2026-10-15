"""``MemorySink``: the last N records, for ``report``.

``MemorySink(limit=10_000)`` is a ring buffer (``collections.deque``) installed
by default at import of ``observe``. ``records(since=None)`` returns a list
snapshot. ``clear()`` empties it; tests call this between cases.

Depends on: observe.records.
"""
