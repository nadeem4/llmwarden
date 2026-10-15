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
