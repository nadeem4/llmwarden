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
  num_retries=0, max_retries=0)``. Never set ``drop_params``. Usage source is
  ``estimated`` when LiteLLM filled it in.
- ``error_kind``: LiteLLM's mapped exception classes (``AuthenticationError``,
  ``RateLimitError``, ``Timeout``, ``APIConnectionError``,
  ``InternalServerError``, ``BadRequestError``, ``NotFoundError``,
  ``PermissionDeniedError``) to their kinds.
- ``price``: the response cost when present, else ``None``.
- Never register LiteLLM callbacks; they receive the raw key.

Tests mock HTTP with respx on the OpenAI and Anthropic paths. Install:
``llmwarden[litellm]``.

Depends on: types, backends.base, litellm.
"""
