"""``AnthropicBackend``: the official anthropic SDK.

Providers: ``anthropic``. Capabilities: ``schema=True`` (a single forced tool
whose input schema is the caller's schema; the tool input is returned as
``text`` serialized to JSON), ``prices=False``, ``http_client=True``.

- ``client``: ``anthropic.Anthropic(api_key=..., base_url=..., max_retries=0,
  http_client=http)``.
- ``complete``: ``client.messages.create``. The system messages are joined into
  the ``system`` argument; user and assistant messages map one to one.
  ``max_tokens`` defaults to 1024 when ``request.params`` has none, since the
  API requires it. Everything else in ``request.params`` (``thinking``,
  ``betas``, ``fallbacks`` and any future beta field) passes through untouched;
  when ``betas`` is present the call goes through ``client.beta.messages``.
  Usage from ``usage.input_tokens`` and ``usage.output_tokens``.
- ``error_kind``: the SDK's exception classes mapped as in the OpenAI adapter.

Tests mock HTTP with respx. Install: ``llmwarden[anthropic]``.

Depends on: types, backends.base, anthropic.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from llmwarden.backends.base import Capabilities
from llmwarden.types import ChatReply, ChatRequest, Cost, ErrorKind, Usage

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_MAX_TOKENS = 1024
SCHEMA_TOOL = "respond"


class AnthropicBackend:
    capabilities = Capabilities(
        providers=frozenset({"anthropic"}),
        schema=True,
        prices=False,
        http_client=True,
        http_lib="httpx2",
    )

    def client(self, *, api_key: str, base_url: str | None, http: httpx.Client | None) -> Any:
        import anthropic

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url or ANTHROPIC_BASE_URL,
            "max_retries": 0,
        }
        if http is not None:
            kwargs["http_client"] = http
        return anthropic.Anthropic(**kwargs)

    def complete(self, client: Any, request: ChatRequest) -> ChatReply:
        params: dict[str, Any] = dict(request.params)
        params.setdefault("max_tokens", DEFAULT_MAX_TOKENS)
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        messages = [
            {"role": m.role, "content": m.content} for m in request.messages if m.role != "system"
        ]
        if system:
            params["system"] = system
        if request.schema is not None:
            params["tools"] = [
                {
                    "name": SCHEMA_TOOL,
                    "description": "Return the answer in the required shape.",
                    "input_schema": request.schema.model_json_schema(),
                }
            ]
            params["tool_choice"] = {"type": "tool", "name": SCHEMA_TOOL}
        api = client.beta.messages if "betas" in params else client.messages
        response = api.create(model=request.model_id, messages=messages, **params)

        text = ""
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == SCHEMA_TOOL:
                text = json.dumps(block.input)
                break
            if getattr(block, "type", None) == "text":
                text += block.text
        usage = getattr(response, "usage", None)
        return ChatReply(
            text=text,
            usage=Usage(
                input_tokens=getattr(usage, "input_tokens", None) if usage else None,
                output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            ),
            model=getattr(response, "model", None) or request.model_id,
            provider="anthropic",
            stop_reason=getattr(response, "stop_reason", None) or "end_turn",
            call_id="",
            attempts=0,
            raw=response,
        )

    def error_kind(self, error: BaseException) -> ErrorKind:
        import anthropic

        table: list[tuple[type[BaseException], ErrorKind]] = [
            (anthropic.AuthenticationError, ErrorKind.auth),
            (anthropic.PermissionDeniedError, ErrorKind.permission),
            (anthropic.NotFoundError, ErrorKind.not_found),
            (anthropic.RateLimitError, ErrorKind.rate_limit),
            (anthropic.APITimeoutError, ErrorKind.timeout),
            (anthropic.APIConnectionError, ErrorKind.connection),
            (anthropic.InternalServerError, ErrorKind.server),
            (anthropic.BadRequestError, ErrorKind.bad_request),
        ]
        for cls, kind in table:
            if isinstance(error, cls):
                return kind
        if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
            return ErrorKind.server
        return ErrorKind.unknown

    def price(self, reply: ChatReply) -> Cost | None:
        return None
