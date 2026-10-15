"""``OtelSink``: one OpenTelemetry span per attempt.

``OtelSink(tracer=None)`` uses ``opentelemetry.trace.get_tracer("llmwarden")``
when none is given. Each record becomes a span started at ``record.started``
with duration ``record.seconds``, status error on a failed outcome, and these
attributes: ``gen_ai.system`` (provider), ``gen_ai.request.model``,
``gen_ai.usage.input_tokens``, ``gen_ai.usage.output_tokens``, plus
``llmwarden.call_id``, ``llmwarden.attempt``, ``llmwarden.outcome``,
``llmwarden.error_kind``, ``llmwarden.cost_usd``, ``llmwarden.price_source``,
``llmwarden.usage_source``, and every tag as ``llmwarden.tag.<name>``. The
GenAI attribute names are pinned to semantic conventions 1.36.0
(``SEMCONV_VERSION``). A token attribute is omitted when the count is ``None``.

Install: ``llmwarden[otel]``.

Depends on: observe.records, opentelemetry-api.
"""

from __future__ import annotations

from typing import Any

from llmwarden.observe.records import AttemptRecord

SEMCONV_VERSION = "1.36.0"


class OtelSink:
    def __init__(self, tracer: Any | None = None) -> None:
        if tracer is None:
            from opentelemetry import trace  # extra: otel

            tracer = trace.get_tracer("llmwarden")
        self._tracer = tracer

    def __call__(self, record: AttemptRecord) -> None:
        from opentelemetry.trace import Status, StatusCode

        start_ns = int(record.started.timestamp() * 1e9)
        end_ns = start_ns + int(record.seconds * 1e9)
        attrs: dict[str, Any] = {
            "gen_ai.system": record.provider,
            "gen_ai.request.model": record.model,
            "llmwarden.call_id": record.call_id,
            "llmwarden.attempt": record.attempt,
            "llmwarden.outcome": record.outcome,
        }
        if record.input_tokens is not None:
            attrs["gen_ai.usage.input_tokens"] = record.input_tokens
        if record.output_tokens is not None:
            attrs["gen_ai.usage.output_tokens"] = record.output_tokens
        if record.error_kind is not None:
            attrs["llmwarden.error_kind"] = record.error_kind.value
        if record.cost_usd is not None:
            attrs["llmwarden.cost_usd"] = record.cost_usd
        if record.price_source is not None:
            attrs["llmwarden.price_source"] = record.price_source
        if record.usage_source is not None:
            attrs["llmwarden.usage_source"] = record.usage_source
        for key, value in record.tags.items():
            attrs[f"llmwarden.tag.{key}"] = value
        span = self._tracer.start_span(
            f"llm {record.provider} {record.model}", start_time=start_ns, attributes=attrs
        )
        if record.outcome != "ok":
            reason = record.error_kind.value if record.error_kind else record.outcome
            span.set_status(Status(StatusCode.ERROR, reason))
        span.end(end_time=end_ns)
