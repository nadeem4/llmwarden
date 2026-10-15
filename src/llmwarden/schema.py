"""Structured output: ask for a shape, always validate the reply ourselves.

- ``prompt_for(schema) -> str``: a short instruction plus the JSON schema from
  ``schema.model_json_schema()``, appended to the last system message when the
  backend cannot send a schema natively.
- ``parse(text, schema) -> BaseModel``: ``schema.model_validate_json`` after
  stripping a surrounding Markdown code fence if the model added one. Raises
  ``InvalidOutput`` carrying ``text`` on any validation error.

This is the only core module that imports pydantic.

Depends on: types, pydantic.
"""
