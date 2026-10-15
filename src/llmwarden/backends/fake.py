"""``FakeBackend``: scripted replies for tests, ours and applications'.

``FakeBackend(replies: list[ChatReply | BaseException], *, capabilities=None)``
returns or raises the next item on each ``complete`` and appends every
``ChatRequest`` to ``.requests``. ``error_kind`` maps a small set of fake
exception classes (``FakeAuthError``, ``FakeRateLimit``, ``FakeServerError``,
``FakeTimeout``, ``FakeConnectionError``, ``FakeBadRequest``) to their kinds.
``client`` returns a token object and records the key it was given in
``.keys_seen`` so a test can assert the key reached the backend and nothing
else; ``keys_seen`` is excluded from ``repr`` so a failing test never prints it.

Default capabilities: ``providers=frozenset({"fake"})``, ``schema=True``,
``prices=False``, ``http_client=True``. Tests pass other capabilities to
exercise the fill-in paths.

Public: applications import ``llmwarden.backends.FakeBackend`` to test their
own code without a network.

Depends on: types, backends.base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from llmwarden.backends.base import Capabilities
from llmwarden.types import ChatReply, ChatRequest, Cost, ErrorKind, Usage


class FakeAuthError(Exception): ...


class FakeRateLimit(Exception): ...


class FakeServerError(Exception): ...


class FakeTimeout(Exception): ...


class FakeConnectionError(Exception): ...


class FakeBadRequest(Exception): ...


_KINDS: dict[type[BaseException], ErrorKind] = {
    FakeAuthError: ErrorKind.auth,
    FakeRateLimit: ErrorKind.rate_limit,
    FakeServerError: ErrorKind.server,
    FakeTimeout: ErrorKind.timeout,
    FakeConnectionError: ErrorKind.connection,
    FakeBadRequest: ErrorKind.bad_request,
}

DEFAULT_CAPABILITIES = Capabilities(
    providers=frozenset({"fake"}), schema=True, prices=False, http_client=True
)


def reply(text: str, *, usage: Usage | None = None, model: str = "fake-model") -> ChatReply:
    """A ``ChatReply`` as a backend would return it: no ``parsed``, no ``cost``."""
    return ChatReply(
        text=text,
        usage=usage or Usage(None, None),
        model=model,
        provider="fake",
        stop_reason="stop",
        call_id="",
        attempts=0,
        raw=None,
    )


@dataclass
class _FakeClient:
    http: httpx.Client | None


@dataclass
class FakeBackend:
    replies: list[ChatReply | BaseException] = field(default_factory=list)
    capabilities: Capabilities = DEFAULT_CAPABILITIES
    requests: list[ChatRequest] = field(default_factory=list, init=False)
    keys_seen: list[str] = field(default_factory=list, init=False, repr=False)

    def client(self, *, api_key: str, base_url: str | None, http: httpx.Client | None) -> Any:
        self.keys_seen.append(api_key)
        return _FakeClient(http=http)

    def complete(self, client: Any, request: ChatRequest) -> ChatReply:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("FakeBackend ran out of scripted replies")
        item = self.replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def error_kind(self, error: BaseException) -> ErrorKind:
        return _KINDS.get(type(error), ErrorKind.unknown)

    def price(self, reply: ChatReply) -> Cost | None:
        return None
