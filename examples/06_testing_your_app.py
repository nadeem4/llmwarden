"""Test your own code without a network, using the same FakeBackend llmwarden tests with.

Script replies and errors in order, then assert on what your code did with them and
on what the backend received. Runs offline.
"""

from pydantic import BaseModel

import llmwarden as lw
from llmwarden.backends import FakeBackend
from llmwarden.backends.fake import FakeServerError, reply
from llmwarden.types import Usage


class Verdict(BaseModel):
    approved: bool


def review(model: lw.Model, text: str) -> bool:
    """The code under test: ask for a verdict, treat an outage as 'not approved'."""
    try:
        return model.complete(
            system="Approve or reject.", user=text, schema=Verdict
        ).parsed.approved
    except lw.ProviderError:
        return False


def test_approves_when_the_model_says_so() -> None:
    backend = FakeBackend([reply('{"approved": true}', usage=Usage(10, 2))])
    model = lw.model("fake/reviewer", api_key="test-key", backend=backend)
    assert review(model, "looks fine") is True
    sent = backend.requests[0]
    assert sent.messages[0].content == "Approve or reject."
    assert sent.schema is Verdict  # the fake declares native schema support


def test_outage_means_not_approved() -> None:
    backend = FakeBackend([FakeServerError("500")] * 3)
    model = lw.model(
        "fake/reviewer",
        api_key="test-key",
        backend=backend,
        retry=lw.Retry(attempts=3, base=0.0, cap=0.0),
    )
    assert review(model, "anything") is False
    assert len(backend.requests) == 3  # every attempt reached the backend and was recorded


if __name__ == "__main__":
    test_approves_when_the_model_says_so()
    test_outage_means_not_approved()
    print("both tests passed")
