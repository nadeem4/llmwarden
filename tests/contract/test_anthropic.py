"""The contract suite on AnthropicBackend.

The anthropic SDK sends through its own ``httpx2`` library, which respx cannot see, so
these tests script responses by patching ``httpx2.HTTPTransport.handle_request``. Any
request outside the script fails the test, so nothing can reach the network.
"""

import pytest

import llmwarden as lw
from llmwarden.backends.anthropic import SCHEMA_TOOL
from tests.contract.scenarios import *  # noqa: F401,F403

pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")


def body(content: list[dict], usage: bool = True, stop: str = "end_turn") -> dict:
    out: dict = {
        "id": "m",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "stop_reason": stop,
        "stop_sequence": None,
        "content": content,
    }
    if usage:
        out["usage"] = {"input_tokens": 11, "output_tokens": 4}
    return out


def text(t: str = "hello", usage: bool = True) -> dict:
    return {"status": 200, "json": body([{"type": "text", "text": t}], usage)}


def tool(inp: dict) -> dict:
    block = {"type": "tool_use", "id": "t1", "name": SCHEMA_TOOL, "input": inp}
    return {"status": 200, "json": body([block], True, stop="tool_use")}


def err(status: int, kind: str, message: str) -> dict:
    return {
        "status": status,
        "json": {"type": "error", "error": {"type": kind, "message": message}},
    }


SCRIPTS = {
    "ok_usage": lambda: [text()],
    "ok_no_usage": lambda: [text("hi", usage=False)],
    "rate_limit_then_ok": lambda: [err(429, "rate_limit_error", "slow"), text()],
    "auth_then_ok": lambda: [err(401, "authentication_error", "bad key"), text()],
    "server_forever": lambda: [err(500, "api_error", "boom")] * 5,
    "invalid_then_valid": lambda: [tool({"n": "x"}), tool({"n": 2})],
    "invalid_forever": lambda: [tool({"n": "x"})] * 5,
}


@pytest.fixture
def scenario():
    return lambda name: SCRIPTS[name]()


@pytest.fixture
def transport(monkeypatch):
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
        if resolver is not None:
            import llmwarden.guard as guard

            monkeypatch.setattr(guard, "resolve_host", resolver)
        kw.setdefault("retry", lw.Retry(attempts=3, base=0.0, cap=0.0))
        return lw.model("anthropic/claude-sonnet-5", **kw)

    return make
