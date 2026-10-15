import json
import os
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel

from llmwarden.backends.base import Backend
from llmwarden.backends.litellm import LiteLLMBackend
from llmwarden.types import ChatRequest, ErrorKind, Message

pytest.importorskip("litellm")

KEY = "sk-test-ABCDEFGHIJKLMNOP1234"
URL = "https://api.openai.com/v1/chat/completions"


class Out(BaseModel):
    n: int


def ok_body(usage: bool = True) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"n": 2}'},
            }
        ],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
    return body


def req(schema: type[BaseModel] | None = None, **params: Any) -> ChatRequest:
    return ChatRequest(
        model_id="openai/gpt-4o-mini",
        messages=(Message("user", "u"),),
        params=params,
        schema=schema,
    )


def test_capabilities_and_local_cost_map_env():
    b = LiteLLMBackend()
    assert isinstance(b, Backend)
    assert "openai" in b.capabilities.providers and "anthropic" in b.capabilities.providers
    assert b.capabilities.prices and b.capabilities.schema and not b.capabilities.http_client
    assert os.environ.get("LITELLM_LOCAL_MODEL_COST_MAP") == "True"


@respx.mock
def test_complete_success_usage_and_price():
    respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body()))
    b = LiteLLMBackend()
    c = b.client(api_key=KEY, base_url=None, http=None)
    r = b.complete(c, req())
    assert r.text == '{"n": 2}' and r.usage.input_tokens == 5 and r.usage.output_tokens == 2
    assert r.provider == "openai" and r.model.endswith("gpt-4o-mini")
    assert r.parsed is None and r.cost is None
    cost = b.price(r)
    assert cost is not None and cost.source == "backend" and cost.usd > 0


@respx.mock
def test_no_retries_and_error_kinds():
    import litellm

    route = respx.post(URL).mock(
        return_value=httpx.Response(429, json={"error": {"message": "slow"}})
    )
    b = LiteLLMBackend()
    c = b.client(api_key=KEY, base_url=None, http=None)
    with pytest.raises(litellm.RateLimitError) as info:
        b.complete(c, req())
    assert route.call_count == 1
    assert b.error_kind(info.value) is ErrorKind.rate_limit
    auth = litellm.AuthenticationError("m", llm_provider="openai", model="x")
    assert b.error_kind(auth) is ErrorKind.auth
    assert b.error_kind(litellm.Timeout("m", llm_provider="openai", model="x")) is ErrorKind.timeout
    assert b.error_kind(ValueError()) is ErrorKind.unknown


@respx.mock
def test_schema_sent_as_response_format_and_key_used():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body()))
    b = LiteLLMBackend()
    c = b.client(api_key=KEY, base_url=None, http=None)
    b.complete(c, req(schema=Out))
    sent = json.loads(route.calls[0].request.content)
    assert sent["response_format"]["type"] == "json_schema"
    assert route.calls[0].request.headers["authorization"] == f"Bearer {KEY}"


@respx.mock
def test_missing_usage_is_none_not_zero():
    respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body(usage=False)))
    b = LiteLLMBackend()
    c = b.client(api_key=KEY, base_url=None, http=None)
    r = b.complete(c, req())
    assert r.usage.input_tokens is None and r.usage.output_tokens is None
    assert b.price(r) is None


def test_price_is_none_without_hidden_cost():
    from llmwarden.backends.fake import reply

    assert LiteLLMBackend().price(reply("x")) is None
