"""``OpenAIBackend``: the official openai SDK, one adapter for every
OpenAI-compatible server.

Providers: ``openai``, ``openai_compatible``, ``openrouter``. Capabilities:
``schema=True`` (``response_format`` with ``json_schema``, strict),
``prices=False``, ``http_client=True``.

- ``client``: ``openai.OpenAI(api_key=..., base_url=..., max_retries=0,
  http_client=http)``. For any base URL other than OpenAI's, send
  ``default_headers`` that omit ``OpenAI-Organization`` and ``OpenAI-Project``
  so the SDK does not fill them from the environment. OpenRouter gets its fixed
  base URL.
- ``complete``: ``client.chat.completions.create`` with ``messages`` mapped one
  to one, ``model=request.model_id``, and ``request.params`` spread in. Read
  ``usage.prompt_tokens`` and ``usage.completion_tokens`` as ``None`` when
  absent. A ``refusal`` becomes ``text`` with ``stop_reason="refusal"``.
- ``error_kind``: ``AuthenticationError -> auth``, ``PermissionDeniedError ->
  permission``, ``NotFoundError -> not_found``, ``RateLimitError ->
  rate_limit``, ``APITimeoutError -> timeout``, ``APIConnectionError ->
  connection``, ``InternalServerError -> server``, ``BadRequestError ->
  bad_request``, else ``unknown``.

Tests mock HTTP with respx. Install: ``llmwarden[openai]``.

Depends on: types, backends.base, openai.
"""

from __future__ import annotations

from typing import Any

import httpx

from llmwarden.backends.base import Capabilities
from llmwarden.types import ChatReply, ChatRequest, Cost, ErrorKind, Usage

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenAIBackend:
    capabilities = Capabilities(
        providers=frozenset({"openai", "openai_compatible", "openrouter"}),
        schema=True,
        prices=False,
        http_client=True,
        http_lib="httpx2",
    )

    def client(self, *, api_key: str, base_url: str | None, http: httpx.Client | None) -> Any:
        import openai

        kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0}
        if base_url and base_url.rstrip("/") != OPENAI_BASE_URL:
            kwargs["base_url"] = base_url
            kwargs["default_headers"] = {
                "OpenAI-Organization": openai.Omit(),
                "OpenAI-Project": openai.Omit(),
            }
        if http is not None:
            kwargs["http_client"] = http
        return openai.OpenAI(**kwargs)

    def complete(self, client: Any, request: ChatRequest) -> ChatReply:
        params: dict[str, Any] = dict(request.params)
        if request.schema is not None:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema.__name__,
                    "schema": request.schema.model_json_schema(),
                    "strict": True,
                },
            }
        response = client.chat.completions.create(
            model=request.model_id,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            **params,
        )
        choice = response.choices[0]
        message = choice.message
        refusal = getattr(message, "refusal", None)
        usage = response.usage
        return ChatReply(
            text=refusal if refusal else (message.content or ""),
            usage=Usage(
                input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            ),
            model=getattr(response, "model", None) or request.model_id,
            provider="openai",
            stop_reason="refusal" if refusal else (choice.finish_reason or "stop"),
            call_id="",
            attempts=0,
            raw=response,
        )

    def error_kind(self, error: BaseException) -> ErrorKind:
        import openai

        # APITimeoutError subclasses APIConnectionError, so the timeout row comes first.
        table: list[tuple[type[BaseException], ErrorKind]] = [
            (openai.AuthenticationError, ErrorKind.auth),
            (openai.PermissionDeniedError, ErrorKind.permission),
            (openai.NotFoundError, ErrorKind.not_found),
            (openai.RateLimitError, ErrorKind.rate_limit),
            (openai.APITimeoutError, ErrorKind.timeout),
            (openai.APIConnectionError, ErrorKind.connection),
            (openai.InternalServerError, ErrorKind.server),
            (openai.BadRequestError, ErrorKind.bad_request),
        ]
        for cls, kind in table:
            if isinstance(error, cls):
                return kind
        return ErrorKind.unknown

    def price(self, reply: ChatReply) -> Cost | None:
        return None
