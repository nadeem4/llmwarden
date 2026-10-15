"""``EnvStore``: environment variables, and ``.env`` files when asked.

``EnvStore(dotenv: str | Path | None = None)`` with ``id = "env"``. ``get``
reads ``os.environ``; when ``dotenv`` is given and python-dotenv is installed,
values from that file fill in variables that are not set, never override them.
A missing variable raises ``SecretNotFound("env", name)``.

Depends on: types, python-dotenv (extra ``dotenv``, optional).
"""

from __future__ import annotations

import os
from pathlib import Path

from llmwarden.types import SecretNotFound


class EnvStore:
    id = "env"

    def __init__(self, dotenv: str | Path | None = None) -> None:
        self._file: dict[str, str] = {}
        if dotenv is not None:
            from dotenv import dotenv_values  # extra: dotenv

            self._file = {k: v for k, v in dotenv_values(dotenv).items() if v is not None}

    def get(self, name: str) -> str:
        value = os.environ.get(name)
        if value is None:
            value = self._file.get(name)
        if value is None:
            raise SecretNotFound(self.id, name)
        return value
