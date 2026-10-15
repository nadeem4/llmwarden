import dataclasses

import pytest

from llmwarden.types import (
    ChatReply,
    ChatRequest,
    Cost,
    ErrorKind,
    InvalidOutput,
    Message,
    Price,
    ProviderError,
    Usage,
)


def test_message_is_frozen():
    m = Message(role="user", content="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.content = "x"  # type: ignore[misc]


def test_usage_defaults_to_reported_and_allows_none_counts():
    u = Usage(input_tokens=None, output_tokens=5)
    assert u.input_tokens is None and u.output_tokens == 5 and u.source == "reported"


def test_chat_request_params_is_read_only_mapping_and_messages_tuple():
    r = ChatRequest(model_id="m", messages=[Message("user", "hi")], params={"a": 1}, schema=None)
    with pytest.raises(TypeError):
        r.params["b"] = 2  # type: ignore[index]
    assert isinstance(r.messages, tuple)


def test_provider_error_carries_kind_and_status():
    e = ProviderError("boom", kind=ErrorKind.rate_limit, provider="openai", status=429)
    assert e.kind is ErrorKind.rate_limit and e.status == 429 and str(e) == "boom"


def test_invalid_output_is_a_provider_error_with_text():
    e = InvalidOutput("bad json", text="{oops", provider="fake")
    assert isinstance(e, ProviderError)
    assert e.kind is ErrorKind.invalid_output and e.text == "{oops"


def test_chat_reply_defaults():
    r = ChatReply(
        text="t",
        usage=Usage(1, 2),
        model="m",
        provider="p",
        stop_reason="stop",
        call_id="c",
        attempts=1,
        raw=None,
    )
    assert r.parsed is None and r.cost is None


def test_cost_and_price_are_frozen_floats():
    assert Price(1.0, 2.0).output_per_million == 2.0
    assert Cost(usd=0.5, source="model").source == "model"


def test_error_kind_values_are_their_names():
    assert all(k.value == k.name for k in ErrorKind)
