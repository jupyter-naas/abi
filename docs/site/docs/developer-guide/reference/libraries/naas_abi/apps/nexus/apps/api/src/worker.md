# `worker.py` (Cloudflare Workers entry point)

## What it is
- An entry point that adapts a FastAPI ASGI app (`app.main.app`) to run on Cloudflare Workers using the Workers Python runtime and an ASGI adapter.

## Public API
- `class Default(WorkerEntrypoint)`
  - `async fetch(self, request)`
    - Handles incoming Cloudflare Worker `request` objects.
    - Delegates request handling to the FastAPI app via `asgi.fetch(app, request, self.env)`.
- `def on_fetch(request, env, ctx)`
  - Synchronous wrapper entry point intended for local development with `wrangler dev`.
  - Instantiates `Default`, sets `env` and `ctx`, and runs `fetch()` on the current asyncio event loop.

## Configuration/Dependencies
- Dependencies:
  - `asgi` (provides `asgi.fetch(...)` adapter)
  - `workers.WorkerEntrypoint` (Cloudflare Workers Python runtime base class)
  - `app.main.app` (the FastAPI application to serve)
- Environment/context:
  - `self.env` is passed to `asgi.fetch(...)` and is expected to contain Cloudflare environment bindings.
  - `ctx` is set on the worker in `on_fetch` but not otherwise used in this module.

## Usage
Minimal example calling the local development entry point (illustrative; requires Cloudflare Workers runtime types and your app):

```python
from worker import on_fetch

# request/env/ctx are provided by Cloudflare / wrangler
response = on_fetch(request, env, ctx)
```

## Caveats
- `on_fetch` uses `asyncio.get_event_loop().run_until_complete(...)`, which assumes an event loop is available and compatible with the runtime.
- The module relies on Cloudflare Workers Python runtime conventions (`WorkerEntrypoint`, `fetch`, and the `request/env/ctx` objects).
