"""OpenAIBackend against a respx-mocked HTTP layer.

The installed openai SDK speaks through its own ``httpx2`` package, which respx
does not patch. Every test that makes a request therefore injects an
``httpx.Client`` through ``Backend.client(http=...)``, the same way the endpoint
guard does in production; that client is what respx intercepts. The
``http=None`` path is checked structurally and never sends anything.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel

from llmwarden.backends.base import Backend
from llmwarden.backends.openai import OPENAI_BASE_URL, OPENROUTER_BASE_URL, OpenAIBackend
from llmwarden.types import ChatRequest, ErrorKind, Message

KEY = "sk-test-ABCDEFGHIJKLMNOP1234"
URL = f"{OPENAI_BASE_URL}/chat/completions"


class Out(BaseModel):
    n: int


def ok_body(content: str | None = '{"n": 1}', usage: bool = True) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-5.4",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    return body


def req(schema: type[Any] | None = None, **params: Any) -> ChatRequest:
    return ChatRequest(
        model_id="gpt-5.4",
        messages=(Message("system", "s"), Message("user", "u")),
        params=params,
        schema=schema,
    )


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with httpx.Client(follow_redirects=False, trust_env=False) as client:
        yield client


def test_capabilities_and_protocol() -> None:
    b = OpenAIBackend()
    assert isinstance(b, Backend)
    assert b.capabilities.schema and b.capabilities.http_client and not b.capabilities.prices
    assert b.capabilities.providers == {"openai", "openai_compatible", "openrouter"}


def test_constants() -> None:
    assert OPENAI_BASE_URL == "https://api.openai.com/v1"
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_client_without_injected_http_has_no_sdk_retries() -> None:
    import openai

    c = OpenAIBackend().client(api_key=KEY, base_url=None, http=None)
    assert isinstance(c, openai.OpenAI)
    assert c.max_retries == 0
    assert str(c.base_url).rstrip("/") == OPENAI_BASE_URL


@respx.mock
def test_complete_success_sends_key_once_and_maps_usage(http: httpx.Client) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body()))
    b = OpenAIBackend()
    c = b.client(api_key=KEY, base_url=None, http=http)
    reply = b.complete(c, req(temperature=0))
    assert reply.text == '{"n": 1}'
    assert reply.usage.input_tokens == 7 and reply.usage.output_tokens == 3
    assert reply.usage.source == "reported" and reply.parsed is None and reply.cost is None
    assert reply.model == "gpt-5.4" and reply.provider == "openai" and reply.stop_reason == "stop"
    assert route.call_count == 1
    sent = json.loads(route.calls[0].request.content)
    assert sent["model"] == "gpt-5.4" and sent["temperature"] == 0
    assert sent["messages"] == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]
    assert "response_format" not in sent
    assert route.calls[0].request.headers["authorization"] == f"Bearer {KEY}"


@respx.mock
def test_missing_usage_is_none(http: httpx.Client) -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body(usage=False)))
    b = OpenAIBackend()
    c = b.client(api_key=KEY, base_url=None, http=http)
    u = b.complete(c, req()).usage
    assert u.input_tokens is None and u.output_tokens is None


@respx.mock
def test_partial_usage_keeps_missing_count_none(http: httpx.Client) -> None:
    body = ok_body()
    body["usage"] = {"prompt_tokens": 7}
    respx.post(URL).mock(return_value=httpx.Response(200, json=body))
    b = OpenAIBackend()
    c = b.client(api_key=KEY, base_url=None, http=http)
    reply = b.complete(c, req())
    assert reply.usage.input_tokens == 7 and reply.usage.output_tokens is None
    assert reply.cost is None


@respx.mock
def test_schema_becomes_json_schema_response_format(http: httpx.Client) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body()))
    b = OpenAIBackend()
    c = b.client(api_key=KEY, base_url=None, http=http)
    b.complete(c, req(schema=Out))
    rf = json.loads(route.calls[0].request.content)["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["name"] == "Out"
    assert rf["json_schema"]["strict"] is True
    assert "n" in rf["json_schema"]["schema"]["properties"]


@respx.mock
def test_no_sdk_retries_and_errors_are_raised_unchanged(http: httpx.Client) -> None:
    import openai

    route = respx.post(URL).mock(
        return_value=httpx.Response(429, json={"error": {"message": "slow"}})
    )
    b = OpenAIBackend()
    c = b.client(api_key=KEY, base_url=None, http=http)
    with pytest.raises(openai.RateLimitError):
        b.complete(c, req())
    assert route.call_count == 1


def test_error_kind_mapping() -> None:
    import openai

    b = OpenAIBackend()
    r = httpx.Request("POST", URL)

    def status(cls: type[openai.APIStatusError], code: int) -> openai.APIStatusError:
        return cls("m", response=httpx.Response(code, request=r), body=None)  # type: ignore[arg-type]

    assert b.error_kind(status(openai.AuthenticationError, 401)) is ErrorKind.auth
    assert b.error_kind(status(openai.PermissionDeniedError, 403)) is ErrorKind.permission
    assert b.error_kind(status(openai.NotFoundError, 404)) is ErrorKind.not_found
    assert b.error_kind(status(openai.RateLimitError, 429)) is ErrorKind.rate_limit
    assert b.error_kind(status(openai.InternalServerError, 500)) is ErrorKind.server
    assert b.error_kind(status(openai.BadRequestError, 400)) is ErrorKind.bad_request
    assert b.error_kind(openai.APITimeoutError(request=r)) is ErrorKind.timeout  # type: ignore[arg-type]
    assert b.error_kind(openai.APIConnectionError(request=r)) is ErrorKind.connection  # type: ignore[arg-type]
    assert b.error_kind(ValueError()) is ErrorKind.unknown


@respx.mock
def test_custom_base_url_uses_injected_http_client_and_omits_org_headers(
    http: httpx.Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The SDK fills these from the environment; a non-OpenAI server must not see them.
    monkeypatch.setenv("OPENAI_ORG_ID", "org-from-env")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj-from-env")
    route = respx.post("https://models.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=ok_body())
    )
    b = OpenAIBackend()
    c = b.client(api_key="not-needed", base_url="https://models.example.com/v1", http=http)
    b.complete(c, req())
    h = route.calls[0].request.headers
    assert "openai-organization" not in h and "openai-project" not in h
    assert h["authorization"] == "Bearer not-needed"


def test_refusal_becomes_text_and_stop_reason(http: httpx.Client) -> None:
    with respx.mock:
        body = ok_body()
        body["choices"][0]["message"] = {"role": "assistant", "content": None, "refusal": "no"}
        respx.post(URL).mock(return_value=httpx.Response(200, json=body))
        b = OpenAIBackend()
        c = b.client(api_key=KEY, base_url=None, http=http)
        r = b.complete(c, req())
        assert r.text == "no" and r.stop_reason == "refusal"


def test_price_is_none() -> None:
    with respx.mock, httpx.Client(trust_env=False) as http:
        respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body()))
        b = OpenAIBackend()
        reply = b.complete(b.client(api_key=KEY, base_url=None, http=http), req())
    assert OpenAIBackend().price(reply) is None
