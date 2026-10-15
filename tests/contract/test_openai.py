"""The contract suite on OpenAIBackend.

The openai SDK sends through its own ``httpx2`` library, which respx cannot see, so
these tests script responses by patching ``httpx2.HTTPTransport.handle_request``. Any
request outside the script fails the test, so nothing can reach the network.
"""

import pytest

import llmwarden as lw
from llmwarden.backends.openai import OPENAI_BASE_URL
from tests.contract.scenarios import *  # noqa: F401,F403

pytest.importorskip("openai")
httpx2 = pytest.importorskip("httpx2")
URL = f"{OPENAI_BASE_URL}/chat/completions"


def body(content: str, usage: bool = True) -> dict:
    out: dict = {
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
        out["usage"] = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    return out


def ok(content: str = '{"n": 1}', usage: bool = True) -> dict:
    return {"status": 200, "json": body(content, usage)}


def err(status: int, message: str) -> dict:
    return {"status": status, "json": {"error": {"message": message, "type": "x"}}}


SCRIPTS = {
    "ok_usage": lambda: [ok()],
    "ok_no_usage": lambda: [ok("hi", usage=False)],
    "rate_limit_then_ok": lambda: [err(429, "slow"), ok()],
    "auth_then_ok": lambda: [err(401, "bad key"), ok()],
    "server_forever": lambda: [err(500, "boom")] * 5,
    "invalid_then_valid": lambda: [ok("not json"), ok('{"n": 2}')],
    "invalid_forever": lambda: [ok("nope")] * 5,
}


@pytest.fixture
def scenario():
    return lambda name: SCRIPTS[name]()


@pytest.fixture
def transport(monkeypatch):
    """Patch the SDK's transport to serve one scripted response per request."""
    queue: list[dict] = []
    seen: list[httpx2.Request] = []

    def handle(self, request):
        seen.append(request)
        if not queue:
            raise AssertionError(f"unexpected request to {request.url.host}")
        item = queue.pop(0)
        return httpx2.Response(item["status"], json=item["json"], request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", handle)
    return queue, seen


@pytest.fixture
def make_model(transport, monkeypatch):
    queue, _seen = transport

    def make(script, *, resolver=None, **kw):
        queue.extend(script)
        name = "openai/gpt-5.4"
        if resolver is not None:
            import llmwarden.guard as guard

            monkeypatch.setattr(guard, "resolve_host", resolver)
            name = "openai_compatible/gpt-5.4"
        kw.setdefault("retry", lw.Retry(attempts=3, base=0.0, cap=0.0))
        return lw.model(name, **kw)

    return make
