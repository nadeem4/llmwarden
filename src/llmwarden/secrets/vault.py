"""``HashiCorpVault``: HashiCorp Vault KV through hvac.

``HashiCorpVault(url, token=None, *, mount="secret", client=None)`` with
``id = "vault"``. ``get(name)`` reads KV v2 at ``name`` under ``mount`` and
returns the data object as a JSON string so ``field`` selection in
``secrets.base.resolve`` picks one key out of it. ``InvalidPath`` becomes
``SecretNotFound``.

``client`` is an already built ``hvac.Client``; when it is ``None`` one is
built lazily on the first ``get`` from ``url`` and ``token``. hvac is imported
only then, never at module import.

Tests mock the hvac client. Install: ``llmwarden[vault]``.

Depends on: types, secrets.base, hvac.
"""

from __future__ import annotations

import json
from typing import Any

from llmwarden.types import SecretNotFound


class HashiCorpVault:
    id = "vault"

    def __init__(
        self,
        url: str,
        token: str | None = None,
        *,
        mount: str = "secret",
        client: Any | None = None,
    ) -> None:
        self._url = url
        self._token = token
        self._mount = mount
        self._client = client

    def _c(self) -> Any:
        if self._client is None:
            import hvac  # type: ignore[import-untyped]  # extra: vault

            self._client = hvac.Client(url=self._url, token=self._token)
        return self._client

    def get(self, name: str) -> str:
        from hvac.exceptions import InvalidPath  # type: ignore[import-untyped]

        try:
            out = self._c().secrets.kv.v2.read_secret_version(
                path=name, mount_point=self._mount, raise_on_deleted_version=True
            )
        except InvalidPath:
            raise SecretNotFound(self.id, name) from None
        return json.dumps(out["data"]["data"])
