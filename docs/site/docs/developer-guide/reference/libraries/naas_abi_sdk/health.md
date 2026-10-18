# `HealthServer`

## What it is
- A small, **standard-library-only** asyncio HTTP server that exposes:
  - `GET /health` for **liveness**
  - `GET /ready` for **readiness**
- Designed to be embedded in a process and driven by a caller-provided `status()` function.

## Public API
### Class: `HealthServer`
- **Purpose:** Serve liveness and readiness endpoints over TCP.

#### `__init__(status: Callable[[], str], host: str, port: int)`
- `status`: callable returning a status string used by `/ready`.
- `host`: interface to bind to (e.g., `"127.0.0.1"`).
- `port`: port to bind to (use `0` for an ephemeral port).

#### `async start() -> None`
- Starts the server (`asyncio.start_server`) and logs the bind address.
- If `port=0`, updates `self.port` with the actual assigned port.

#### `async close() -> None`
- Gracefully closes the server if running.

## Configuration/Dependencies
- **Dependencies:** Python standard library only (`asyncio`, `logging`).
- **Readiness status mapping:**
  - `/ready` returns **200** only when `status()` returns `"READY"` or `"DISABLED"`.
  - Any other status string yields **503**.
- **Request limits/timeouts:**
  - Reads up to ~8192 bytes while searching for `\r\n\r\n`.
  - Per-request read is wrapped in a **2 second timeout**.

## Usage
```python
import asyncio
from naas_abi_sdk.health import HealthServer

def status():
    return "READY"

async def main():
    srv = HealthServer(status=status, host="127.0.0.1", port=0)
    await srv.start()
    print(f"listening on {srv.host}:{srv.port}")
    try:
        await asyncio.sleep(3600)
    finally:
        await srv.close()

asyncio.run(main())
```

## Caveats
- Only supports **HTTP GET**:
  - Non-`GET` requests return **405 Method Not Allowed**.
- Only two paths are handled:
  - `/health` → `200 OK` with body `ok`
  - `/ready` → `200 OK` or `503 Service Unavailable` with body set to the current status
  - Anything else → `404 Not Found`
- The readiness body is derived from `status()` but is constrained:
  - uses only the **first line**
  - **max 64 characters**
  - falls back to `UNAVAILABLE` on errors or empty output
