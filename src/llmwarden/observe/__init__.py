"""Observability: tags, attempt records, sinks and the report.

Re-exports ``add``, ``remove``, ``emit`` and ``AttemptRecord`` from
``observe.records``, ``tags`` and ``current`` from ``observe.tags``,
``MemorySink`` from ``observe.memory`` and ``report`` from ``observe.report``.
``OtelSink`` is imported from ``observe.otel`` by the application, since it
needs the ``otel`` extra.

Depends on: observe.records, observe.tags, observe.memory, observe.report.
"""
