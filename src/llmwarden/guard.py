"""Endpoint guard: refuse custom base URLs that could reach a private address.

- ``check_url(url) -> list[ipaddress.IPv4Address | IPv6Address]``: the scheme
  must be ``https``; no user info, query or fragment; every resolved address
  must be public. Refused: private, loopback, link-local, multicast, reserved,
  unspecified, and the cloud metadata addresses ``169.254.169.254``,
  ``fd00:ec2::254`` and ``100.100.100.200``. Raises ``EndpointRefused`` with a
  message that names the rule that failed.
- ``guarded_client(url, addresses) -> httpx.Client``: redirects off,
  ``trust_env=False``, and a transport that connects to one checked address
  while keeping the host name for TLS and the ``Host`` header.
- A DNS cache keyed by host with a 60 second TTL, so the check does not resolve
  on every call. ``model.py`` re-checks when the entry has expired.

With ``public_only`` false nothing here runs, so ``localhost`` servers work.

Depends on: types (``EndpointRefused``), httpx, ipaddress, socket.
"""
