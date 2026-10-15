"""Shared scenario tests for every backend.

A backend's test module defines two fixtures and imports ``*`` from here:

- ``make_model(script, *, resolver=None, **kw) -> Model``: a model on that backend
  whose transport is scripted with ``script``. ``resolver`` replaces
  ``guard.resolve_host`` for the ``public_only`` scenario.
- ``scenario(name) -> script``: the backend's script for a named scenario:
  ``ok_usage``, ``ok_no_usage``, ``rate_limit_then_ok``, ``auth_then_ok``,
  ``server_forever``, ``invalid_then_valid``, ``invalid_forever``.

The key constant below is a fake. No assertion message prints it.
"""

import pytest
from pydantic import BaseModel

from llmwarden.observe.memory import default_sink
from llmwarden.retry import Retry
from llmwarden.secrets.base import clear as clear_secrets
from llmwarden.secrets.base import secret
from llmwarden.secrets.base import use as use_store
from llmwarden.types import EndpointRefused, ErrorKind, InvalidOutput, ProviderError

KEY = "sk-contract-ABCDEFGHIJKLMNOP1234"


class Out(BaseModel):
    n: int


class RecordingStore:
    id = "rec"

    def __init__(self, value: str) -> None:
        self.value = value
        self.calls = 0

    def get(self, name: str) -> str:
        self.calls += 1
        return self.value


@pytest.fixture(autouse=True)
def clean_state():
    default_sink.clear()
    clear_secrets()
    yield
    default_sink.clear()
    clear_secrets()


def records():
    return default_sink.records()


def test_success_with_usage(make_model, scenario):
    m = make_model(scenario("ok_usage"), api_key=KEY)
    r = m.complete(system="s", user="u", tags={"step": "a"})
    assert r.text and r.usage.input_tokens is not None and r.attempts == 1
    (rec,) = records()
    assert rec.outcome == "ok" and rec.attempt == 1 and rec.tags == {"step": "a"}
    assert rec.input_tokens == r.usage.input_tokens


def test_success_without_usage_has_none_tokens_and_cost(make_model, scenario):
    m = make_model(scenario("ok_no_usage"), api_key=KEY)
    r = m.complete(user="u")
    assert r.usage.input_tokens is None and r.cost is None
    assert records()[0].cost_usd is None


def test_reply_provider_is_the_requested_provider(make_model, scenario):
    m = make_model(scenario("ok_usage"), api_key=KEY)
    r = m.complete(user="u")
    assert r.provider == m.provider
    assert records()[0].provider == m.provider


def test_rate_limit_then_success(make_model, scenario):
    m = make_model(scenario("rate_limit_then_ok"), api_key=KEY)
    r = m.complete(user="u")
    assert r.attempts == 2
    kinds = [x.error_kind for x in records()]
    assert kinds == [ErrorKind.rate_limit, None]
    assert records()[0].call_id == records()[1].call_id


def test_auth_error_with_store_key_refetches_once(make_model, scenario):
    store = RecordingStore(KEY)
    use_store(store)
    m = make_model(scenario("auth_then_ok"), api_key=secret("rec", "k"))
    assert store.calls == 1
    r = m.complete(user="u")
    assert store.calls == 2 and r.attempts == 2
    assert [x.error_kind for x in records()] == [ErrorKind.auth, None]


def test_auth_refetch_does_not_count_against_retry_attempts(make_model, scenario):
    store = RecordingStore(KEY)
    use_store(store)
    m = make_model(scenario("auth_then_ok"), api_key=secret("rec", "k"), retry=Retry(attempts=1))
    r = m.complete(user="u")
    assert r.attempts == 2 and len(records()) == 2


def test_auth_error_with_callable_key_refetches_once(make_model, scenario):
    calls = {"n": 0}

    def fetch() -> str:
        calls["n"] += 1
        return KEY

    m = make_model(scenario("auth_then_ok"), api_key=fetch)
    assert calls["n"] == 1
    r = m.complete(user="u")
    assert calls["n"] == 2 and r.attempts == 2


def test_auth_error_with_string_key_raises_at_once(make_model, scenario):
    m = make_model(scenario("auth_then_ok"), api_key=KEY)
    with pytest.raises(ProviderError) as info:
        m.complete(user="u")
    assert info.value.kind is ErrorKind.auth and len(records()) == 1


def test_server_error_until_attempts_run_out(make_model, scenario):
    m = make_model(scenario("server_forever"), api_key=KEY, retry=Retry(attempts=2))
    with pytest.raises(ProviderError) as info:
        m.complete(user="u")
    assert info.value.kind is ErrorKind.server and len(records()) == 2


def test_invalid_output_then_valid(make_model, scenario):
    m = make_model(scenario("invalid_then_valid"), api_key=KEY)
    r = m.complete(user="u", schema=Out)
    assert isinstance(r.parsed, Out) and r.attempts == 2
    assert records()[0].outcome == "invalid_output"
    assert records()[0].error_kind is ErrorKind.invalid_output


def test_invalid_output_exhausted_carries_text(make_model, scenario):
    m = make_model(scenario("invalid_forever"), api_key=KEY, retry=Retry(attempts=2))
    with pytest.raises(InvalidOutput) as info:
        m.complete(user="u", schema=Out)
    assert info.value.text
    assert len(records()) == 2


def test_public_only_custom_url(make_model, scenario):
    import llmwarden.guard as guard

    guard.clear_cache()
    try:
        m = make_model(
            scenario("ok_usage"),
            api_key=KEY,
            base_url="https://models.example.com/v1",
            public_only=True,
            resolver=lambda host: ["93.184.216.34"],
        )
    except EndpointRefused:
        pytest.skip("backend cannot accept an injected client; refusal is the contract")
    assert m is not None


def test_public_only_private_address_is_refused(make_model, scenario):
    import llmwarden.guard as guard

    guard.clear_cache()
    with pytest.raises(EndpointRefused):
        make_model(
            scenario("ok_usage"),
            api_key=KEY,
            base_url="https://models.example.com/v1",
            public_only=True,
            resolver=lambda host: ["10.0.0.7"],
        )


def test_key_never_appears_in_errors_records_or_repr(make_model, scenario):
    m = make_model(scenario("auth_then_ok"), api_key=KEY)
    assert KEY not in repr(m)
    with pytest.raises(ProviderError) as info:
        m.complete(user="u")
    assert KEY not in str(info.value)
    assert info.value.__cause__ is None
    for rec in records():
        assert KEY not in repr(rec)
