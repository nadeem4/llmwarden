"""``HashiCorpVault``: HashiCorp Vault KV through hvac.

``HashiCorpVault(url, token=None, *, mount="secret", client=None)`` with
``id = "vault"``. ``get(name)`` reads KV v2 at ``name`` and returns the data
object as a JSON string so ``field`` selection in ``secrets.base.resolve``
picks one key out of it. ``InvalidPath`` becomes ``SecretNotFound``.

Tests mock the hvac client. Install: ``llmwarden[vault]``.

Depends on: types, secrets.base, hvac.
"""
