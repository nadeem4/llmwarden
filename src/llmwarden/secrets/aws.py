"""``AwsSecrets``: AWS Secrets Manager through boto3.

``AwsSecrets(region, *, session=None)`` with ``id = "aws"``. ``get(name)``
calls ``get_secret_value(SecretId=name)`` and returns ``SecretString``.
``ResourceNotFoundException`` becomes ``SecretNotFound``. JSON field selection
is done by ``secrets.base.resolve``, not here.

Tests mock the boto3 client. Install: ``llmwarden[aws]``.

Depends on: types, secrets.base, boto3.
"""
