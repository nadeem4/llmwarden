"""The contract suite on FakeBackend. The reference run; the real backends must match it."""

import pytest

import llmwarden as lw
from llmwarden.backends.fake import (
    FakeAuthError,
    FakeBackend,
    FakeRateLimit,
    FakeServerError,
    reply,
)
from llmwarden.types import Usage
from tests.contract.scenarios import *  # noqa: F401,F403

SCRIPTS = {
    "ok_usage": lambda: [reply('{"n": 1}', usage=Usage(7, 3))],
    "ok_no_usage": lambda: [reply("hi")],
    "rate_limit_then_ok": lambda: [FakeRateLimit("slow"), reply("ok", usage=Usage(1, 1))],
    "auth_then_ok": lambda: [FakeAuthError("401 bad key"), reply("ok", usage=Usage(1, 1))],
    "server_forever": lambda: [FakeServerError("500")] * 5,
    "invalid_then_valid": lambda: [reply("not json"), reply('{"n": 2}', usage=Usage(1, 1))],
    "invalid_forever": lambda: [reply("nope")] * 5,
}


@pytest.fixture
def scenario():
    return lambda name: SCRIPTS[name]()


@pytest.fixture
def make_model(monkeypatch):
    def make(script, *, resolver=None, **kw):
        if resolver is not None:
            import llmwarden.guard as guard

            monkeypatch.setattr(guard, "resolve_host", resolver)
        kw.setdefault("retry", lw.Retry(attempts=3, base=0.0, cap=0.0))
        return lw.model("fake/fake-model", backend=FakeBackend(script), **kw)

    return make
