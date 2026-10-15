"""AnthropicBackend tests.

The anthropic SDK (1.14) runs on ``httpx2``, a separate package that respx
does not patch, and it refuses a plain ``httpx.Client`` as ``http_client``.
Every request here therefore goes through an ``httpx2.MockTransport``
injected into the SDK, and an autouse fixture disables ``httpx2``'s real
transport so an unmocked call fails instead of reaching the network.
"""

import json

import httpx
import httpx2
import pytest
from pydantic import BaseModel

from llmwarden.backends.anthropic import (
    ANTHROPIC_BASE_URL,
    DEFAULT_MAX_TOKENS,
    SCHEMA_TOOL,
    AnthropicBackend,
)
from llmwarden.backends.base import Backend
from llmwarden.types import ChatRequest, ErrorKind, Message

KEY = "sk-ant-test-ABCDEFGHIJKLMNOP1234"
URL = f"{ANTHROPIC_BASE_URL}/v1/messages"


class Out(BaseModel):
    n: int


def text_body(text="hello", usage=True):
    body = {
        "id": "m",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "content": [{"type": "text", "text": text}],
    }
    if usage:
        body["usage"] = {"input_tokens": 11, "output_tokens": 4}
    return body


def tool_body():
    body = text_body()
    body["stop_reason"] = "tool_use"
    body["content"] = [{"type": "tool_use", "id": "t1", "name": SCHEMA_TOOL, "input": {"n": 3}}]
    return body


def req(schema=None, messages=None, **params):
    msgs = messages or (Message("system", "s"), Message("user", "u"))
    return ChatRequest(model_id="claude-sonnet-5", messages=msgs, params=params, schema=schema)


class Wire:
    """Records every request the SDK sends and answers with queued responses."""

    def __init__(self):
        self.requests: list[httpx2.Request] = []
        self.responses: list[httpx2.Response] = []
        self.http = httpx2.Client(transport=httpx2.MockTransport(self._handle))

    def reply(self, status=200, body=None):
        self.responses.append(httpx2.Response(status, json=body))

    def _handle(self, request):
        self.requests.append(request)
        return self.responses.pop(0)

    def sent_json(self, index=0):
        return json.loads(self.requests[index].content)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def blocked(self, request):
        raise RuntimeError("network access is blocked in tests")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", blocked)


@pytest.fixture
def wire():
    w = Wire()
    yield w
    w.http.close()


def client(wire, base_url=None):
    return AnthropicBackend().client(api_key=KEY, base_url=base_url, http=wire.http)


def test_capabilities():
    b = AnthropicBackend()
    assert isinstance(b, Backend)
    assert b.capabilities.providers == {"anthropic"}
    assert b.capabilities.schema and b.capabilities.http_client
    assert not b.capabilities.prices


def test_client_has_no_retries_and_ignores_base_url_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://elsewhere.example.test")
    c = AnthropicBackend().client(api_key=KEY, base_url=None, http=None)
    assert c.max_retries == 0
    assert str(c.base_url).rstrip("/") == ANTHROPIC_BASE_URL
    c.close()


def test_client_uses_base_url_and_injected_http_client(wire):
    c = client(wire, base_url="https://proxy.example.test")
    assert c._client is wire.http
    wire.reply(200, text_body())
    AnthropicBackend().complete(c, req())
    assert str(wire.requests[0].url) == "https://proxy.example.test/v1/messages"


def test_complete_maps_system_messages_and_usage_and_default_max_tokens(wire):
    wire.reply(200, text_body())
    r = AnthropicBackend().complete(client(wire), req())
    assert r.text == "hello" and r.usage.input_tokens == 11 and r.usage.output_tokens == 4
    assert r.usage.source == "reported"
    assert r.provider == "anthropic" and r.stop_reason == "end_turn"
    assert r.model == "claude-sonnet-5"
    assert r.parsed is None and r.cost is None
    sent = wire.sent_json()
    assert sent["system"] == "s" and sent["messages"] == [{"role": "user", "content": "u"}]
    assert sent["max_tokens"] == DEFAULT_MAX_TOKENS
    assert str(wire.requests[0].url) == URL
    assert wire.requests[0].headers["x-api-key"] == KEY


def test_params_pass_through_and_max_tokens_respected(wire):
    wire.reply(200, text_body())
    AnthropicBackend().complete(client(wire), req(max_tokens=50, thinking={"type": "adaptive"}))
    sent = wire.sent_json()
    assert sent["max_tokens"] == 50 and sent["thinking"] == {"type": "adaptive"}


def test_schema_uses_forced_tool_and_returns_input_as_json_text(wire):
    wire.reply(200, tool_body())
    r = AnthropicBackend().complete(client(wire), req(schema=Out))
    assert json.loads(r.text) == {"n": 3}
    sent = wire.sent_json()
    assert sent["tool_choice"] == {"type": "tool", "name": SCHEMA_TOOL}
    assert sent["tools"][0]["name"] == SCHEMA_TOOL
    assert "n" in sent["tools"][0]["input_schema"]["properties"]


def test_missing_usage_is_none(wire):
    wire.reply(200, text_body(usage=False))
    r = AnthropicBackend().complete(client(wire), req())
    assert r.usage.input_tokens is None and r.usage.output_tokens is None


def test_server_error_raises_sdk_exception_unchanged_and_no_retries(wire):
    import anthropic

    wire.reply(529, {"type": "error", "error": {"type": "overloaded_error", "message": "busy"}})
    with pytest.raises(anthropic.APIStatusError):
        AnthropicBackend().complete(client(wire), req())
    assert len(wire.requests) == 1


def test_error_kind_mapping():
    import anthropic

    b = AnthropicBackend()
    r = httpx2.Request("POST", URL)

    def status(cls, code):
        return cls("m", response=httpx2.Response(code, request=r), body=None)

    assert b.error_kind(status(anthropic.AuthenticationError, 401)) is ErrorKind.auth
    assert b.error_kind(status(anthropic.PermissionDeniedError, 403)) is ErrorKind.permission
    assert b.error_kind(status(anthropic.NotFoundError, 404)) is ErrorKind.not_found
    assert b.error_kind(status(anthropic.RateLimitError, 429)) is ErrorKind.rate_limit
    assert b.error_kind(status(anthropic.InternalServerError, 500)) is ErrorKind.server
    assert b.error_kind(status(anthropic.BadRequestError, 400)) is ErrorKind.bad_request
    assert b.error_kind(anthropic.APITimeoutError(request=r)) is ErrorKind.timeout
    assert b.error_kind(anthropic.APIConnectionError(request=r)) is ErrorKind.connection
    assert b.error_kind(status(anthropic.APIStatusError, 529)) is ErrorKind.server
    assert b.error_kind(ValueError()) is ErrorKind.unknown


def test_price_is_none():
    assert AnthropicBackend().price(None) is None  # type: ignore[arg-type]


def test_betas_route_through_beta_messages(wire):
    wire.reply(200, text_body())
    AnthropicBackend().complete(client(wire), req(betas=["some-beta-2026-01-01"]))
    assert "some-beta-2026-01-01" in wire.requests[0].headers.get("anthropic-beta", "")
    assert "betas" not in wire.sent_json()


def test_plain_httpx_client_is_refused_by_the_sdk():
    with httpx.Client() as http, pytest.raises(TypeError):
        AnthropicBackend().client(api_key=KEY, base_url=None, http=http)
