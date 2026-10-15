"""The attempt loop. llmwarden retries; every backend's own retries are off.

- ``Retry(attempts=3, on=frozenset({rate_limit, timeout, connection, server,
  invalid_output}), base=0.5, cap=8.0)``: a frozen dataclass.
- ``wait(policy, attempt) -> float``: exponential backoff with full jitter,
  ``random.uniform(0, min(cap, base * 2 ** (attempt - 1)))``.
- ``run(attempt_fn, policy, sleep=time.sleep) -> ChatReply``: call
  ``attempt_fn(attempt_number)`` until it returns, re-raising a
  ``ProviderError`` whose ``kind`` is not in ``policy.on`` at once and the last
  error when attempts run out. ``attempt_fn`` emits its own record; ``run``
  only sequences and waits. ``sleep`` is injectable so tests use a fake clock.

The auth re-fetch is not here. ``model.py`` wraps ``attempt_fn`` so that one
``auth`` error triggers a key re-fetch and one extra attempt outside the count.

Depends on: types.
"""
