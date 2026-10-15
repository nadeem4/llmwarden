"""Tags through a ``ContextVar``.

- ``tags(**kv)``: a context manager that merges ``kv`` over the current tags
  for the block. Nested blocks stack; inner values win on a clash. Values are
  coerced to ``str``.
- ``current() -> Mapping[str, str]``: the tags in effect, read by ``model.py``
  and merged under the per-call ``tags=`` argument.

Tags propagate into asyncio tasks. They do not propagate into threads on
CPython before 3.14; callers use ``contextvars.copy_context().run``.

Depends on: nothing in the package.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType

_tags: ContextVar[Mapping[str, str]] = ContextVar("llmwarden_tags", default=MappingProxyType({}))


def current() -> Mapping[str, str]:
    return _tags.get()


@contextmanager
def tags(**kv: object) -> Iterator[None]:
    merged = dict(_tags.get())
    merged.update({k: str(v) for k, v in kv.items()})
    token = _tags.set(MappingProxyType(merged))
    try:
        yield
    finally:
        _tags.reset(token)
