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
