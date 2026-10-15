from datetime import UTC, datetime

import pytest

from llmwarden.observe.records import AttemptRecord
from llmwarden.types import ErrorKind

pytest.importorskip("opentelemetry.sdk")
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from llmwarden.observe.otel import OtelSink  # noqa: E402


def test_span_per_record_with_genai_attributes_and_error_status():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    sink = OtelSink(provider.get_tracer("t"))
    now = datetime.now(UTC)
    sink(
        AttemptRecord(
            id="1",
            call_id="c",
            model="gpt",
            provider="openai",
            attempt=1,
            outcome="ok",
            error_kind=None,
            input_tokens=3,
            output_tokens=4,
            usage_source="reported",
            cost_usd=0.01,
            price_source="llmwarden",
            started=now,
            seconds=0.5,
            tags={"customer": "acme"},
        )
    )
    sink(
        AttemptRecord(
            id="2",
            call_id="c",
            model="gpt",
            provider="openai",
            attempt=2,
            outcome="provider_error",
            error_kind=ErrorKind.rate_limit,
            input_tokens=None,
            output_tokens=None,
            usage_source=None,
            cost_usd=None,
            price_source=None,
            started=now,
            seconds=0.1,
            tags={},
        )
    )
    ok, bad = exporter.get_finished_spans()
    a = ok.attributes
    assert a["gen_ai.system"] == "openai" and a["gen_ai.request.model"] == "gpt"
    assert a["gen_ai.usage.input_tokens"] == 3 and a["gen_ai.usage.output_tokens"] == 4
    assert a["llmwarden.cost_usd"] == 0.01 and a["llmwarden.tag.customer"] == "acme"
    assert "gen_ai.usage.input_tokens" not in bad.attributes
    assert bad.attributes["llmwarden.error_kind"] == "rate_limit"
    assert bad.status.status_code.name == "ERROR" and ok.status.status_code.name != "ERROR"
    assert ok.end_time - ok.start_time == pytest.approx(0.5e9, rel=0.01)
