"""``report``: add up the memory sink by tag.

``report(group_by: list[str], since: datetime | None = None) -> list[Row]``.
``Row`` (frozen): the group's tag values, ``calls`` (distinct ``call_id``),
``attempts``, ``failures: dict[ErrorKind, int]``, ``input_tokens``,
``output_tokens``, ``cost_usd``, ``wasted_usd`` (cost of failed attempts that
used tokens), ``unknown_cost_attempts``, ``seconds``. A record missing a
group-by tag falls into a group with that value ``None``.

Depends on: observe.memory, types.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from llmwarden.observe.memory import MemorySink, default_sink
from llmwarden.observe.records import AttemptRecord
from llmwarden.types import ErrorKind


@dataclass(frozen=True)
class Row:
    group: Mapping[str, str | None]
    calls: int
    attempts: int
    failures: Mapping[ErrorKind, int]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    wasted_usd: float
    unknown_cost_attempts: int
    seconds: float


def report(
    group_by: list[str], since: datetime | None = None, *, sink: MemorySink | None = None
) -> list[Row]:
    records = (sink or default_sink).records(since)
    groups: dict[tuple[tuple[str, str | None], ...], list[AttemptRecord]] = defaultdict(list)
    for r in records:
        key = tuple((g, r.tags.get(g)) for g in group_by)
        groups[key].append(r)
    rows: list[Row] = []
    for key, items in groups.items():
        failures: dict[ErrorKind, int] = defaultdict(int)
        for r in items:
            if r.error_kind is not None:
                failures[r.error_kind] += 1
        rows.append(
            Row(
                group=dict(key),
                calls=len({r.call_id for r in items}),
                attempts=len(items),
                failures=dict(failures),
                input_tokens=sum(r.input_tokens or 0 for r in items),
                output_tokens=sum(r.output_tokens or 0 for r in items),
                cost_usd=sum(r.cost_usd or 0.0 for r in items),
                wasted_usd=sum(r.cost_usd or 0.0 for r in items if r.outcome != "ok"),
                unknown_cost_attempts=sum(1 for r in items if r.cost_usd is None),
                seconds=sum(r.seconds for r in items),
            )
        )
    return rows
