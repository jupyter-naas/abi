# outbound

## What it is
The one HTTP client for requests sent to URLs the platform was given: a URL from a user, a model, a fetched page or a stored setting. Every such request reaches public addresses only.

What the client keeps:
- Only `http` and `https`, on the first request and on every redirect.
- Each host name is resolved once, when its connection opens, and the lookup is waited for 10 s at most. Every address it resolves to must be public: loopback, private, link-local, shared (CGNAT), unspecified, multicast and reserved addresses are refused. An IPv6 address carrying an IPv4 one (mapped, 6to4, NAT64) is judged by that IPv4 address.
- The connection goes to the address that was checked. The `Host` header and the TLS server name stay the URL's own, so certificates are verified against the name.
- Local and internal names (`localhost`, `*.local`, `*.internal`, names without a dot, the cloud metadata names) are refused before any lookup.
- Redirects open new connections, so every hop is checked the same way.
- Proxy settings from the environment are ignored.
- `fetch` and `afetch` cap the body size, and one deadline (`timeout`) bounds the whole exchange: lookups, connections, headers, every redirect hop and the body. Past the deadline nothing more is sent: the sync client's connections and streams refuse every operation once it has passed. Async lookups wait in a thread pool of their own (16 threads), never the default one.

## Public API
- `fetch(url, *, headers=None, max_bytes=5 MB, timeout=15.0, max_redirects=5, allowed_origins=None) -> FetchedResponse`: GET with redirects followed and checked. Any status is returned.
- `afetch(...)`: the same, async.
- `FetchedResponse`: `url` (final URL), `status_code`, `headers`, `content` (at most `max_bytes`), `truncated`, `content_type`, `charset`, `text()`.
- `client(*, allowed_origins=None, **httpx_kwargs) -> httpx.Client` and `async_client(...) -> httpx.AsyncClient`: guarded httpx clients for other methods and streaming. They refuse `transport`, `mounts`, `proxy` and `trust_env`.
- `check_url(url, *, allowed_origins=None)`: URL, scheme and host checks, without a lookup.
- `parse_origins(entries) -> frozenset[(host, port)]` and `url_origin(url) -> (host, port)`.
- `resolve_public(host, port, *, allowed_origins=None, timeout=10.0) -> list[str]`: the checked addresses of a host (`allowed_origins` as parsed pairs).
- `address_refusal(address)` and `host_refusal(host)`: why an address or host is refused, or `None`.
- Errors: `OutboundRefused` (the URL or a destination is not allowed) is a subclass of `OutboundError` (every other failure: network, timeout, too many redirects). Their messages are fixed and name no address. `OutboundRefused.reason` is one of `INVALID_URL`, `SCHEME`, `NO_HOST`, `LOCAL_NAME`, `NOT_PUBLIC`, `UNRESOLVED`, `UNIX_SOCKET`.

## Configuration
- `allowed_origins`: origins a deployment trusts on its own network, such as a model server on the private network: `host:port`, a URL (`http://host:port`), or a bare host for its ports 80 and 443. A listed origin skips the address check and nothing else; it is still resolved once and connected to by address, and another port of the same host is checked like any other destination.

## Usage
```python
from naas_abi_core.utils import outbound

try:
    page = outbound.fetch("https://example.com/", max_bytes=200_000, timeout=15)
except outbound.OutboundRefused as exc:
    print("refused:", exc)
except outbound.OutboundError as exc:
    print("failed:", exc)
else:
    if page.status_code == 200 and not page.truncated:
        print(page.text()[:200])
```

```python
async with outbound.async_client(timeout=120.0, allowed_origins=["ollama:11434"]) as http:
    response = await http.post("http://ollama:11434/api/chat", json={...})
```
