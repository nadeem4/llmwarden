"""``AttemptRecord`` and the sink registry.

``AttemptRecord`` (frozen): ``id``, ``call_id``, ``model``, ``provider``,
``attempt``, ``outcome`` (``ok``, ``provider_error``, ``invalid_output``),
``error_kind``, ``input_tokens``, ``output_tokens``, ``usage_source``,
``cost_usd``, ``price_source``, ``started``, ``seconds``, ``tags``. No prompt,
no reply, no key, ever.

- ``add(sink)`` and ``remove(sink)``: a sink is any callable taking one record.
- ``emit(record)``: call every sink. A sink that raises is logged once through
  the ``llmwarden`` logger and skipped afterwards, so one broken sink never
  breaks a call.

Depends on: types.
"""
