"""``AzureKeyVault``: Azure Key Vault through azure-keyvault-secrets.

``AzureKeyVault(vault_url, *, credential=None, client=None)`` with
``id = "azure"``. ``get(name)`` returns ``client.get_secret(name).value``.
``ResourceNotFoundError`` becomes ``SecretNotFound``, as does a secret whose
value is ``None``.

``client`` is an already built ``SecretClient``; when it is ``None`` one is
built lazily on the first ``get`` from ``vault_url`` and ``credential`` (or
``DefaultAzureCredential`` when that is ``None``). The Azure SDKs are imported
only then, never at module import.

Tests mock the SecretClient. Install: ``llmwarden[azure]``.

Depends on: types, secrets.base, azure-identity, azure-keyvault-secrets.
"""

from __future__ import annotations

from typing import Any

from llmwarden.types import SecretNotFound


class AzureKeyVault:
    id = "azure"

    def __init__(
        self, vault_url: str, *, credential: Any | None = None, client: Any | None = None
    ) -> None:
        self._url = vault_url
        self._credential = credential
        self._client = client

    def _c(self) -> Any:
        if self._client is None:
            from azure.identity import DefaultAzureCredential  # extra: azure
            from azure.keyvault.secrets import SecretClient

            self._client = SecretClient(
                vault_url=self._url, credential=self._credential or DefaultAzureCredential()
            )
        return self._client

    def get(self, name: str) -> str:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            value = self._c().get_secret(name).value
        except ResourceNotFoundError:
            raise SecretNotFound(self.id, name) from None
        if value is None:
            raise SecretNotFound(self.id, name)
        return str(value)
