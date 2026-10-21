# AppHost

## What it is

Serves module “web apps” over instance-addressed NATS subjects. Each browser request is forwarded by Nexus as an `abi.app.v1.HttpRequest`; `AppHost` authorizes the caller via discovery, then responds with:

- A static file from the app’s folder (for `GET`/`HEAD` with configured `root`), or
- The app’s ASGI callable executed in-process (no HTTP server/port).

Request/response bodies can stream via NATS (see `naas_abi_sdk.app_streams`).

---

## Public API

### Functions

- `app_subject(project: str, instance_id: str, name: str) -> str`  
  Builds the NATS subject for an app HTTP endpoint: `abi.mod.{project}.{instance_id}.app.{name}.http`.

- `call_app(transport: Any, project: str, instance_id: str, request: pb.HttpRequest) -> pb.HttpResponse`  
  Sends a `pb.HttpRequest` to a specific module instance’s app subject and awaits a `pb.HttpResponse`.  
  - Raises `naas_abi_sdk.transport.RPCError` if the reply is an error.
  - Note: reply arrives when the app starts its response (streaming may continue afterward).

### Class: `AppHost`

Hosts one or more apps for a module instance.

#### `__init__(session, apps, *, max_concurrency=DEFAULT_LIMIT, max_uploads=MAX_UPLOADS, idle_seconds=IDLE_SECONDS, user_callers=USER_CALLERS)`
- `session`: provides access to `session.client.transport.connect()`, `session.client.project`, `session.instance_id`, `session.lease_token`, and `session.client._call(...)` for discovery authorization.
- `apps`: `dict[str, tuple[AppDescriptor, ASGIApp | None]]`
  - Key: app name (used in subject and request routing)
  - Value: `(descriptor, asgi_callable_or_None)`
- `max_concurrency`: concurrent non-upload request handlers.
- `max_uploads`: concurrent streaming uploads accepted.
- `idle_seconds`: idle timeout for an app call before it answers (defaults to `60s`).
- `user_callers`: iterable of caller identities allowed to set `user_id`/`workspace_id` in requests (default `{"api"}`).

#### `start() -> None`
- Runs ASGI lifespan startup for each app that provides an ASGI callable.
- Subscribes to each app’s NATS subject and starts serving.

#### `close() -> None`
- Unsubscribes and stops serving.
- Cancels outstanding work, aborts active body streams, and runs ASGI lifespan shutdown.
- Streaming responses end with an error when the host closes (not a clean EOF); waits up to `CLOSE_SECONDS` for readers to observe termination.

---

## Configuration/Dependencies

### Protocol types
- Uses protobuf messages:
  - `naas_abi_proto.app.v1.app_pb2.HttpRequest` / `HttpResponse`
  - `naas_abi_proto.discovery.v1.discovery_pb2.AuthorizeAppRequest` / `AuthorizeAppResponse`

### NATS / transport expectations
- Expects an async NATS-like connection object from `session.client.transport.connect()` supporting:
  - `subscribe(subject, cb=...)`
  - `flush()`
  - optional `max_payload` attribute (used for message sizing)
- Uses `naas_abi_sdk.messages.reply(msg, bytes)` to reply.

### App descriptors
- `naas_abi_sdk.apps.AppDescriptor` fields used:
  - `name`
  - `root` (optional `Path`): enables static file serving for `GET`/`HEAD`
  - `entry` (default file when `/`)
  - `upload_limit` (max request body bytes accepted by the app)

### Important constants (behavioral limits)
- `MAX_INLINE_REQUEST_BODY`: 1 MiB max inline request body accepted.
- `MAX_REQUEST_BYTES`: inline request message size limit (body + overhead).
- `MAX_STREAMS`: max in-process concurrent streaming responses (default 256).
- `MAX_UPLOADS`: max concurrent streaming uploads accepted (default 16).
- `IDLE_SECONDS`: app call idle timeout before responding 504 (default 60s).
- Authorization caching:
  - `AUTHORIZATION_SECONDS`: cache lifetime cap (5s)
  - `MAX_AUTHORIZATIONS`: max cached entries (1024)

---

## Usage

Minimal skeleton (illustrative; requires a compatible `session` implementation and protobuf messages):

```python
import asyncio
from naas_abi_sdk.app_host import AppHost
from naas_abi_sdk.apps import AppDescriptor

async def asgi_app(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": b"ok", "more_body": False})

async def main(session):
    apps = {
        "demo": (AppDescriptor(name="demo", root=None), asgi_app),
    }
    host = AppHost(session, apps)
    await host.start()
    try:
        await asyncio.Event().wait()  # serve forever
    finally:
        await host.close()

# asyncio.run(main(session))
```

To call an app (as Nexus would), use `call_app(...)` with a transport that implements `.call(...)`:

```python
from naas_abi_sdk.app_host import call_app
from naas_abi_proto.app.v1 import app_pb2 as pb

# request = pb.HttpRequest(app="demo", method="GET", path="/", query="")
# response = await call_app(transport, project, instance_id, request)
```

---

## Caveats

- Static file serving is limited to specific suffixes (`STATIC_SUFFIXES`) and forbids path traversal; `manifest.json` at the app root is never served.
- Hop-by-hop headers are filtered when translating to ASGI (`HOP_BY_HOP` / `RESPONSE_HOP_BY_HOP`).
- If the ASGI app does not send any response, the host returns `500 "App sent no response"`.
- If the app stays idle (neither reads body nor starts a response) longer than `idle_seconds`, the host answers `504 "App timed out"` and cancels the app task.
- When the host is closing, in-flight streaming responses are aborted with an error (`MODULE_UNAVAILABLE`), not a normal completion.
- Only callers whose identity is in `user_callers` may send `user_id` or `workspace_id` in the request; otherwise `PERMISSION_DENIED`.
