"""``model()`` and ``Model``: one call orchestrated in a fixed order.

``model(name, *, api_key=None, base_url=None, public_only=False, params=None,
price=None, retry=None, fallback=None, backend=None) -> Model``:

1. Split ``name`` into ``provider`` and ``model_id``. Pick the backend from the
   provider table (``openai``, ``openai_compatible``, ``openrouter`` ->
   ``OpenAIBackend``; ``anthropic`` -> ``AnthropicBackend``; anything else ->
   ``LiteLLMBackend`` when installed, else raise ``ProviderUnavailable`` naming
   the extra). ``backend=`` overrides. ``backends.use(provider, backend)``
   edits the table for the process.
2. Resolve the key: a string as is; a callable by calling it; a ``SecretRef``
   through ``secrets.resolve``; ``None`` through ``env`` with the provider's
   standard variable. ``openai_compatible`` with no key gets a placeholder so
   the SDK never reads an environment key.
3. When ``base_url`` is set and ``public_only`` is true, run ``guard.check_url``
   and build the guarded client. Raise ``EndpointRefused`` if the backend's
   ``capabilities.http_client`` is false.
4. Build the adapter client. Models are not cached; the HTTP client is shared
   per backend and guard setting, so this is cheap.

``Model.complete(*, messages=None, system=None, user=None, schema=None,
params=None, tags=None) -> ChatReply``:

- ``system`` and ``user`` build a two-message list; giving both forms raises
  ``ValueError``. ``tools`` in ``params`` raises ``NotSupported``.
- When the backend lacks ``capabilities.schema`` and ``schema`` is set, append
  ``schema.prompt_for(schema)`` to the last system message.
- Run ``retry.run`` with one attempt function that calls the backend, maps and
  scrubs any exception through ``hygiene.reraise``, parses with
  ``schema.parse``, prices with ``prices.cost`` in the order model price,
  backend price, llmwarden table, and emits one ``AttemptRecord`` per attempt
  with ``observe.tags.current()`` merged under the per-call tags.
- On an ``auth`` error with a key from a store or callable, resolve the key
  again, rebuild the client and make one extra attempt, once per call, not
  counted against ``Retry.attempts``.
- When attempts run out and ``fallback`` is set, call ``fallback.complete``
  with the same arguments and the same ``call_id``.

``Model.refresh()`` resolves the key again and rebuilds the client.
``repr(Model)`` masks a string key and shows a ``SecretRef`` as store and name.

Depends on: types, backends.base, secrets.base, guard, hygiene, retry, schema,
prices, observe.records, observe.tags.
"""
