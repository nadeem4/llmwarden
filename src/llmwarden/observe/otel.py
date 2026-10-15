"""``OtelSink``: one OpenTelemetry span per attempt.

``OtelSink(tracer=None)`` uses ``opentelemetry.trace.get_tracer("llmwarden")``
when none is given. Each record becomes a span started at ``record.started``
with duration ``record.seconds``, status error on a failed outcome, and these
attributes: ``gen_ai.system`` (provider), ``gen_ai.request.model``,
``gen_ai.usage.input_tokens``, ``gen_ai.usage.output_tokens``, plus
``llmwarden.call_id``, ``llmwarden.attempt``, ``llmwarden.outcome``,
``llmwarden.error_kind``, ``llmwarden.cost_usd``, ``llmwarden.price_source``,
``llmwarden.usage_source``, and every tag as ``llmwarden.tag.<name>``. The
GenAI attribute names are pinned to one semantic-conventions version, named in
this docstring once chosen.

Install: ``llmwarden[otel]``.

Depends on: observe.records, opentelemetry-api.
"""
