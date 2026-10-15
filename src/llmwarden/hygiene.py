"""Key hygiene: no key in any error, log line or repr.

- ``scrub(text, secrets) -> str``: replace every secret in ``secrets`` with
  ``[redacted]``. Also matches each secret URL-encoded and base64-encoded, since
  SDK messages can embed headers either way.
- ``mask(key) -> str``: the first three and last four characters, or ``***``
  when the key is shorter than twelve.
- ``ScrubFilter(secrets)``: a ``logging.Filter`` that scrubs ``record.msg`` and
  ``record.args``. Applications add it to any logger.
- ``reraise(error, kind, secrets, provider, status) -> NoReturn``: build a
  ``ProviderError`` (or ``InvalidOutput`` when ``kind`` is ``invalid_output``)
  from the scrubbed message and raise it ``from None``. The original is dropped
  because SDK errors hold the request, and the request holds the key.

Depends on: types.
"""

from __future__ import annotations

import base64
import logging
import urllib.parse
from collections.abc import Iterable
from typing import NoReturn

from llmwarden.types import ErrorKind, InvalidOutput, ProviderError

REDACTED = "[redacted]"


def _forms(secret: str) -> list[str]:
    forms = [secret, urllib.parse.quote(secret, safe=""), urllib.parse.quote(secret)]
    forms.append(base64.b64encode(secret.encode()).decode())
    forms.append(base64.urlsafe_b64encode(secret.encode()).decode().rstrip("="))
    # Longest first so a form that contains another is replaced whole.
    return sorted(set(forms), key=len, reverse=True)


def scrub(text: str, secrets: Iterable[str]) -> str:
    for secret in secrets:
        if not secret:
            continue
        for form in _forms(secret):
            text = text.replace(form, REDACTED)
    return text


def mask(key: str) -> str:
    if not key or len(key) < 12:
        return "***"
    return f"{key[:3]}...{key[-4:]}"


class ScrubFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def _scrub_arg(self, value: object) -> object:
        # Keep a clean non-string argument as is so ``%d`` and friends still format.
        text = str(value)
        scrubbed = scrub(text, self._secrets)
        return scrubbed if scrubbed != text else value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub(str(record.msg), self._secrets)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._scrub_arg(v) for k, v in record.args.items()}
            else:
                record.args = tuple(self._scrub_arg(a) for a in record.args)
        return True


def reraise(
    error: BaseException,
    *,
    kind: ErrorKind,
    secrets: Iterable[str],
    provider: str,
    status: int | None = None,
    text: str | None = None,
) -> NoReturn:
    message = scrub(str(error) or type(error).__name__, secrets)
    if kind is ErrorKind.invalid_output:
        raise InvalidOutput(message, text=text or "", provider=provider) from None
    raise ProviderError(message, kind=kind, provider=provider, status=status) from None
