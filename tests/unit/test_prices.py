from llmwarden.prices import AS_OF, PRICES, cost, price_for
from llmwarden.types import Cost, Price, Usage


def test_table_is_dated_and_has_known_models():
    assert AS_OF.count("-") == 2
    assert price_for("openai", "gpt-5.4") is not None
    assert price_for("anthropic", "claude-sonnet-5") is not None
    assert price_for("openai", "unknown-model") is None
    assert all(isinstance(p, Price) for p in PRICES.values())


def test_cost_math():
    c = cost(Usage(1_000_000, 500_000), Price(2.0, 10.0), "llmwarden")
    assert c == Cost(usd=7.0, source="llmwarden")


def test_cost_is_none_when_either_count_missing():
    assert cost(Usage(None, 5), Price(1, 1), "model") is None
    assert cost(Usage(5, None), Price(1, 1), "model") is None
