"""The core types every other module speaks. Standard library only.

Frozen dataclasses:

- ``Message(role, content)`` with ``role`` in ``system``, ``user``, ``assistant``.
- ``ChatRequest(model_id, messages, params, schema)``. ``params`` is a read-only
  mapping handed to the backend after llmwarden removes the keys it owns
  (``schema``, ``tools``). ``schema`` is the caller's Pydantic class or ``None``.
- ``Usage(input_tokens, output_tokens, source)``; a count the provider did not
  send is ``None``, never ``0``. ``source`` is ``reported`` or ``estimated``.
- ``Price(input_per_million, output_per_million)`` in US dollars.
- ``Cost(usd, source)`` with ``source`` in ``model``, ``backend``, ``llmwarden``.
- ``ChatReply(text, parsed, usage, cost, model, provider, stop_reason, call_id,
  attempts, raw)``. A backend returns it with ``parsed=None`` and ``cost=None``;
  ``model.py`` fills both. ``raw`` is the backend's response object and is
  never recorded.

``ErrorKind`` enum: ``auth``, ``permission``, ``not_found``, ``rate_limit``,
``timeout``, ``connection``, ``server``, ``bad_request``, ``invalid_output``,
``cancelled``, ``unknown``. Retries and records read only this.

Exceptions:

- ``ProviderError(kind, status, provider, message)``: the scrubbed error raised
  to the caller after retries run out. ``message`` never contains a key.
- ``InvalidOutput(ProviderError)``: ``kind`` is ``invalid_output``; ``text``
  holds the last raw reply.
- ``NotSupported``, ``ProviderUnavailable``, ``EndpointRefused``,
  ``SecretNotFound(store, name)``: plain exceptions, each raised at model
  creation or call time as the architecture describes.

Depends on: nothing in the package.
"""
