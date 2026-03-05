# `Default` (Cloudflare Workers entry point)

## What it is
- Cloudflare Workers entry point that adapts a FastAPI ASGI app (`app.main.app`) to run on Cloudflare’s Python runtime using `asgi.fetch`.
- Provides a secondary `on_fetch` function for local development via `wrangler dev`.

## Public API
- `class Default(WorkerEntrypoint)`
  - `async fetch(self, request)`
    - Handles an incoming Cloudflare request by forwarding it to the FastAPI app through `asgi.fetch(app, request, self.env)`.
    - Passes Workers environment bindings (`self.env`) to the ASGI adapter.

- `def on_fetch(request, env, ctx)`
  - Synchronous wrapper used for local development (`wrangler dev`).
  - Instantiates `Default`, sets `worker.env` and `worker.ctx`, then runs `worker.fetch(request)` in the current asyncio event loop.

## Configuration/Dependencies
- Imports:
  - `asgi` (used for `asgi.fetch(...)`)
  - `workers.WorkerEntrypoint` (Cloudflare Workers Python entrypoint base class)
  - `app.main.app` (FastAPI application)
- Runtime expectations:
  - Cloudflare Workers provides `request`, `env`, and `ctx` objects.
  - `Default.fetch` relies on `self.env` being set by the Workers runtime (or manually in `on_fetch`).

## Usage
### Cloudflare Workers (entrypoint class)
```python
# worker.py (this module)
# Cloudflare will invoke Default().fetch(request) as the entrypoint.
```

### Local development (`wrangler dev`)
```python
# Wrangler calls on_fetch(request, env, ctx)
# which delegates to Default.fetch(...)
```

## Caveats
- `on_fetch` uses `asyncio.get_event_loop().run_until_complete(...)`; this assumes an event loop is available and not already running in the current thread.
