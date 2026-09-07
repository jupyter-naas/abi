"""
Shared async httpx client.

A single AsyncClient is created at startup (lifespan) and shared across
all adapters. This reuses the underlying connection pool rather than opening
a new TCP connection on every request — critical for high-frequency endpoints
like flights (every 30 s) and theater aircraft (every 45 s).
"""

import httpx

_client: httpx.AsyncClient | None = None

DEFAULT_HEADERS = {
    "User-Agent": "WSR/1.0",
    "Accept": "application/json",
}

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=12.0, write=5.0, pool=5.0)


async def init_client() -> None:
    global _client
    _client = httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
    )


async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized — call init_client() first")
    return _client
