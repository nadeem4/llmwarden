import pytest

from llmwarden.backends.base import Backend
from llmwarden.backends.fake import FakeAuthError, FakeBackend, FakeRateLimit, reply
from llmwarden.types import ChatRequest, ErrorKind, Message, Usage


def _req(text: str = "hi") -> ChatRequest:
    return ChatRequest(model_id="fake-model", messages=(Message("user", text),))


def test_fake_is_a_backend_and_declares_capabilities():
    b = FakeBackend()
    assert isinstance(b, Backend)
    assert b.capabilities.schema and b.capabilities.http_client and not b.capabilities.prices
    assert "fake" in b.capabilities.providers


def test_replies_are_returned_in_order_and_requests_recorded():
    b = FakeBackend([reply("one"), reply("two", usage=Usage(3, 4))])
    c = b.client(api_key="k", base_url=None, http=None)
    assert b.complete(c, _req("a")).text == "one"
    r = b.complete(c, _req("b"))
    assert r.text == "two" and r.usage == Usage(3, 4) and r.parsed is None and r.cost is None
    assert [m.content for q in b.requests for m in q.messages] == ["a", "b"]


def test_exceptions_in_script_are_raised():
    b = FakeBackend([FakeRateLimit("slow down")])
    c = b.client(api_key="k", base_url=None, http=None)
    with pytest.raises(FakeRateLimit):
        b.complete(c, _req())


def test_running_out_of_replies_is_an_assertion_error():
    b = FakeBackend([])
    c = b.client(api_key="k", base_url=None, http=None)
    with pytest.raises(AssertionError):
        b.complete(c, _req())


def test_error_kind_maps_fake_exceptions():
    b = FakeBackend()
    assert b.error_kind(FakeAuthError("x")) is ErrorKind.auth
    assert b.error_kind(FakeRateLimit("x")) is ErrorKind.rate_limit
    assert b.error_kind(ValueError("x")) is ErrorKind.unknown


def test_client_records_key_and_price_is_none():
    b = FakeBackend()
    b.client(api_key="secret-value", base_url=None, http=None)
    assert len(b.keys_seen) == 1
    assert "secret-value" not in repr(b)
    assert b.price(reply("x")) is None
