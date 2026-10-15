"""``AzureKeyVault``: Azure Key Vault through azure-keyvault-secrets.

``AzureKeyVault(vault_url, *, credential=None)`` with ``id = "azure"``. A
missing credential uses ``DefaultAzureCredential``. ``get(name)`` returns
``client.get_secret(name).value``. ``ResourceNotFoundError`` becomes
``SecretNotFound``.

Tests mock the SecretClient. Install: ``llmwarden[azure]``.

Depends on: types, secrets.base, azure-identity, azure-keyvault-secrets.
"""
