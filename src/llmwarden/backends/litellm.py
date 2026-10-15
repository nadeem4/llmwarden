"""``LiteLLMBackend``: breadth through LiteLLM, with its hidden behaviour off.

Providers: every provider LiteLLM lists (``litellm.provider_list``).
Capabilities: ``schema=True`` (``response_format`` takes the class),
``prices=True`` (``response._hidden_params["response_cost"]``),
``http_client=False`` in version one, so ``public_only`` with a custom base
URL on this backend is refused at model creation.

- Set ``LITELLM_LOCAL_MODEL_COST_MAP=True`` in the environment before importing
  litellm, so it reads its price file from the package and downloads nothing.
- ``client`` returns a small holder with the key and base URL; LiteLLM takes
  them per call as ``api_key`` and ``api_base``.
- ``complete``: ``litellm.completion(model=f"{provider}/{model_id}", ...,
  num_retries=0, max_retries=0)``. Never set ``drop_params``. LiteLLM
  zero-fills usage the provider did not send; the adapter reports that as
  ``None``.
- ``error_kind``: LiteLLM's mapped exception classes (``AuthenticationError``,
  ``RateLimitError``, ``Timeout``, ``APIConnectionError``,
  ``InternalServerError``, ``BadRequestError``, ``NotFoundError``,
  ``PermissionDeniedError``) to their kinds.
- ``price``: the response cost when present and the usage is known, else
  ``None``. LiteLLM reports ``0.0`` for its zero-filled usage.
- Never register LiteLLM callbacks; they receive the raw key.

Tests mock HTTP with respx on the OpenAI and Anthropic paths. Install:
``llmwarden[litellm]``.

Depends on: types, backends.base, litellm.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from llmwarden.backends.base import Capabilities
from llmwarden.types import ChatReply, ChatRequest, Cost, ErrorKind, Usage

# Read the price file from the installed package; download nothing at import.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


@dataclass(frozen=True)
class _LiteLLMClient:
    api_key: str = field(repr=False)
    base_url: str | None = None


def _usage(reported: Any) -> Usage:
    """LiteLLM substitutes an all-zero ``Usage`` when the provider sent none.

    A reply to a non-empty prompt cannot have zero prompt tokens, so all-zero
    means unknown and both counts become ``None``.
    """
    if reported is None:
        return Usage(None, None)
    prompt = getattr(reported, "prompt_tokens", None)
    completion = getattr(reported, "completion_tokens", None)
    if not prompt and not completion:
        return Usage(None, None)
    return Usage(input_tokens=prompt, output_tokens=completion)


class LiteLLMBackend:
    def __init__(self) -> None:
        import litellm

        litellm.drop_params = False
        self.capabilities = Capabilities(
            providers=frozenset(getattr(p, "value", str(p)) for p in litellm.provider_list),
            schema=True,
            prices=True,
            http_client=False,
        )

    def client(self, *, api_key: str, base_url: str | None, http: httpx.Client | None) -> Any:
        return _LiteLLMClient(api_key=api_key, base_url=base_url)

    def complete(self, client: Any, request: ChatRequest) -> ChatReply:
        import litellm

        params: dict[str, Any] = dict(request.params)
        if request.schema is not None:
            params["response_format"] = request.schema
        response = litellm.completion(
            model=request.model_id,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            api_key=client.api_key,
            api_base=client.base_url,
            num_retries=0,
            max_retries=0,
            **params,
        )
        choice = response.choices[0]
        usage = _usage(getattr(response, "usage", None))
        provider = request.model_id.split("/", 1)[0] if "/" in request.model_id else "openai"
        return ChatReply(
            text=choice.message.content or "",
            usage=usage,
            model=getattr(response, "model", None) or request.model_id,
            provider=provider,
            stop_reason=choice.finish_reason or "stop",
            call_id="",
            attempts=0,
            raw=response,
        )

    def error_kind(self, error: BaseException) -> ErrorKind:
        from litellm import exceptions

        table: list[tuple[type[BaseException], ErrorKind]] = [
            (exceptions.AuthenticationError, ErrorKind.auth),
            (exceptions.PermissionDeniedError, ErrorKind.permission),
            (exceptions.NotFoundError, ErrorKind.not_found),
            (exceptions.RateLimitError, ErrorKind.rate_limit),
            (exceptions.Timeout, ErrorKind.timeout),
            (exceptions.APIConnectionError, ErrorKind.connection),
            (exceptions.InternalServerError, ErrorKind.server),
            (exceptions.ServiceUnavailableError, ErrorKind.server),
            (exceptions.BadRequestError, ErrorKind.bad_request),
        ]
        for cls, kind in table:
            if isinstance(error, cls):
                return kind
        return ErrorKind.unknown

    def price(self, reply: ChatReply) -> Cost | None:
        if reply.usage.input_tokens is None and reply.usage.output_tokens is None:
            return None
        hidden = getattr(reply.raw, "_hidden_params", None) or {}
        usd = hidden.get("response_cost")
        if usd is None:
            return None
        return Cost(usd=float(usd), source="backend")
