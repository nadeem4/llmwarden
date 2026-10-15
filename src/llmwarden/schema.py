"""Structured output: ask for a shape, always validate the reply ourselves.

- ``prompt_for(schema) -> str``: a short instruction plus the JSON schema from
  ``schema.model_json_schema()``, appended to the last system message when the
  backend cannot send a schema natively.
- ``parse(text, schema) -> BaseModel``: ``schema.model_validate_json`` after
  stripping a surrounding Markdown code fence if the model added one. Raises
  ``InvalidOutput`` carrying ``text`` on any validation error.

This is the only core module that imports pydantic.

Depends on: types, pydantic.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from llmwarden.types import InvalidOutput

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


def prompt_for(schema: type[BaseModel]) -> str:
    body = json.dumps(schema.model_json_schema(), indent=None)
    return (
        "Reply with a single JSON object and nothing else, no prose and no code fence. "
        f"It must match this JSON schema exactly: {body}"
    )


def _unfence(text: str) -> str:
    m = _FENCE.match(text)
    return m.group(1) if m else text


def parse[T: BaseModel](text: str, schema: type[T], *, provider: str) -> T:
    try:
        return schema.model_validate_json(_unfence(text))
    except (ValidationError, ValueError) as e:
        raise InvalidOutput(
            f"reply did not match {schema.__name__}: {e.__class__.__name__}",
            text=text,
            provider=provider,
        ) from None
