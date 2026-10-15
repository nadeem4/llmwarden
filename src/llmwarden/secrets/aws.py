"""``AwsSecrets``: AWS Secrets Manager through boto3.

``AwsSecrets(region, *, session=None, client=None)`` with ``id = "aws"``.
``get(name)`` calls ``get_secret_value(SecretId=name)`` and returns
``SecretString``. ``ResourceNotFoundException`` becomes ``SecretNotFound``, as
does a secret that has no ``SecretString`` (binary only). JSON field selection
is done by ``secrets.base.resolve``, not here.

``client`` is an already built Secrets Manager client; when it is ``None`` one
is built lazily from ``session`` (or a fresh ``boto3.session.Session()``) on
the first ``get``. boto3 is imported only then, never at module import.

Tests mock the boto3 client. Install: ``llmwarden[aws]``.

Depends on: types, secrets.base, boto3.
"""

from __future__ import annotations

from typing import Any

from llmwarden.types import SecretNotFound


class AwsSecrets:
    id = "aws"

    def __init__(
        self, region: str, *, session: Any | None = None, client: Any | None = None
    ) -> None:
        self._region = region
        self._session = session
        self._client = client

    def _c(self) -> Any:
        if self._client is None:
            import boto3  # type: ignore[import-untyped]  # extra: aws

            session = self._session or boto3.session.Session()
            self._client = session.client("secretsmanager", region_name=self._region)
        return self._client

    def get(self, name: str) -> str:
        c = self._c()
        try:
            out = c.get_secret_value(SecretId=name)
        except c.exceptions.ResourceNotFoundException:
            raise SecretNotFound(self.id, name) from None
        value = out.get("SecretString")
        if value is None:
            raise SecretNotFound(self.id, name)
        return str(value)
