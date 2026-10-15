"""The contract suite on LiteLLMBackend, with HTTP mocked by respx on the OpenAI path."""

import httpx
import pytest
import respx

import llmwarden as lw
from tests.contract.scenarios import *  # noqa: F401,F403

pytest.importorskip("litellm")
from llmwarden.backends.litellm import LiteLLMBackend  # noqa: E402

URL = "https://api.openai.com/v1/chat/completions"


def body(content: str, usage: bool = True) -> dict:
    out: dict = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    if usage:
        out["usage"] = {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
    return out


def ok(content: str = '{"n": 1}', usage: bool = True) -> httpx.Response:
    return httpx.Response(200, json=body(content, usage))


def err(status: int, message: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": message, "type": "x"}})


SCRIPTS = {
    "ok_usage": lambda: [ok()],
    "ok_no_usage": lambda: [ok("hi", usage=False)],
    "rate_limit_then_ok": lambda: [err(429, "slow"), ok()],
    "auth_then_ok": lambda: [err(401, "bad key"), ok()],
    "server_forever": lambda: [err(500, "boom")] * 5,
    "invalid_then_valid": lambda: [ok("not json"), ok('{"n": 2}')],
    "invalid_forever": lambda: [ok("nope")] * 5,
}


@pytest.fixture(scope="module")
def backend():
    return LiteLLMBackend()


@pytest.fixture
def router():
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as r:
        yield r


@pytest.fixture
def scenario():
    return lambda name: SCRIPTS[name]()


@pytest.fixture
def make_model(router, monkeypatch, backend):
    def make(script, *, resolver=None, **kw):
        router.post(URL).mock(side_effect=script)
        if resolver is not None:
            import llmwarden.guard as guard

            monkeypatch.setattr(guard, "resolve_host", resolver)
        kw.setdefault("retry", lw.Retry(attempts=3, base=0.0, cap=0.0))
        return lw.model("openai/gpt-4o-mini", backend=backend, **kw)

    return make
