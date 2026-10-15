"""The contract suite: one scenario set, every backend.

Each backend gets a module here (``test_fake.py``, ``test_openai.py``,
``test_anthropic.py``, ``test_litellm.py``) that provides two fixtures,
``backend`` and ``script(scenario)``, and imports the shared scenario tests
from ``scenarios.py``. For ``FakeBackend`` the script sets replies; for the SDK
backends it registers respx routes that return the same sequence as HTTP.

Scenarios in ``scenarios.py``:

1. success with usage reported
2. success with no usage; tokens are ``None`` and cost is ``None``
3. rate limit, then success; two records, ``attempts == 2``
4. auth error with a store key, then success after the re-fetch; the store's
   ``get`` was called twice; one extra attempt not counted against the policy
5. auth error with a string key; raised at once, no re-fetch
6. server error until attempts run out; ``ProviderError(kind=server)``,
   ``attempts`` records
7. invalid output, then valid; ``parsed`` is the schema instance
8. custom base URL under ``public_only`` is refused for a backend without
   ``http_client``, and accepted with a guarded client for one with it
9. the key appears in no exception message, no record and no ``repr``

A new adapter is done when its module here passes.
"""
