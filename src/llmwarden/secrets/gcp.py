"""``GcpSecretManager``: Google Secret Manager.

``GcpSecretManager(project, *, client=None)`` with ``id = "gcp"``. ``get(name)``
accepts ``name`` or ``name/versions/<v>`` (default ``latest``), reads
``projects/<project>/secrets/<name>/versions/<v>`` and returns the payload
decoded as UTF-8. ``NotFound`` becomes ``SecretNotFound``.

``client`` is an already built ``SecretManagerServiceClient``; when it is
``None`` one is built lazily on the first ``get``. The Google SDK is imported
only then, never at module import.

Tests mock the SecretManagerServiceClient. Install: ``llmwarden[gcp]``.

Depends on: types, secrets.base, google-cloud-secret-manager.
"""

from __future__ import annotations

from typing import Any

from llmwarden.types import SecretNotFound


class GcpSecretManager:
    id = "gcp"

    def __init__(self, project: str, *, client: Any | None = None) -> None:
        self._project = project
        self._client = client

    def _c(self) -> Any:
        if self._client is None:
            from google.cloud import secretmanager  # extra: gcp

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def get(self, name: str) -> str:
        from google.api_core.exceptions import NotFound

        versioned = name if "/versions/" in name else f"{name}/versions/latest"
        path = f"projects/{self._project}/secrets/{versioned}"
        try:
            out = self._c().access_secret_version(request={"name": path})
        except NotFound:
            raise SecretNotFound(self.id, name) from None
        return bytes(out.payload.data).decode("utf-8")
