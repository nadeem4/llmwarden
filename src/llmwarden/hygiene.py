"""Key hygiene: no key in any error, log line or repr.

- ``scrub(text, secrets) -> str``: replace every secret in ``secrets`` with
  ``[redacted]``. Also matches each secret URL-encoded and base64-encoded, since
  SDK messages can embed headers either way.
- ``mask(key) -> str``: the first three and last four characters, or ``***``
  when the key is shorter than twelve.
- ``ScrubFilter(secrets)``: a ``logging.Filter`` that scrubs ``record.msg`` and
  ``record.args``. Applications add it to any logger.
- ``reraise(error, kind, secrets, provider, status) -> NoReturn``: build a
  ``ProviderError`` (or ``InvalidOutput`` when ``kind`` is ``invalid_output``)
  from the scrubbed message and raise it ``from None``. The original is dropped
  because SDK errors hold the request, and the request holds the key.

Depends on: types.
"""
