"""Observability: tags, attempt records, sinks and the report.

Re-exports ``add``, ``remove``, ``emit`` and ``AttemptRecord`` from
``observe.records``, ``tags`` and ``current`` from ``observe.tags``,
``MemorySink`` from ``observe.memory`` and ``report`` from ``observe.report``.
``OtelSink`` is imported from ``observe.otel`` by the application, since it
needs the ``otel`` extra.

Depends on: observe.records, observe.tags, observe.memory, observe.report.
"""

from llmwarden.observe.memory import MemorySink, default_sink
from llmwarden.observe.records import AttemptRecord, add, emit, remove
from llmwarden.observe.report import report
from llmwarden.observe.tags import current, tags

__all__ = [
    "AttemptRecord",
    "MemorySink",
    "add",
    "current",
    "default_sink",
    "emit",
    "remove",
    "report",
    "tags",
]

# The memory sink that ``report`` reads is installed once, at import.
add(default_sink)
