"""The contract every adapter implements. Small on purpose.

``Capabilities`` (frozen dataclass): ``providers: frozenset[str]``,
``schema: bool`` (can send a JSON schema natively), ``prices: bool`` (can price
a reply), ``http_client: bool`` (accepts an injected ``httpx.Client``, required
for the guard).

``Backend`` (Protocol):

- ``capabilities: Capabilities``
- ``client(*, api_key, base_url, http) -> Any``: build the library client with
  its own retries turned off. The key goes here and nowhere else.
- ``complete(client, request: ChatRequest) -> ChatReply``: one HTTP attempt.
  Return ``parsed=None`` and ``cost=None``. Raise the library's exception
  unchanged. Pass ``request.params`` through untouched. Missing usage is
  ``None``.
- ``error_kind(error) -> ErrorKind``: map the library's exception class to an
  ``ErrorKind``; ``unknown`` for anything unrecognised.
- ``price(reply) -> Cost | None``: only called when ``capabilities.prices``.

An adapter never retries, records, scrubs, validates a schema, logs, registers
library callbacks or reads environment variables.

Depends on: types, httpx (type only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from llmwarden.types import ChatReply, ChatRequest, Cost, ErrorKind


@dataclass(frozen=True)
class Capabilities:
    providers: frozenset[str]
    schema: bool
    prices: bool
    http_client: bool


@runtime_checkable
class Backend(Protocol):
    capabilities: Capabilities

    def client(self, *, api_key: str, base_url: str | None, http: httpx.Client | None) -> Any: ...

    def complete(self, client: Any, request: ChatRequest) -> ChatReply: ...

    def error_kind(self, error: BaseException) -> ErrorKind: ...

    def price(self, reply: ChatReply) -> Cost | None: ...
