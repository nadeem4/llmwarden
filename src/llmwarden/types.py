"""The core types every other module speaks. Standard library only.

Frozen dataclasses:

- ``Message(role, content)`` with ``role`` in ``system``, ``user``, ``assistant``.
- ``ChatRequest(model_id, messages, params, schema)``. ``params`` is a read-only
  mapping handed to the backend after llmwarden removes the keys it owns
  (``schema``, ``tools``). ``schema`` is the caller's Pydantic class or ``None``.
- ``Usage(input_tokens, output_tokens, source)``; a count the provider did not
  send is ``None``, never ``0``. ``source`` is ``reported`` or ``estimated``.
- ``Price(input_per_million, output_per_million)`` in US dollars.
- ``Cost(usd, source)`` with ``source`` in ``model``, ``backend``, ``llmwarden``.
- ``ChatReply(text, usage, model, provider, stop_reason, call_id, attempts, raw,
  parsed, cost)``. A backend returns it with ``parsed=None`` and ``cost=None``;
  ``model.py`` fills both. ``raw`` is the backend's response object and is
  never recorded.

``ErrorKind`` enum: ``auth``, ``permission``, ``not_found``, ``rate_limit``,
``timeout``, ``connection``, ``server``, ``bad_request``, ``invalid_output``,
``cancelled``, ``unknown``. Retries and records read only this.

Exceptions:

- ``ProviderError(message, *, kind, provider, status)``: the scrubbed error
  raised to the caller after retries run out. ``message`` never contains a key.
- ``InvalidOutput(ProviderError)``: ``kind`` is ``invalid_output``; ``text``
  holds the last raw reply.
- ``NotSupported``, ``ProviderUnavailable``, ``EndpointRefused``,
  ``SecretNotFound(store, name)``: plain exceptions, each raised at model
  creation or call time as the architecture describes.

Depends on: nothing in the package.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]
UsageSource = Literal["reported", "estimated"]
CostSource = Literal["model", "backend", "llmwarden"]


class ErrorKind(StrEnum):
    auth = "auth"
    permission = "permission"
    not_found = "not_found"
    rate_limit = "rate_limit"
    timeout = "timeout"
    connection = "connection"
    server = "server"
    bad_request = "bad_request"
    invalid_output = "invalid_output"
    cancelled = "cancelled"
    unknown = "unknown"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


def _frozen(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(mapping or {}))


@dataclass(frozen=True)
class ChatRequest:
    model_id: str
    messages: Sequence[Message]
    params: Mapping[str, Any] = field(default_factory=lambda: _frozen(None))
    schema: type[Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", tuple(self.messages))
        object.__setattr__(self, "params", _frozen(self.params))


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    source: UsageSource = "reported"


@dataclass(frozen=True)
class Price:
    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class Cost:
    usd: float
    source: CostSource


@dataclass(frozen=True)
class ChatReply:
    text: str
    usage: Usage
    model: str
    provider: str
    stop_reason: str
    call_id: str
    attempts: int
    raw: Any
    parsed: Any | None = None
    cost: Cost | None = None


class ProviderError(Exception):
    def __init__(
        self, message: str, *, kind: ErrorKind, provider: str, status: int | None = None
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.provider = provider
        self.status = status


class InvalidOutput(ProviderError):
    def __init__(self, message: str, *, text: str, provider: str) -> None:
        super().__init__(message, kind=ErrorKind.invalid_output, provider=provider)
        self.text = text


class NotSupported(Exception):
    """A feature the architecture reserves but this version does not implement."""


class ProviderUnavailable(Exception):
    """No backend reaches this provider, or its extra is not installed."""


class EndpointRefused(Exception):
    """The endpoint guard refused a custom base URL."""


class SecretNotFound(Exception):
    def __init__(self, store: str, name: str) -> None:
        super().__init__(f"secret {name!r} not found in store {store!r}")
        self.store = store
        self.name = name
