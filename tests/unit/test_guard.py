import ipaddress

import httpx
import pytest

from llmwarden.guard import DNS_TTL, check_url, clear_cache, guarded_client, is_public
from llmwarden.types import EndpointRefused


@pytest.fixture(autouse=True)
def _clean():
    clear_cache()
    yield
    clear_cache()


def fake_resolver(mapping):
    calls = []

    def resolve(host):
        calls.append(host)
        return mapping[host]

    resolve.calls = calls
    return resolve


@pytest.mark.parametrize(
    "ip,ok",
    [
        ("93.184.216.34", True),
        ("2606:2800:220:1:248:1893:25c8:1946", True),
        ("10.0.0.1", False),
        ("172.16.5.5", False),
        ("192.168.1.1", False),
        ("127.0.0.1", False),
        ("::1", False),
        ("169.254.169.254", False),
        ("169.254.1.1", False),
        ("fd00:ec2::254", False),
        ("100.100.100.200", False),
        ("0.0.0.0", False),  # noqa: S104 - the unspecified address must be refused
        ("224.0.0.1", False),
        ("240.0.0.1", False),
        ("fe80::1", False),
        ("fc00::1", False),
    ],
)
def test_is_public(ip, ok):
    assert is_public(ipaddress.ip_address(ip)) is ok


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/v1",
        "https://user:pw@api.example.com/v1",
        "https://api.example.com/v1?x=1",
        "https://api.example.com/v1#frag",
        "https:///v1",
        "ftp://api.example.com",
    ],
)
def test_url_rules(url):
    with pytest.raises(EndpointRefused):
        check_url(url, resolver=fake_resolver({"api.example.com": ["93.184.216.34"]}))


def test_public_host_passes_and_returns_addresses():
    ips = check_url(
        "https://api.example.com/v1",
        resolver=fake_resolver({"api.example.com": ["93.184.216.34"]}),
    )
    assert ips == [ipaddress.ip_address("93.184.216.34")]


def test_mixed_public_and_private_is_refused():
    with pytest.raises(EndpointRefused):
        check_url(
            "https://evil.example.com/v1",
            resolver=fake_resolver({"evil.example.com": ["93.184.216.34", "10.0.0.5"]}),
        )


def test_host_that_resolves_to_nothing_is_refused():
    with pytest.raises(EndpointRefused):
        check_url("https://gone.example.com/v1", resolver=fake_resolver({"gone.example.com": []}))


def test_literal_ip_hosts_are_checked_without_dns():
    r = fake_resolver({})
    with pytest.raises(EndpointRefused):
        check_url("https://169.254.169.254/latest", resolver=r)
    assert r.calls == []


def test_dns_cache_ttl():
    r = fake_resolver({"api.example.com": ["93.184.216.34"]})
    clock = [0.0]
    check_url("https://api.example.com/v1", resolver=r, now=lambda: clock[0])
    check_url("https://api.example.com/v1", resolver=r, now=lambda: clock[0])
    assert r.calls == ["api.example.com"]
    clock[0] = DNS_TTL + 1.0
    check_url("https://api.example.com/v1", resolver=r, now=lambda: clock[0])
    assert r.calls == ["api.example.com", "api.example.com"]


def test_guarded_client_settings_and_pinned_transport(monkeypatch):
    seen = {}

    def fake_handle_request(self, request):
        seen["url"] = str(request.url)
        seen["host_header"] = request.headers["host"]
        seen["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fake_handle_request)
    ips = [ipaddress.ip_address("93.184.216.34")]
    with guarded_client("https://api.example.com/v1", ips) as client:
        assert client.follow_redirects is False
        assert client.trust_env is False
        resp = client.get("https://api.example.com/v1/models")
    assert resp.status_code == 200
    assert seen["url"].startswith("https://93.184.216.34/")
    assert seen["host_header"] == "api.example.com"
    assert seen["sni"] == "api.example.com"


def test_guarded_client_pins_ipv6_address(monkeypatch):
    seen = {}

    def fake_handle_request(self, request):
        seen["host"] = request.url.host
        return httpx.Response(200)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fake_handle_request)
    ips = [ipaddress.ip_address("2606:2800:220:1:248:1893:25c8:1946")]
    with guarded_client("https://api.example.com/v1", ips) as client:
        client.get("https://api.example.com/v1/models")
    assert seen["host"] == "2606:2800:220:1:248:1893:25c8:1946"


def test_guarded_client_can_be_built_from_httpx2(monkeypatch):
    httpx2 = pytest.importorskip("httpx2")
    seen = {}

    def fake_handle_request(self, request):
        seen["url"] = str(request.url)
        seen["host"] = request.headers["host"]
        seen["sni"] = request.extensions.get("sni_hostname")
        return httpx2.Response(200)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", fake_handle_request)
    ips = [ipaddress.ip_address("93.184.216.34")]
    with guarded_client("https://api.example.com/v1", ips, lib="httpx2") as client:
        assert isinstance(client, httpx2.Client)
        assert client.follow_redirects is False and client.trust_env is False
        assert client.get("https://api.example.com/v1/models").status_code == 200
    assert seen["url"].startswith("https://93.184.216.34/")
    assert seen["host"] == "api.example.com" and seen["sni"] == "api.example.com"


def test_capabilities_default_http_lib_is_httpx():
    from llmwarden.backends.anthropic import AnthropicBackend
    from llmwarden.backends.base import Capabilities
    from llmwarden.backends.openai import OpenAIBackend

    assert Capabilities(frozenset(), True, False, True).http_lib == "httpx"
    assert OpenAIBackend.capabilities.http_lib == "httpx2"
    assert AnthropicBackend.capabilities.http_lib == "httpx2"
