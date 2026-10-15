"""``FakeBackend``: scripted replies for tests, ours and applications'.

``FakeBackend(replies: list[ChatReply | BaseException], *, capabilities=None)``
returns or raises the next item on each ``complete`` and appends every
``ChatRequest`` to ``.requests``. ``error_kind`` maps a small set of fake
exception classes (``FakeAuthError``, ``FakeRateLimit``, ``FakeServerError``,
``FakeTimeout``) to their kinds. ``client`` returns a token object and records
the key it was given in ``.keys_seen`` so a test can assert the key reached the
backend and nothing else; the test must never print that list on failure.

Default capabilities: ``providers=frozenset({"fake"})`` plus any passed,
``schema=True``, ``prices=False``, ``http_client=True``. Tests flip flags to
exercise the fill-in paths.

Public: applications import ``llmwarden.backends.FakeBackend`` to test their
own code without a network.

Depends on: types, backends.base.
"""
