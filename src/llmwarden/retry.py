"""The attempt loop. llmwarden retries; every backend's own retries are off.

- ``Retry(attempts=3, on=frozenset({rate_limit, timeout, connection, server,
  invalid_output}), base=0.5, cap=8.0)``: a frozen dataclass. ``DEFAULT_RETRY_ON``
  is that default ``on`` set.
- ``wait(policy, attempt, rng=random.random) -> float``: exponential backoff
  with full jitter, ``min(cap, base * 2 ** (attempt - 1)) * rng()``. ``rng`` is
  injectable so tests pin the jitter.
- ``run(attempt_fn, policy, *, sleep=time.sleep) -> ChatReply``: call
  ``attempt_fn(attempt_number)`` with ``attempt_number`` counting from 1 until
  it returns. A ``ProviderError`` whose ``kind`` is not in ``policy.on`` is
  re-raised at once; a retryable one is re-raised when attempts run out.
  Between attempts ``run`` calls ``sleep(wait(policy, attempt_number))``. Any
  exception that is not a ``ProviderError`` passes through untouched.
  ``attempt_fn`` emits its own record; ``run`` only sequences and waits.
  ``sleep`` is injectable so tests use a fake clock.

The auth re-fetch is not here. ``model.py`` wraps ``attempt_fn`` so that one
``auth`` error triggers a key re-fetch and one extra attempt outside the count.

Depends on: types.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from llmwarden.types import ChatReply, ErrorKind, ProviderError

DEFAULT_RETRY_ON: frozenset[ErrorKind] = frozenset(
    {
        ErrorKind.rate_limit,
        ErrorKind.timeout,
        ErrorKind.connection,
        ErrorKind.server,
        ErrorKind.invalid_output,
    }
)


@dataclass(frozen=True)
class Retry:
    attempts: int = 3
    on: frozenset[ErrorKind] = DEFAULT_RETRY_ON
    base: float = 0.5
    cap: float = 8.0


def wait(policy: Retry, attempt: int, rng: Callable[[], float] = random.random) -> float:
    upper = min(policy.cap, policy.base * 2.0 ** (attempt - 1))
    return upper * rng()


def run(
    attempt_fn: Callable[[int], ChatReply],
    policy: Retry,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> ChatReply:
    attempt = 0
    while True:
        attempt += 1
        try:
            return attempt_fn(attempt)
        except ProviderError as e:
            if e.kind not in policy.on or attempt >= policy.attempts:
                raise
            sleep(wait(policy, attempt))
