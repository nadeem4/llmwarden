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

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable, Sequence
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from urllib.parse import urlsplit

import httpx

from llmwarden.types import EndpointRefused

type IP = IPv4Address | IPv6Address

DNS_TTL = 60.0

_METADATA = [
    ip_network(n) for n in ("169.254.169.254/32", "fd00:ec2::254/128", "100.100.100.200/32")
]
_cache: dict[str, tuple[list[IP], float]] = {}
_lock = threading.Lock()


def is_public(ip: IP) -> bool:
    """True when ``ip`` is a globally routable unicast address and not a metadata address."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False
    return not any(ip in net for net in _METADATA)


def resolve_host(host: str) -> list[str]:
    """Every address ``host`` resolves to, as strings, in a stable order."""
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return sorted({str(info[4][0]) for info in infos})


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def check_url(
    url: str,
    *,
    resolver: Callable[[str], list[str]] = resolve_host,
    now: Callable[[], float] = time.monotonic,
) -> list[IP]:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise EndpointRefused("custom endpoints must use https")
    if not parts.hostname:
        raise EndpointRefused("custom endpoint has no host")
    if parts.username or parts.password:
        raise EndpointRefused("custom endpoint must not carry credentials")
    if parts.query or parts.fragment:
        raise EndpointRefused("custom endpoint must not carry a query or fragment")
    host = parts.hostname
    try:
        literal: IP | None = ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        ips = [literal]
    else:
        with _lock:
            hit = _cache.get(host)
        if hit is not None and now() - hit[1] < DNS_TTL:
            ips = hit[0]
        else:
            ips = [ip_address(a) for a in resolver(host)]
            with _lock:
                _cache[host] = (ips, now())
    if not ips:
        raise EndpointRefused("custom endpoint host did not resolve")
    if not all(is_public(ip) for ip in ips):
        raise EndpointRefused("custom endpoint host resolves to a non-public address")
    return ips


class _PinnedTransport(httpx.HTTPTransport):
    """Connects to one checked address while the host name stays in TLS and ``Host``."""

    def __init__(self, host: str, address: IP, *, retries: int = 0) -> None:
        super().__init__(retries=retries)
        self._host = host
        self._address = address

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == self._host:
            request.headers["Host"] = self._host
            request.extensions["sni_hostname"] = self._host
            request.url = request.url.copy_with(host=str(self._address))
        return super().handle_request(request)


def guarded_client(url: str, addresses: Sequence[IP]) -> httpx.Client:
    host = urlsplit(url).hostname or ""
    transport = _PinnedTransport(host, addresses[0], retries=0)
    return httpx.Client(transport=transport, follow_redirects=False, trust_env=False)
