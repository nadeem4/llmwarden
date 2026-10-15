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
