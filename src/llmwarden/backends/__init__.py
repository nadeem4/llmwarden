"""Backend adapters and the provider table.

- ``use(provider, backend)``: route a provider name to a backend instance for
  the process. ``default_for(provider) -> Backend``: the table lookup
  ``model.py`` uses, raising ``ProviderUnavailable`` when the backend's extra
  is not installed. ``reset()`` clears overrides and cached instances; tests
  call it.
- Re-exports ``Backend``, ``Capabilities`` and ``FakeBackend``. The real
  adapters are imported lazily by name so importing this package never imports
  an SDK.

Depends on: types, backends.base, backends.fake.
"""

from __future__ import annotations

import importlib

from llmwarden.backends.base import Backend, Capabilities
from llmwarden.backends.fake import FakeBackend
from llmwarden.types import ProviderUnavailable

__all__ = ["Backend", "Capabilities", "FakeBackend", "default_for", "reset", "use"]

_NATIVE: dict[str, tuple[str, str, str]] = {
    "openai": ("llmwarden.backends.openai", "OpenAIBackend", "openai"),
    "openai_compatible": ("llmwarden.backends.openai", "OpenAIBackend", "openai"),
    "openrouter": ("llmwarden.backends.openai", "OpenAIBackend", "openai"),
    "anthropic": ("llmwarden.backends.anthropic", "AnthropicBackend", "anthropic"),
}
_LITELLM = ("llmwarden.backends.litellm", "LiteLLMBackend", "litellm")

_overrides: dict[str, Backend] = {}
_instances: dict[str, Backend] = {}


def use(provider: str, backend: Backend) -> None:
    _overrides[provider] = backend


def reset() -> None:
    _overrides.clear()
    _instances.clear()


def _load(module: str, cls: str, extra: str) -> Backend:
    key = f"{module}.{cls}"
    if key not in _instances:
        try:
            mod = importlib.import_module(module)
        except ImportError as e:
            raise ProviderUnavailable(
                f"backend {cls} needs the '{extra}' extra: pip install \"llmwarden[{extra}]\""
            ) from e
        instance: Backend = getattr(mod, cls)()
        _instances[key] = instance
    return _instances[key]


def default_for(provider: str) -> Backend:
    if provider in _overrides:
        return _overrides[provider]
    if provider in _NATIVE:
        return _load(*_NATIVE[provider])
    return _load(*_LITELLM)
