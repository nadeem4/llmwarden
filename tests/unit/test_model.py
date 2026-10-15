"""Unit tests for ``model.py``: what the shared contract scenarios do not cover."""

import sys

import pytest
from pydantic import BaseModel

import llmwarden as lw
from llmwarden.backends.base import Capabilities
from llmwarden.backends.fake import FakeBackend, FakeServerError, reply
from llmwarden.observe.memory import default_sink
from llmwarden.types import NotSupported, Price, ProviderUnavailable, Usage


@pytest.fixture(autouse=True)
def _clean():
    default_sink.clear()
    yield
    default_sink.clear()


def test_name_is_split_and_repr_masks_key():
    m = lw.model("fake/x", api_key="sk-test-ABCDEFGHIJKLMNOP1234", backend=FakeBackend())
    assert m.provider == "fake" and m.model_id == "x"
    assert "ABCDEFGHIJKLMNOP" not in repr(m) and "sk-...1234" in repr(m)


def test_repr_shows_secret_as_store_and_name_and_hides_other_sources():
    from llmwarden.secrets.base import clear, secret, use

    clear()

    class S:
        id = "s"

        def get(self, name: str) -> str:
            return "sk-secret-ABCDEFGHIJKLMNOP9999"

    use(S())
    try:
        m = lw.model("fake/x", api_key=secret("s", "n"), backend=FakeBackend())
        assert "store='s'" in repr(m) and "name='n'" in repr(m)
        assert "ABCDEFGHIJKLMNOP" not in repr(m)
        m2 = lw.model(
            "fake/x", api_key=lambda: "sk-call-ABCDEFGHIJKLMNOP9999", backend=FakeBackend()
        )
        assert "ABCDEFGHIJKLMNOP" not in repr(m2)
    finally:
        clear()


def test_bad_name_raises_value_error():
    with pytest.raises(ValueError):
        lw.model("no-slash", backend=FakeBackend())


def test_both_message_forms_is_error_and_tools_not_supported():
    m = lw.model("fake/x", api_key="k", backend=FakeBackend([reply("a")]))
    with pytest.raises(ValueError):
        m.complete(messages=[lw.Message("user", "u")], user="u")
    with pytest.raises(NotSupported):
        m.complete(user="u", params={"tools": []})


def test_messages_form_is_passed_through_and_params_merge():
    b = FakeBackend([reply("a")])
    m = lw.model("fake/x", api_key="k", backend=b, params={"temperature": 0.1, "top_p": 1})
    m.complete(messages=[lw.Message("system", "s"), lw.Message("user", "u")], params={"top_p": 0.5})
    sent = b.requests[0]
    assert [x.role for x in sent.messages] == ["system", "user"]
    assert dict(sent.params) == {"temperature": 0.1, "top_p": 0.5}
    assert sent.model_id == "x"


def test_schema_prompt_added_when_backend_lacks_schema():
    b = FakeBackend(
        [reply('{"n": 1}')],
        capabilities=Capabilities(
            frozenset({"fake"}), schema=False, prices=False, http_client=True
        ),
    )
    m = lw.model("fake/x", api_key="k", backend=b)

    class Out(BaseModel):
        n: int

    r = m.complete(system="s", user="u", schema=Out)
    assert r.parsed.n == 1
    sent = b.requests[0]
    assert sent.messages[0].role == "system" and "JSON schema" in sent.messages[0].content
    assert sent.messages[0].content.startswith("s")
    assert sent.schema is None and "schema" not in sent.params


def test_schema_passed_natively_when_backend_supports_it():
    b = FakeBackend([reply('{"n": 1}')])
    m = lw.model("fake/x", api_key="k", backend=b)

    class Out(BaseModel):
        n: int

    m.complete(user="u", schema=Out)
    sent = b.requests[0]
    assert sent.schema is Out and [x.role for x in sent.messages] == ["user"]


def test_price_order_model_then_table_then_none():
    b = FakeBackend(
        [
            reply("a", usage=Usage(1_000_000, 0)),
            reply("a", usage=Usage(1_000_000, 0)),
            reply("a", usage=Usage(1, 1)),
        ]
    )
    m = lw.model("fake/x", api_key="k", backend=b, price=Price(3.0, 0.0))
    assert m.complete(user="u").cost.usd == 3.0 and m.complete(user="u").cost.source == "model"
    m2 = lw.model("fake/x", api_key="k", backend=b)
    assert m2.complete(user="u").cost is None


def test_backend_price_used_when_backend_can_price():
    class PricingFake(FakeBackend):
        def price(self, reply):
            return lw.Cost(usd=0.25, source="backend")

    b = PricingFake(
        [reply("a", usage=Usage(1, 1))],
        capabilities=Capabilities(frozenset({"fake"}), schema=True, prices=True, http_client=True),
    )
    r = lw.model("fake/x", api_key="k", backend=b).complete(user="u")
    assert r.cost == lw.Cost(usd=0.25, source="backend")
    assert default_sink.records()[0].price_source == "backend"


def test_table_price_used_for_known_model():
    b = FakeBackend(
        [reply("a", usage=Usage(1_000_000, 1_000_000))],
        capabilities=Capabilities(
            frozenset({"openai"}), schema=True, prices=False, http_client=True
        ),
    )
    r = lw.model("openai/gpt-5.4", api_key="k", backend=b).complete(user="u")
    assert r.cost is not None and r.cost.source == "llmwarden" and r.cost.usd == 17.5


def test_context_tags_merge_under_call_tags():
    b = FakeBackend([reply("a")])
    m = lw.model("fake/x", api_key="k", backend=b)
    with lw.tags(customer="acme", step="outer"):
        m.complete(user="u", tags={"step": "inner"})
    assert default_sink.records()[0].tags == {"customer": "acme", "step": "inner"}


def test_fallback_runs_with_shared_call_id_and_counts_attempts():
    primary = FakeBackend([FakeServerError("x")] * 2)
    second = FakeBackend([reply("saved", usage=Usage(1, 1))])
    fb = lw.model("fake/second", api_key="k", backend=second)
    m = lw.model(
        "fake/first",
        api_key="k",
        backend=primary,
        retry=lw.Retry(attempts=2, base=0, cap=0),
        fallback=fb,
    )
    r = m.complete(user="u")
    assert r.text == "saved" and r.attempts == 3 and r.model == "fake-model"
    recs = default_sink.records()
    assert len(recs) == 3 and len({x.call_id for x in recs}) == 1
    assert [x.model for x in recs] == ["first", "first", "fake-model"]
    assert [x.attempt for x in recs] == [1, 2, 3]


def test_non_retryable_error_is_not_retried_but_still_falls_back():
    from llmwarden.backends.fake import FakeBadRequest

    primary = FakeBackend([FakeBadRequest("bad"), reply("never")])
    m = lw.model("fake/first", api_key="k", backend=primary)
    with pytest.raises(lw.ProviderError) as info:
        m.complete(user="u")
    assert info.value.kind is lw.ErrorKind.bad_request
    assert len(default_sink.records()) == 1 and len(primary.replies) == 1

    default_sink.clear()
    primary = FakeBackend([FakeBadRequest("bad"), reply("never")])
    fb = lw.model("fake/second", api_key="k", backend=FakeBackend([reply("saved")]))
    m = lw.model("fake/first", api_key="k", backend=primary, fallback=fb)
    r = m.complete(user="u")
    assert r.text == "saved" and r.attempts == 2
    assert [x.outcome for x in default_sink.records()] == ["provider_error", "ok"]


def test_unknown_provider_without_litellm_raises_provider_unavailable(monkeypatch):
    import llmwarden.backends as backends

    backends.reset()
    monkeypatch.setitem(sys.modules, "llmwarden.backends.litellm", None)
    with pytest.raises(ProviderUnavailable) as info:
        lw.model("groq/llama", api_key="k")
    assert "litellm" in str(info.value)
    backends.reset()


def test_backend_table_override_is_used():
    import llmwarden.backends as backends

    b = FakeBackend([reply("a")], capabilities=Capabilities(frozenset({"groq"}), True, False, True))
    backends.use("groq", b)
    try:
        m = lw.model("groq/llama", api_key="k")
        assert m.backend is b and m.model_id == "llama"
    finally:
        backends.reset()


def test_default_backend_that_does_not_reach_provider_is_refused():
    import llmwarden.backends as backends

    backends.use("groq", FakeBackend())
    try:
        with pytest.raises(ValueError):
            lw.model("groq/llama", api_key="k")
    finally:
        backends.reset()


def test_litellm_backend_keeps_the_provider_prefix_in_model_id():
    class LiteLLMBackend(FakeBackend):
        pass

    b = LiteLLMBackend([reply("a")])
    m = lw.model("groq/llama", api_key="k", backend=b)
    assert m.model_id == "groq/llama" and m.provider == "groq"
    m.complete(user="u")
    assert b.requests[0].model_id == "groq/llama"


def test_refresh_resolves_key_again():
    from llmwarden.secrets.base import clear, secret, use

    clear()

    class S:
        id = "s"
        calls = 0

        def get(self, name):
            S.calls += 1
            return "k"

    use(S())
    try:
        b = FakeBackend()
        m = lw.model("fake/x", api_key=secret("s", "n"), backend=b)
        m.refresh()
        assert S.calls == 2 and len(b.keys_seen) == 2
    finally:
        clear()


def test_two_models_on_one_secret_fetch_it_once():
    from llmwarden.secrets.base import clear, secret, use

    clear()

    class S:
        id = "s"
        calls = 0

        def get(self, name):
            S.calls += 1
            return "k"

    use(S())
    try:
        ref = secret("s", "n")
        lw.model("fake/x", api_key=ref, backend=FakeBackend())
        lw.model("fake/y", api_key=ref, backend=FakeBackend())
        assert S.calls == 1
    finally:
        clear()


def test_missing_key_reads_the_provider_env_var(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "from-env")
    b = FakeBackend()
    lw.model("fake/x", backend=b)
    assert b.keys_seen == ["from-env"]


def test_missing_key_for_unknown_env_var_raises_secret_not_found(monkeypatch):
    monkeypatch.delenv("FAKE_API_KEY", raising=False)
    from llmwarden.secrets.base import clear

    clear()
    with pytest.raises(lw.SecretNotFound):
        lw.model("fake/x", backend=FakeBackend())


def test_openai_compatible_without_key_gets_placeholder():
    from llmwarden.model import PLACEHOLDER_KEY

    b = FakeBackend(capabilities=Capabilities(frozenset({"openai_compatible"}), True, False, True))
    lw.model("openai_compatible/m", backend=b, base_url="http://localhost:8000/v1")
    assert b.keys_seen == [PLACEHOLDER_KEY]


def test_public_only_without_http_client_capability_is_refused():
    b = FakeBackend(capabilities=Capabilities(frozenset({"fake"}), True, False, http_client=False))
    with pytest.raises(lw.EndpointRefused):
        lw.model(
            "fake/x",
            api_key="k",
            backend=b,
            base_url="https://models.example.com",
            public_only=True,
        )


def test_base_url_without_public_only_skips_the_guard(monkeypatch):
    import llmwarden.guard as guard

    def boom(url, **kw):
        raise AssertionError("guard ran")

    monkeypatch.setattr(guard, "check_url", boom)
    b = FakeBackend()
    lw.model("fake/x", api_key="k", backend=b, base_url="http://localhost:11434/v1")
    assert len(b.keys_seen) == 1


def test_http_client_is_shared_per_backend_class():
    a, b = FakeBackend([reply("a")]), FakeBackend([reply("b")])
    ma = lw.model("fake/x", api_key="k", backend=a)
    mb = lw.model("fake/y", api_key="k", backend=b)
    ca = ma.complete(user="u")
    assert ca.text == "a"
    assert ma._client.http is mb._client.http and ma._client.http is not None


def test_shared_client_comes_from_the_backend_http_lib():
    httpx2 = pytest.importorskip("httpx2")
    caps = Capabilities(frozenset({"fake"}), True, False, True, http_lib="httpx2")

    class Httpx2Fake(FakeBackend):
        pass

    b = Httpx2Fake([reply("a")], capabilities=caps)
    m = lw.model("fake/x", api_key="k", backend=b)
    assert isinstance(m._client.http, httpx2.Client)
    assert m._client.http.follow_redirects is False


def test_guarded_client_comes_from_the_backend_http_lib(monkeypatch):
    import llmwarden.guard as guard

    httpx2 = pytest.importorskip("httpx2")
    guard.clear_cache()
    monkeypatch.setattr(guard, "resolve_host", lambda host: ["93.184.216.34"])
    caps = Capabilities(frozenset({"fake"}), True, False, True, http_lib="httpx2")
    b = FakeBackend([reply("a")], capabilities=caps)
    m = lw.model(
        "fake/x", api_key="k", backend=b, base_url="https://models.example.com/v1", public_only=True
    )
    assert isinstance(m._client.http, httpx2.Client) and m._client.http.trust_env is False
    m._client.http.close()
