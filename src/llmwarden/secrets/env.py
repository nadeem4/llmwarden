"""``EnvStore``: environment variables, and ``.env`` files when asked.

``EnvStore(dotenv: str | Path | None = None)`` with ``id = "env"``. ``get``
reads ``os.environ``; when ``dotenv`` is given and python-dotenv is installed,
values from that file fill in variables that are not set, never override them.
A missing variable raises ``SecretNotFound("env", name)``.

Depends on: types, python-dotenv (extra ``dotenv``, optional).
"""
