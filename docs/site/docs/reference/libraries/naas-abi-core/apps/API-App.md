# API App

The FastAPI app lives at `naas_abi_core.apps.api.api` and lazily loads engine/runtime routes.

## Start

```bash
uv run python -m naas_abi_core.apps.api.api
```bash

Default host/port: `0.0.0.0:9879`.

## Route loading model

- API starts with static routes (`/`, `/docs`, `/redoc`, auth).
- Runtime routes are loaded lazily by calling `get_app()`.
- For each module agent, `agent.New().as_api(...)` is registered under `/agents`.

## Auth model

- Protected endpoints use bearer token validation against `ABI_API_KEY`.
- Token can be passed in `Authorization: Bearer <token>`.
- Query parameter token is also supported (`?token=...`).

## Main agent endpoints

- `POST /agents/<agent_name>/completion`
- `POST /agents/<agent_name>/stream-completion`

Payload shape:

```json
{
  "prompt": "Your question",
  "thread_id": "1"
}
```
