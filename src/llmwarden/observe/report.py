"""``report``: add up the memory sink by tag.

``report(group_by: list[str], since: datetime | None = None) -> list[Row]``.
``Row`` (frozen): the group's tag values, ``calls`` (distinct ``call_id``),
``attempts``, ``failures: dict[ErrorKind, int]``, ``input_tokens``,
``output_tokens``, ``cost_usd``, ``wasted_usd`` (cost of failed attempts that
used tokens), ``unknown_cost_attempts``, ``seconds``. A record missing a
group-by tag falls into a group with that value ``None``.

Depends on: observe.memory, types.
"""
