"""The ``SecretStore`` protocol, ``SecretRef``, the registry and ``resolve``.

- ``SecretStore`` (Protocol): ``id: str`` and ``get(name) -> str``. Raise
  ``SecretNotFound(store, name)`` for a missing secret; let SDK errors through.
- ``SecretRef(store, name, field=None, ttl=None)`` (frozen): ``store`` is a
  store id or a ``SecretStore`` instance. ``repr`` shows store and name only.
- ``secret(store, name, field=None, ttl=None) -> SecretRef``: the public
  constructor exported as ``lw.secret``.
- Registry: ``use(store)`` adds or replaces a store by its ``id``; ``env`` is
  registered at import. ``store_for(ref) -> SecretStore``.
- ``resolve(ref) -> str``: fetch through the store, pick ``field`` out of a
  JSON object when set, cache by ``(store id, name, field)`` until ``ttl``
  passes or ``invalidate(ref)`` is called. Concurrent first fetches of one
  reference share one store call (a per-key lock). The cache is a dict in
  memory and is never written, logged or put in an error.

Depends on: types.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from llmwarden.types import SecretNotFound


@runtime_checkable
class SecretStore(Protocol):
    id: str

    def get(self, name: str) -> str: ...


@dataclass(frozen=True)
class SecretRef:
    store: str | SecretStore
    name: str
    field: str | None = None
    ttl: float | None = None

    @property
    def store_id(self) -> str:
        return self.store if isinstance(self.store, str) else self.store.id

    def __repr__(self) -> str:
        return f"SecretRef(store={self.store_id!r}, name={self.name!r})"


def secret(
    store: str | SecretStore, name: str, field: str | None = None, ttl: float | None = None
) -> SecretRef:
    return SecretRef(store, name, field, ttl)


type _Key = tuple[str, str, str | None]

_stores: dict[str, SecretStore] = {}
_cache: dict[_Key, tuple[str, float]] = {}
_locks: dict[_Key, threading.Lock] = {}
_registry_lock = threading.Lock()


def use(store: SecretStore) -> None:
    with _registry_lock:
        _stores[store.id] = store


def store_for(ref: SecretRef) -> SecretStore:
    if not isinstance(ref.store, str):
        return ref.store
    with _registry_lock:
        return _stores[ref.store]


def _key(ref: SecretRef) -> _Key:
    return (ref.store_id, ref.name, ref.field)


def _lock_for(key: _Key) -> threading.Lock:
    with _registry_lock:
        return _locks.setdefault(key, threading.Lock())


def _pick(ref: SecretRef, raw: str) -> str:
    if ref.field is None:
        return raw
    try:
        data = json.loads(raw)
    except ValueError:
        raise SecretNotFound(ref.store_id, f"{ref.name}#{ref.field}") from None
    if not isinstance(data, dict) or ref.field not in data:
        raise SecretNotFound(ref.store_id, f"{ref.name}#{ref.field}")
    return str(data[ref.field])


def resolve(ref: SecretRef, *, now: Callable[[], float] = time.monotonic) -> str:
    key = _key(ref)
    with _lock_for(key):
        hit = _cache.get(key)
        if hit is not None:
            value, fetched = hit
            if ref.ttl is None or now() - fetched < ref.ttl:
                return value
        value = _pick(ref, store_for(ref).get(ref.name))
        _cache[key] = (value, now())
        return value


def invalidate(ref: SecretRef) -> None:
    with _registry_lock:
        _cache.pop(_key(ref), None)


def clear() -> None:
    """Drop every cached value and every store but env. For tests."""
    with _registry_lock:
        _cache.clear()
        _locks.clear()
        for sid in [s for s in _stores if s != "env"]:
            del _stores[sid]


from llmwarden.secrets.env import EnvStore  # noqa: E402  registered at import

use(EnvStore())
