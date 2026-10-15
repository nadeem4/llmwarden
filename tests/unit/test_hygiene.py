import base64
import logging
import urllib.parse

import pytest

from llmwarden.hygiene import ScrubFilter, mask, reraise, scrub
from llmwarden.types import ErrorKind, InvalidOutput, ProviderError

KEY = "sk-test-ABCDEFGHIJKLMNOP1234"


def assert_absent(text: str) -> None:
    assert KEY not in text, "key leaked"  # message never includes the key


def test_scrub_plain_urlencoded_and_base64():
    msg = (
        f"auth {KEY} q={urllib.parse.quote(KEY + '/x')} b={base64.b64encode(KEY.encode()).decode()}"
    )
    out = scrub(msg, [KEY])
    assert_absent(out)
    assert urllib.parse.quote(KEY + "/x") not in out
    assert base64.b64encode(KEY.encode()).decode() not in out
    assert out.count("[redacted]") == 3


def test_scrub_ignores_empty_secrets():
    assert scrub("hello", ["", None]) == "hello"  # type: ignore[list-item]


def test_mask():
    assert mask(KEY) == "sk-...1234"
    assert mask("short") == "***"
    assert mask("") == "***"


def test_reraise_builds_scrubbed_error_without_cause():
    err = RuntimeError(f"401 for key {KEY}")
    with pytest.raises(ProviderError) as info:
        reraise(err, kind=ErrorKind.auth, secrets=[KEY], provider="openai", status=401)
    e = info.value
    assert_absent(str(e))
    assert e.kind is ErrorKind.auth and e.status == 401 and e.provider == "openai"
    assert e.__cause__ is None and e.__suppress_context__ is True


def test_reraise_invalid_output_carries_text():
    with pytest.raises(InvalidOutput) as info:
        reraise(
            ValueError("bad"),
            kind=ErrorKind.invalid_output,
            secrets=[],
            provider="fake",
            text="{not json",
        )
    assert info.value.text == "{not json"


def test_logging_filter_scrubs_msg_and_args(caplog):
    logger = logging.getLogger("llmwarden.test")
    logger.addFilter(ScrubFilter([KEY]))
    with caplog.at_level(logging.INFO, logger="llmwarden.test"):
        logger.info("key %s used", KEY)
        logger.info(f"literal {KEY}")
    for rec in caplog.records:
        assert_absent(rec.getMessage())


def test_logging_filter_keeps_clean_non_string_args(caplog):
    logger = logging.getLogger("llmwarden.test.ints")
    logger.addFilter(ScrubFilter([KEY]))
    with caplog.at_level(logging.INFO, logger="llmwarden.test.ints"):
        logger.info("%d calls for %s", 3, KEY)
    (rec,) = caplog.records
    assert rec.getMessage() == "3 calls for [redacted]"
