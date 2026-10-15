"""``AttemptRecord`` and the sink registry.

``AttemptRecord`` (frozen): ``id``, ``call_id``, ``model``, ``provider``,
``attempt``, ``outcome`` (``ok``, ``provider_error``, ``invalid_output``),
``error_kind``, ``input_tokens``, ``output_tokens``, ``usage_source``,
``cost_usd``, ``price_source``, ``started``, ``seconds``, ``tags``. No prompt,
no reply, no key, ever.

- ``add(sink)`` and ``remove(sink)``: a sink is any callable taking one record.
- ``emit(record)``: call every sink. A sink that raises is logged once through
  the ``llmwarden`` logger and skipped afterwards, so one broken sink never
  breaks a call.

Depends on: types.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from llmwarden.types import CostSource, ErrorKind, UsageSource

Outcome = Literal["ok", "provider_error", "invalid_output"]
log = logging.getLogger("llmwarden")


@dataclass(frozen=True)
class AttemptRecord:
    id: str
    call_id: str
    model: str
    provider: str
    attempt: int
    outcome: Outcome
    error_kind: ErrorKind | None
    input_tokens: int | None
    output_tokens: int | None
    usage_source: UsageSource | None
    cost_usd: float | None
    price_source: CostSource | None
    started: datetime
    seconds: float
    tags: Mapping[str, str]


Sink = Callable[[AttemptRecord], None]
_sinks: list[Sink] = []
_broken: set[int] = set()
_lock = threading.Lock()


def add(sink: Sink) -> None:
    with _lock:
        if sink not in _sinks:
            _sinks.append(sink)


def remove(sink: Sink) -> None:
    with _lock:
        if sink in _sinks:
            _sinks.remove(sink)
        _broken.discard(id(sink))


def sinks() -> list[Sink]:
    with _lock:
        return list(_sinks)


def emit(record: AttemptRecord) -> None:
    for sink in sinks():
        if id(sink) in _broken:
            continue
        try:
            sink(record)
        except Exception as exc:
            _broken.add(id(sink))
            log.exception("llmwarden sink %r raised %s and is disabled", sink, exc)
