import pytest

from llmwarden.backends.fake import reply
from llmwarden.retry import DEFAULT_RETRY_ON, Retry, run, wait
from llmwarden.types import ChatReply, ErrorKind, ProviderError


def err(kind: ErrorKind) -> ProviderError:
    return ProviderError("x", kind=kind, provider="fake")


def test_defaults() -> None:
    p = Retry()
    assert p.attempts == 3 and p.base == 0.5 and p.cap == 8.0
    assert (
        p.on
        == DEFAULT_RETRY_ON
        == frozenset(
            {
                ErrorKind.rate_limit,
                ErrorKind.timeout,
                ErrorKind.connection,
                ErrorKind.server,
                ErrorKind.invalid_output,
            }
        )
    )


def test_wait_is_full_jitter_bounded_by_cap() -> None:
    p = Retry(base=0.5, cap=8.0)
    assert wait(p, 1, rng=lambda: 1.0) == 0.5
    assert wait(p, 2, rng=lambda: 1.0) == 1.0
    assert wait(p, 10, rng=lambda: 1.0) == 8.0
    assert wait(p, 3, rng=lambda: 0.0) == 0.0


def test_run_returns_first_success_without_sleeping() -> None:
    waits: list[float] = []
    out = run(lambda n: reply(f"ok{n}"), Retry(), sleep=waits.append)
    assert out.text == "ok1" and waits == []


def test_run_retries_retryable_kinds_and_sleeps_between() -> None:
    calls: list[int] = []
    waits: list[float] = []

    def attempt(n: int) -> ChatReply:
        calls.append(n)
        if n < 3:
            raise err(ErrorKind.rate_limit)
        return reply("done")

    out = run(attempt, Retry(attempts=3), sleep=waits.append)
    assert out.text == "done" and calls == [1, 2, 3] and len(waits) == 2
    assert all(0 <= w <= 8.0 for w in waits)


def test_run_raises_last_error_when_attempts_run_out() -> None:
    def attempt(n: int) -> ChatReply:
        raise err(ErrorKind.server)

    with pytest.raises(ProviderError) as info:
        run(attempt, Retry(attempts=2), sleep=lambda s: None)
    assert info.value.kind is ErrorKind.server


def test_run_does_not_retry_non_retryable_kind() -> None:
    calls: list[int] = []

    def attempt(n: int) -> ChatReply:
        calls.append(n)
        raise err(ErrorKind.auth)

    with pytest.raises(ProviderError):
        run(attempt, Retry(attempts=3), sleep=lambda s: None)
    assert calls == [1]


def test_run_lets_non_provider_errors_through_unchanged() -> None:
    def attempt(n: int) -> ChatReply:
        raise KeyError("boom")

    with pytest.raises(KeyError):
        run(attempt, Retry(), sleep=lambda s: None)
