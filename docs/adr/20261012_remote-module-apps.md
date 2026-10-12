# Apps served by remote modules over NATS

## Status
Accepted.

## Date
2026-10-12

## Context
Nexus builds its app catalog from the files of the modules the engine loads:
`apps__primary_adapter__FastAPI` walks every loaded module's
`apps/<app>/manifest.json`, and `/app-html/<module path>/<app>/` serves the
entry point and its assets from disk. Access needs a Nexus JWT, a scoped
`app-html` JWT or `ABI_API_KEY`; a scoped token opened with `?token=` is kept in
an HttpOnly cookie on `/app-html/`, so an app's later requests carry it too.

Remote modules (`naas-abi-sdk`, created by `abi new module`) run in their own
process or container. The engine never sees their files, so their `apps/`
folder never reaches Nexus. Their agents and jobs do: discovery carries them
in each `ModuleDescriptor`, and Nexus lists remote agents through
`services/agents/remote`.

Requirements:

- A module must not need a port, a hostname, a route or TLS to ship an app.
  NATS is its only connection.
- Apps must be able to have a backend (API routes next to the HTML), so that
  complex apps can be built on Nexus by modules.
- The discovery registry is one bounded snapshot: 256 live instances and
  512 KiB per project (20260923_module-discovery-registry.md). App files cannot
  travel in it.
- One NATS message is at most 8 MB.

## Decision
**Nexus stays the only HTTP entry point and forwards app requests to the
module over NATS. The module answers them like a web server.**

### Discovery
`ModuleDescriptor.apps = 8` lists the module's apps:

```proto
message AppDescriptor {
  string name = 1;          // URL segment, ^[A-Za-z0-9_-]{1,64}$
  string title = 2;
  string description = 3;
  string category = 4;
  string icon_emoji = 5;
  string entry = 6;         // path of the entry page, default "index.html"
  uint32 contract_major = 7;
}
```

At most 16 apps per module and 4 KiB per descriptor, so apps stay a small part
of the 512 KiB snapshot. Replicas of one contract must declare identical apps,
as they do agents, jobs and models.

`authorize_app` (`AuthorizeAppRequest`/`Response`) works like
`authorize_model`: the module asks discovery whether the caller's service token
is valid and the app is declared on a READY instance holding its lease.

### Requests
A new `abi.app.v1` package:

```proto
message Header { string name = 1; string value = 2; }
message HttpRequest {
  abi.common.v1.CallContext context = 1;
  string app = 2;
  string method = 3;
  string path = 4;          // below the app's root, starting with "/"
  string query = 5;
  repeated Header headers = 6;
  bytes body = 7;
  string root_path = 8;     // where Nexus mounts the app
  string user_id = 9;       // the signed-in Nexus user; empty with ABI_API_KEY
}
message HttpResponse {
  abi.common.v1.CallError error = 1;
  uint32 status = 2;
  repeated Header headers = 3;
  bytes body = 4;
}
```

Requests go to `abi.mod.<project>.<instance_id>.app.<name>.http`, the
instance-addressed shape model hosts use. A request body is at most 1 MiB and
a response at most 6 MiB, below the 8 MB broker limit. Larger answers return
502 with a clear message; streaming and WebSockets are later work.

### SDK
- `BaseModule` finds `apps/<name>/manifest.json` next to the module's package
  and declares an `AppDescriptor` for each (title, description, category and
  icon from the manifest).
- An `AppHost`, started next to the agent and model hosts, answers each
  request: it authorizes the caller (cached 5 s per token and app, as the agent
  host does), serves a file from `apps/<name>/` when the path names one (the
  same browser-asset suffixes Nexus allows), and otherwise passes the request
  to the app's ASGI application when the module bound one with
  `self.expose_app(name, asgi_app)` in `on_initialized`, else answers 404.
- The ASGI app is called in process, without an HTTP server: FastAPI or
  Starlette routes work as they are. `root_path` is set, so generated URLs
  point back through Nexus. `request.scope["abi"]["user_id"]` holds the Nexus
  user.

### Nexus
- The catalog adds the apps of READY remote instances, read from discovery and
  cached for 10 seconds, not for the life of the process. Their id is
  `remote/<module_id>:<app>` and their URL
  `/app-html/remote/<module_id>/<app>/<entry>`.
- `/app-html/remote/<module_id>/<app>/{path}` accepts every method, behind the
  same `/app-html/` access check. It picks a READY instance, forwards the
  request, and returns the response. It never forwards `Authorization` or the
  access cookie: the module gets the user's id, not the user's credential.
- The Next.js `/app-html/` proxy and Caddy already pass every method to the
  API, so the web app needs no change.

### CLI
`abi new app` in a remote module no longer prints a "not listed yet" note. The
remote module template shows how to bind a backend with `expose_app`.

## Alternatives considered
**Upload app files to the engine's object storage, served by Nexus.** No
domain needed and apps survive module restarts, but only static files: no
backend, so no complex apps. It also needs an upload step and a clean-up job.

**The module serves HTTP itself and Nexus links or proxies to it.** Supports
backends, but every module needs a network route, a hostname or path in Caddy,
TLS, and its own check of Nexus tokens. Rejected: a module must only need NATS.

## Consequences
- A remote module ships an app the way an in-engine module does (a folder with
  a manifest), and can add a backend in Python with no server of its own.
- Each request is one NATS round trip to the module, about a millisecond on
  the same network. Static files can be cached by browsers through the
  module's `Cache-Control` headers.
- An app is available while at least one instance of its module is READY, like
  its agents.
- All apps share the `/app-html/` origin and access cookie. A remote module's
  app is trusted like an in-engine module's: modules hold a service token, and
  only trusted modules should be run.
- The user id a module receives is asserted by Nexus. It is as trustworthy as
  the service-token boundary (Stage 1: a secret shared by the project).
- Not covered yet: responses above 6 MiB, streaming responses, WebSockets.
