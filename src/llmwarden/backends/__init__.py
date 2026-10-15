"""Backend adapters and the provider table.

- ``use(provider, backend)``: route a provider name to a backend instance for
  the process. ``default_for(provider) -> Backend``: the table lookup
  ``model.py`` uses, raising ``ProviderUnavailable`` when the backend's extra
  is not installed.
- Re-exports ``Backend``, ``Capabilities`` and ``FakeBackend``. The real
  adapters are imported lazily by name so importing this package never imports
  an SDK.

Depends on: types, backends.base, backends.fake.
"""
