"""Shared fixtures.

Planned fixtures, added as the modules they serve are built:

- ``fake_backend``: a ``FakeBackend`` with no scripted replies.
- ``memory``: the default ``MemorySink``, cleared before and after each test.
- ``no_network``: a respx router in ``assert_all_mocked`` mode, active for every
  test so an unmocked HTTP call fails the test.
- ``fake_clock``: a sleep replacement that records waits, for ``retry`` tests.
- ``secret_key``: a fixed fake key string and an assertion helper
  ``assert_absent(text)`` that checks the key is not in ``text`` without
  printing the key when it fails.
"""
