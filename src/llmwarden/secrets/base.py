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
