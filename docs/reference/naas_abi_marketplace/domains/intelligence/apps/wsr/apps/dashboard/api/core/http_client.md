# http_client

## What it is
- A shared, module-level `httpx.AsyncClient` intended to be initialized once at app startup and reused across adapters.
- Reuses the underlying connection pool instead of opening new TCP connections per request.

## Public API
- `DEFAULT_HEADERS: dict`
  - Default headers applied to the shared client.
- `DEFAULT_TIMEOUT: httpx.Timeout`
  - Default connect/read/write/pool timeouts for the shared client.
- `async init_client() -> None`
  - Creates and stores the shared `httpx.AsyncClient` with:
    - `headers=DEFAULT_HEADERS`
    - `timeout=DEFAULT_TIMEOUT`
    - `follow_redirects=True`
    - `limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)`
- `async close_client() -> None`
  - Closes the shared client (if initialized) and resets it to `None`.
- `get_client() -> httpx.AsyncClient`
  - Returns the initialized shared client.
  - Raises `RuntimeError` if the client has not been initialized.

## Configuration/Dependencies
- Dependency: `httpx`
- Defaults:
  - `DEFAULT_HEADERS = {"User-Agent": "WSR/1.0", "Accept": "application/json"}`
  - `DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=12.0, write=5.0, pool=5.0)`
  - Connection limits: `max_connections=50`, `max_keepalive_connections=20`
  - Redirects: `follow_redirects=True`

## Usage
```python
import asyncio

from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.core.http_client import (
    init_client,
    close_client,
    get_client,
)

async def main():
    await init_client()
    try:
        client = get_client()
        resp = await client.get("https://httpbin.org/json")
        print(resp.status_code)
    finally:
        await close_client()

asyncio.run(main())
```

## Caveats
- `get_client()` raises `RuntimeError` until `init_client()` has been awaited.
- Always `await close_client()` to properly close connections and release resources.
