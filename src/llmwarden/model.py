"""``model()`` and ``Model``: one call orchestrated in a fixed order.

``model(name, *, api_key=None, base_url=None, public_only=False, params=None,
price=None, retry=None, fallback=None, backend=None) -> Model``:

1. Split ``name`` into ``provider`` and ``model_id``. Pick the backend from the
   provider table (``openai``, ``openai_compatible``, ``openrouter`` ->
   ``OpenAIBackend``; ``anthropic`` -> ``AnthropicBackend``; anything else ->
   ``LiteLLMBackend`` when installed, else raise ``ProviderUnavailable`` naming
   the extra). ``backend=`` overrides. ``backends.use(provider, backend)``
   edits the table for the process.
2. Resolve the key: a string as is; a callable by calling it; a ``SecretRef``
   through ``secrets.resolve``; ``None`` through ``env`` with the provider's
   standard variable. ``openai_compatible`` with no key gets a placeholder so
   the SDK never reads an environment key.
3. When ``base_url`` is set and ``public_only`` is true, run ``guard.check_url``
   and build the guarded client. Raise ``EndpointRefused`` if the backend's
   ``capabilities.http_client`` is false.
4. Build the adapter client. Models are not cached; the HTTP client is shared
   per backend and guard setting, so this is cheap.

``Model.complete(*, messages=None, system=None, user=None, schema=None,
params=None, tags=None) -> ChatReply``:

- ``system`` and ``user`` build a two-message list; giving both forms raises
  ``ValueError``. ``tools`` in ``params`` raises ``NotSupported``.
- When the backend lacks ``capabilities.schema`` and ``schema`` is set, append
  ``schema.prompt_for(schema)`` to the last system message.
- Run ``retry.run`` with one attempt function that calls the backend, maps and
  scrubs any exception through ``hygiene.reraise``, parses with
  ``schema.parse``, prices with ``prices.cost`` in the order model price,
  backend price, llmwarden table, and emits one ``AttemptRecord`` per attempt
  with ``observe.tags.current()`` merged under the per-call tags.
- On an ``auth`` error with a key from a store or callable, resolve the key
  again, rebuild the client and make one extra attempt, once per call, not
  counted against ``Retry.attempts``.
- When attempts run out and ``fallback`` is set, call ``fallback.complete``
  with the same arguments and the same ``call_id``.

``Model.refresh()`` resolves the key again and rebuilds the client.
``repr(Model)`` masks a string key and shows a ``SecretRef`` as store and name.

Depends on: types, backends.base, secrets.base, guard, hygiene, retry, schema,
prices, observe.records, observe.tags.
"""

from __future__ import annotations

import importlib
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from llmwarden import backends as backend_table
from llmwarden import guard, hygiene
from llmwarden import prices as price_table
from llmwarden import schema as schema_mod
from llmwarden.backends.base import Backend
from llmwarden.observe.records import AttemptRecord, Outcome, emit
from llmwarden.observe.tags import current as current_tags
from llmwarden.retry import Retry, run
from llmwarden.secrets.base import SecretRef, invalidate, resolve
from llmwarden.types import (
    ChatReply,
    ChatRequest,
    Cost,
    EndpointRefused,
    ErrorKind,
    InvalidOutput,
    Message,
    NotSupported,
    Price,
    ProviderError,
)

PLACEHOLDER_KEY = "not-needed"
DEFAULT_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
type KeySource = str | Callable[[], str] | SecretRef | None

_shared_http: dict[str, Any] = {}


def _shared_client(backend: Backend) -> Any:
    """One plain client per backend class, built from the HTTP library its SDK accepts.

    ``capabilities.http_lib`` names that library: ``httpx``, or ``httpx2`` for the
    openai and anthropic SDKs. A backend that takes no client gets ``None``.
    """
    if not backend.capabilities.http_client:
        return None
    key = type(backend).__qualname__
    if key not in _shared_http:
        module = importlib.import_module(backend.capabilities.http_lib)
        _shared_http[key] = module.Client(follow_redirects=False)
    return _shared_http[key]


def _resolve_key(source: KeySource, provider: str) -> str:
    if isinstance(source, str):
        return source
    if isinstance(source, SecretRef):
        return resolve(source)
    if callable(source):
        return str(source())
    if provider == "openai_compatible":
        return PLACEHOLDER_KEY
    var = DEFAULT_ENV_VARS.get(provider, f"{provider.upper()}_API_KEY")
    return resolve(SecretRef("env", var))


def _refetchable(source: KeySource) -> bool:
    """A key from a store or a callable can be fetched again; a string or env cannot."""
    return isinstance(source, SecretRef) or (source is not None and callable(source))


@dataclass
class Model:
    name: str
    provider: str
    model_id: str
    backend: Backend
    key_source: KeySource = field(repr=False)
    base_url: str | None = None
    public_only: bool = False
    params: Mapping[str, Any] = field(default_factory=dict)
    price: Price | None = None
    retry: Retry = field(default_factory=Retry)
    fallback: Model | None = None
    _key: str = field(default="", repr=False)
    _client: Any = field(default=None, repr=False)
    _http: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._build()

    def refresh(self) -> None:
        """Fetch the key again and rebuild the client."""
        if isinstance(self.key_source, SecretRef):
            invalidate(self.key_source)
        self._build()

    def _build(self) -> None:
        self._key = _resolve_key(self.key_source, self.provider)
        self._http = self._http_client()
        self._client = self.backend.client(
            api_key=self._key, base_url=self.base_url, http=self._http
        )

    def _http_client(self) -> Any:
        if self.base_url and self.public_only:
            if not self.backend.capabilities.http_client:
                raise EndpointRefused(
                    f"backend {type(self.backend).__name__} cannot pin a custom endpoint; "
                    "public_only requires a backend that accepts an http client"
                )
            ips = guard.check_url(self.base_url, resolver=guard.resolve_host)
            return guard.guarded_client(self.base_url, ips, lib=self.backend.capabilities.http_lib)
        return _shared_client(self.backend)

    def __repr__(self) -> str:
        if isinstance(self.key_source, SecretRef):
            key = repr(self.key_source)
        elif isinstance(self.key_source, str):
            key = hygiene.mask(self.key_source)
        elif self.key_source is None:
            key = "env"
        else:
            key = "<callable>"
        return f"Model({self.name!r}, api_key={key})"

    def complete(
        self,
        *,
        messages: list[Message] | None = None,
        system: str | None = None,
        user: str | None = None,
        schema: type[Any] | None = None,
        params: Mapping[str, Any] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> ChatReply:
        if messages is not None and (system is not None or user is not None):
            raise ValueError("pass either messages or system/user, not both")
        if messages is None:
            messages = []
            if system is not None:
                messages.append(Message("system", system))
            if user is not None:
                messages.append(Message("user", user))
        merged: dict[str, Any] = {**self.params, **(params or {})}
        if "tools" in merged:
            raise NotSupported("tool calling is not supported in this version")
        merged.pop("schema", None)
        call_id = uuid.uuid4().hex
        all_tags = {**current_tags(), **{k: str(v) for k, v in (tags or {}).items()}}
        return self._run(list(messages), schema, merged, call_id, all_tags, attempts_before=0)

    def _request(
        self, messages: list[Message], schema: type[Any] | None, params: Mapping[str, Any]
    ) -> ChatRequest:
        if schema is not None and not self.backend.capabilities.schema:
            hint = schema_mod.prompt_for(schema)
            for i, m in enumerate(messages):
                if m.role == "system":
                    messages[i] = Message("system", f"{m.content}\n\n{hint}")
                    break
            else:
                messages.insert(0, Message("system", hint))
            request_schema = None
        else:
            request_schema = schema
        return ChatRequest(
            model_id=self.model_id, messages=tuple(messages), params=params, schema=request_schema
        )

    def _run(
        self,
        messages: list[Message],
        schema: type[Any] | None,
        params: Mapping[str, Any],
        call_id: str,
        tags: Mapping[str, str],
        attempts_before: int,
    ) -> ChatReply:
        request = self._request(list(messages), schema, params)
        refetched = False
        count = attempts_before

        def attempt(n: int) -> ChatReply:
            nonlocal refetched, count
            count += 1
            started = datetime.now(UTC)
            t0 = time.perf_counter()
            try:
                reply = self.backend.complete(self._client, request)
                reply = self._finish(reply, schema, call_id, count)
            except ProviderError as e:
                self._record(call_id, count, e, None, started, t0, tags)
                raise
            except BaseException as e:
                kind = self.backend.error_kind(e)
                status = getattr(e, "status_code", None)
                if kind is ErrorKind.auth and not refetched and _refetchable(self.key_source):
                    refetched = True
                    self._record_error(call_id, count, "provider_error", kind, started, t0, tags)
                    self.refresh()
                    return attempt(n)
                try:
                    hygiene.reraise(
                        e,
                        kind=kind,
                        secrets=[self._key],
                        provider=self.provider,
                        status=status if isinstance(status, int) else None,
                    )
                except ProviderError as pe:
                    self._record(call_id, count, pe, None, started, t0, tags)
                    raise
            self._record(call_id, count, None, reply, started, t0, tags)
            return reply

        try:
            return run(attempt, self.retry)
        except ProviderError:
            if self.fallback is None:
                raise
            return self.fallback._run(messages, schema, params, call_id, tags, count)

    def _finish(
        self, reply: ChatReply, schema: type[Any] | None, call_id: str, n: int
    ) -> ChatReply:
        parsed = None
        if schema is not None:
            parsed = schema_mod.parse(reply.text, schema, provider=self.provider)
        return ChatReply(
            text=reply.text,
            usage=reply.usage,
            model=reply.model,
            provider=self.provider,
            stop_reason=reply.stop_reason,
            call_id=call_id,
            attempts=n,
            raw=reply.raw,
            parsed=parsed,
            cost=self._cost(reply),
        )

    def _cost(self, reply: ChatReply) -> Cost | None:
        if self.price is not None:
            return price_table.cost(reply.usage, self.price, "model")
        if self.backend.capabilities.prices:
            c = self.backend.price(reply)
            if c is not None:
                return c
        table = price_table.price_for(self.provider, self.model_id)
        if table is not None:
            return price_table.cost(reply.usage, table, "llmwarden")
        return None

    def _record_error(
        self,
        call_id: str,
        n: int,
        outcome: Outcome,
        kind: ErrorKind,
        started: datetime,
        t0: float,
        tags: Mapping[str, str],
    ) -> None:
        emit(
            AttemptRecord(
                id=uuid.uuid4().hex,
                call_id=call_id,
                model=self.model_id,
                provider=self.provider,
                attempt=n,
                outcome=outcome,
                error_kind=kind,
                input_tokens=None,
                output_tokens=None,
                usage_source=None,
                cost_usd=None,
                price_source=None,
                started=started,
                seconds=time.perf_counter() - t0,
                tags=dict(tags),
            )
        )

    def _record(
        self,
        call_id: str,
        n: int,
        error: ProviderError | None,
        reply: ChatReply | None,
        started: datetime,
        t0: float,
        tags: Mapping[str, str],
    ) -> None:
        if error is not None:
            outcome: Outcome = (
                "invalid_output" if isinstance(error, InvalidOutput) else "provider_error"
            )
            self._record_error(call_id, n, outcome, error.kind, started, t0, tags)
            return
        if reply is None:
            raise TypeError("_record needs a reply when there is no error")
        emit(
            AttemptRecord(
                id=uuid.uuid4().hex,
                call_id=call_id,
                model=reply.model,
                provider=self.provider,
                attempt=n,
                outcome="ok",
                error_kind=None,
                input_tokens=reply.usage.input_tokens,
                output_tokens=reply.usage.output_tokens,
                usage_source=reply.usage.source,
                cost_usd=reply.cost.usd if reply.cost else None,
                price_source=reply.cost.source if reply.cost else None,
                started=started,
                seconds=time.perf_counter() - t0,
                tags=dict(tags),
            )
        )


def model(
    name: str,
    *,
    api_key: KeySource = None,
    base_url: str | None = None,
    public_only: bool = False,
    params: Mapping[str, Any] | None = None,
    price: Price | None = None,
    retry: Retry | None = None,
    fallback: Model | None = None,
    backend: Backend | None = None,
) -> Model:
    if "/" not in name:
        raise ValueError("model name must be provider/model, for example openai/gpt-5.4")
    provider, model_id = name.split("/", 1)
    chosen = backend if backend is not None else backend_table.default_for(provider)
    if type(chosen).__name__ == "LiteLLMBackend":
        model_id = name  # LiteLLM routes on the provider prefix
    if backend is None and provider not in chosen.capabilities.providers:
        raise ValueError(f"backend {type(chosen).__name__} does not reach provider {provider!r}")
    return Model(
        name=name,
        provider=provider,
        model_id=model_id,
        backend=chosen,
        key_source=api_key,
        base_url=base_url,
        public_only=public_only,
        params=dict(params or {}),
        price=price,
        retry=retry if retry is not None else Retry(),
        fallback=fallback,
    )
