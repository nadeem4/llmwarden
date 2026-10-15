"""Prices and the order they apply in.

- ``PRICES: dict[tuple[str, str], Price]`` keyed by ``(provider, model_id)``,
  list prices in US dollars per million input and output tokens at the standard
  tier, for current OpenAI and Anthropic models only. ``AS_OF`` is the date the
  providers' pricing pages were read. Keep this table small; LiteLLM users get
  LiteLLM's prices through the backend.
- ``price_for(provider, model_id) -> Price | None``.
- ``cost(usage, price, source) -> Cost | None``: ``None`` when either token
  count is ``None``.

``model.py`` applies the order: the model's own ``price`` (source ``model``),
the backend's ``price()`` when ``capabilities.prices`` (source ``backend``),
this table (source ``llmwarden``), else ``None``.

Depends on: types.
"""
