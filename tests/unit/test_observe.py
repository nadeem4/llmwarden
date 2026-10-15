import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest

from llmwarden.observe.memory import MemorySink
from llmwarden.observe.records import AttemptRecord, add, emit, remove, sinks
from llmwarden.observe.report import report
from llmwarden.observe.tags import current, tags
from llmwarden.types import ErrorKind


def rec(**kw):
    base = dict(
        id="a1",
        call_id="c1",
        model="m",
        provider="p",
        attempt=1,
        outcome="ok",
        error_kind=None,
        input_tokens=10,
        output_tokens=5,
        usage_source="reported",
        cost_usd=0.01,
        price_source="llmwarden",
        started=datetime.now(UTC),
        seconds=0.1,
        tags={"customer": "acme", "step": "a"},
    )
    base.update(kw)
    return AttemptRecord(**base)


def test_tags_nest_and_inner_wins_and_values_are_strings():
    assert current() == {}
    with tags(request=1, customer="acme"):
        assert current() == {"request": "1", "customer": "acme"}
        with tags(customer="beta", step="x"):
            assert current() == {"request": "1", "customer": "beta", "step": "x"}
        assert current() == {"request": "1", "customer": "acme"}
    assert current() == {}


def test_tags_propagate_into_asyncio_tasks():
    async def inner():
        return dict(current())

    async def main():
        with tags(request="r"):
            return await asyncio.create_task(inner())

    assert asyncio.run(main()) == {"request": "r"}


def test_emit_calls_sinks_and_a_failing_sink_is_skipped_after_first_error(caplog):
    seen = []

    def good(r):
        seen.append(r)

    def bad(r):
        raise RuntimeError("sink broke")

    add(good)
    add(bad)
    try:
        with caplog.at_level(logging.ERROR, logger="llmwarden"):
            emit(rec())
            emit(rec(id="a2"))
        assert len(seen) == 2
        assert sum("sink broke" in m for m in caplog.messages) == 1
    finally:
        remove(good)
        remove(bad)
    assert good not in sinks() and bad not in sinks()


def test_memory_sink_ring_buffer_and_since():
    s = MemorySink(limit=2)
    t0 = datetime.now(UTC)
    s(rec(id="1", started=t0 - timedelta(seconds=10)))
    s(rec(id="2", started=t0 - timedelta(seconds=5)))
    s(rec(id="3", started=t0))
    assert [r.id for r in s.records()] == ["2", "3"]
    assert [r.id for r in s.records(since=t0 - timedelta(seconds=1))] == ["3"]
    s.clear()
    assert s.records() == []


def test_report_groups_and_sums():
    s = MemorySink()
    s(
        rec(
            id="1",
            call_id="c1",
            attempt=1,
            outcome="provider_error",
            error_kind=ErrorKind.rate_limit,
            input_tokens=10,
            output_tokens=0,
            cost_usd=0.001,
        )
    )
    s(
        rec(
            id="2",
            call_id="c1",
            attempt=2,
            outcome="ok",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.002,
        )
    )
    s(
        rec(
            id="3",
            call_id="c2",
            outcome="ok",
            tags={"customer": "beta", "step": "a"},
            input_tokens=None,
            output_tokens=None,
            usage_source=None,
            cost_usd=None,
            price_source=None,
        )
    )
    s(rec(id="4", call_id="c3", outcome="ok", tags={"step": "a"}, cost_usd=0.5))
    rows = {tuple(r.group.items()): r for r in report(["customer"], sink=s)}
    acme = rows[(("customer", "acme"),)]
    assert acme.calls == 1 and acme.attempts == 2 and acme.failures == {ErrorKind.rate_limit: 1}
    assert acme.input_tokens == 20 and acme.output_tokens == 5
    assert acme.cost_usd == pytest.approx(0.003) and acme.wasted_usd == pytest.approx(0.001)
    beta = rows[(("customer", "beta"),)]
    assert beta.unknown_cost_attempts == 1 and beta.cost_usd == 0.0
    assert rows[(("customer", None),)].cost_usd == 0.5
