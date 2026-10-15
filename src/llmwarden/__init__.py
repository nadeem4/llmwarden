"""llmwarden: call any model with any key, fetched safely, and see where the money goes.

Public API, re-exported here and nowhere else:

- ``model(name, *, api_key, base_url, public_only, params, price, retry, fallback, backend)``
  and the ``Model`` class, from ``model.py``.
- ``secret(store, name, field=None, ttl=None)`` and the ``secrets`` registry
  (``secrets.use(store)``), from ``secrets/base.py``. ``stores`` exposes the
  store classes (``EnvStore``, ``AwsSecrets``, ``AzureKeyVault``,
  ``GcpSecretManager``, ``HashiCorpVault``); the cloud ones import lazily so a
  missing extra is reported only when used.
- ``tags(**kv)`` from ``observe/tags.py``; ``report(group_by, since)`` from
  ``observe/report.py``; ``observe`` for ``observe.add(sink)`` and
  ``observe.remove(sink)``.
- ``backends`` for ``backends.use(provider, backend)`` and the adapter classes.
- ``Retry``, ``Price``, ``Message``, ``ChatReply``, ``Usage``, ``Cost``,
  ``ErrorKind``, ``AttemptRecord`` and the exceptions from ``types.py``.

Importing this package must not import any backend SDK, any secret store SDK
or opentelemetry. Those load inside the module that uses them.

Build order and the full design: ``docs/architecture.md``.
"""

__version__ = "0.1.0.dev0"
