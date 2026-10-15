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

from __future__ import annotations

from llmwarden.types import Cost, CostSource, Price, Usage

AS_OF = "2026-10-15"

# Standard tier, short context, US dollars per million tokens, read from the
# providers' public pricing pages on AS_OF. OpenAI prices are the <272K context
# rate; Anthropic prices are the base input and output rate.
PRICES: dict[tuple[str, str], Price] = {
    ("openai", "gpt-5.4"): Price(2.5, 15.0),
    ("openai", "gpt-5.4-mini"): Price(0.75, 4.5),
    ("anthropic", "claude-opus-5"): Price(5.0, 25.0),
    ("anthropic", "claude-sonnet-5"): Price(2.0, 10.0),
    ("anthropic", "claude-haiku-4-5"): Price(1.0, 5.0),
}


def price_for(provider: str, model_id: str) -> Price | None:
    return PRICES.get((provider, model_id))


def cost(usage: Usage, price: Price, source: CostSource) -> Cost | None:
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    usd = (
        usage.input_tokens * price.input_per_million
        + usage.output_tokens * price.output_per_million
    ) / 1_000_000
    return Cost(usd=usd, source=source)
