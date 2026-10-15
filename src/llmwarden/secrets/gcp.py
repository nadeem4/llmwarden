"""``GcpSecretManager``: Google Secret Manager.

``GcpSecretManager(project, *, client=None)`` with ``id = "gcp"``. ``get(name)``
accepts ``name`` or ``name/versions/<v>`` (default ``latest``) and returns the
payload decoded as UTF-8. ``NotFound`` becomes ``SecretNotFound``.

Tests mock the SecretManagerServiceClient. Install: ``llmwarden[gcp]``.

Depends on: types, secrets.base, google-cloud-secret-manager.
"""
