"""Store classes by name, imported lazily so a missing extra is reported only when used.

``lw.stores.EnvStore``, ``lw.stores.AwsSecrets``, ``lw.stores.AzureKeyVault``,
``lw.stores.GcpSecretManager`` and ``lw.stores.HashiCorpVault`` resolve on first
access. Importing this module imports no SDK.

Depends on: secrets.env, secrets.aws, secrets.azure, secrets.gcp, secrets.vault (lazily).
"""

from __future__ import annotations

import importlib
from typing import Any

_WHERE: dict[str, str] = {
    "EnvStore": "llmwarden.secrets.env",
    "AwsSecrets": "llmwarden.secrets.aws",
    "AzureKeyVault": "llmwarden.secrets.azure",
    "GcpSecretManager": "llmwarden.secrets.gcp",
    "HashiCorpVault": "llmwarden.secrets.vault",
}

__all__ = list(_WHERE)


def __getattr__(name: str) -> Any:
    if name in _WHERE:
        return getattr(importlib.import_module(_WHERE[name]), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(__all__)
