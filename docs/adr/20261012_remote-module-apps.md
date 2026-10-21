# Apps served by remote modules over NATS

## Status
Accepted.

Amended seven times since; see the amendments at the end. The text above
them is the decision as accepted on 2026-10-12.

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
  point back through Nexus. `request.scope["abi.user_id"]` holds the Nexus
  user.

### Nexus
- The catalog adds the apps of READY remote instances, read from discovery and
  cached for 10 seconds, not for the life of the process. Their id is
  `remote/<module_id>/<app>` and their URL
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

## Amendment (2026-10-12): names as built
Two names in the decision changed when it was built:

- A remote app's catalog id is `remote/<module_id>:<app>`, not
  `remote/<module_id>/<app>`: like every catalog app, `<module path>:<app>`.
  Its URL is unchanged.
- The Nexus user is in `request.scope["abi"]["user_id"]`, not
  `request.scope["abi.user_id"]`: one `abi` key holds what ABI adds to the
  ASGI scope.

## Amendment (2026-10-12): streamed bodies
This replaces the size limits under "Requests" (a request body at most 1 MiB, a
response at most 6 MiB, 502 above) and the consequence "Not covered yet:
responses above 6 MiB, streaming responses, WebSockets".

Bodies up to 256 KiB travel inline. Larger ones stream, in both directions:

- **Uploads.** Nexus sends the request with `body_follows` and a random
  `_INBOX` subject, `body_inbox`. The module pulls the body with `BodyPull`, one
  `BodyChunk` at a time, as its app reads `receive()` (`request.stream()` in
  FastAPI). Nothing is read from the browser faster than the app consumes it,
  so memory holds about one chunk in Nexus and in the module, and the app can
  pass the stream on, for example into object storage
  (`put_object_stream(prefix, key, request.stream())`). Nexus answers 413
  above the app's `max_upload_bytes` (manifest; default 1 GiB).
- **Responses.** A response sent in parts, or larger than 256 KiB, is answered
  with `body_follows`: Nexus pulls it as the browser reads it. This serves
  downloads, large files and server-sent events. A pull with nothing new is
  answered empty after 15 s, which keeps an idle stream alive; when the
  browser leaves, Nexus cancels the pull and the module cancels the app.
- **Timeouts are idle limits**, not totals: an app that neither reads nor
  answers for 60 s gets 504; a holder nobody pulls from for 60 s stops.
- **Retries.** A request moves to another instance only while none of its
  body was delivered; after that it is tied to the instance reading it.

Pulls are per chunk (256 KiB, or less under a smaller broker limit), so
throughput is bounded by round trips; measured locally at about 20 MB/s up
and 30 MB/s down. Every byte crosses NATS twice (browser to Nexus to module),
the price of keeping the module the owner of its data.

Not covered yet: WebSockets. Uploads and downloads are bounded by round trips
per chunk; prefetching chunks would raise throughput.

## Amendment (2026-10-13): apps run sandboxed, under a grant
Served from the Nexus origin with `allow-same-origin`, a module's page could
read the Nexus session from `localStorage`, and its `?token=` opened the whole
API. Remote apps no longer share the Nexus origin or the `/app-html/` cookie.
This replaces the consequence "All apps share the `/app-html/` origin and access
cookie" for remote modules.

- **Where.** Pages are served at `/app-remote/<grant>/<module_id>/<app>/<path>`,
  from the API origin, with `Content-Security-Policy: sandbox allow-scripts
  allow-forms allow-popups allow-downloads` and `Referrer-Policy: no-referrer`.
  The iframe sandbox has no `allow-same-origin` either. The page has an opaque
  origin: no `localStorage`, no access to the Nexus page, and the browser sends
  it no `SameSite=Lax` cookie.
- **The grant** is the only credential, so relative URLs carry it. It is signed
  with a key derived from the API secret and carries no `sub`, so it is never a
  session token. It opens one app as one user for 8 hours
  (`remote_app_grant_expire_minutes`). The Apps page mints it
  (`POST /api/apps/remote-grant`). The catalog URL
  `/app-html/remote/<module_id>/<app>/<path>` runs the usual access check and
  redirects to a fresh grant. nexus-web does not proxy `/app-html/remote/`.
- **The app** gets the grant URL as `root_path`, so URLs it builds keep the
  grant. Its page's `fetch()` calls are cross-origin: Nexus answers them, and
  their preflights, with `Access-Control-Allow-Origin: *`.
- **Headers pass on allow-lists.** Requests: `accept*`, `content-type`,
  `content-disposition`, `range`, `if-*`, `user-agent` and the app's `x-`
  headers (not `x-forwarded-*`, `x-real-ip` or `x-api-key`). Referer is not
  forwarded. Responses: `content-type`, `content-disposition`, `cache-control`,
  `etag`, `last-modified`, `vary`, `content-encoding`, `content-language`,
  `content-range`, `accept-ranges`, a `Location` inside the app, and the app's
  cookies.
- **Cookies.** A module's `Set-Cookie` is kept only with a `Path` under the
  app's root and no `Domain`. It is renamed `abi_app.<name>` in the browser,
  and only those cookies come back to the module, under their own names. From
  the sandbox the browser sends only `SameSite=None; Secure` cookies, and they
  last as long as the grant URL.
- **Scoped JWTs** (`scope`, as `app-html` link tokens have) no longer
  authenticate `/api/*` or the WebSocket.

## Amendment (2026-10-13): grants stay narrow and short
Changes to the previous amendment, from its security review:

- A grant opens one app as one user, never anonymously.
- The grant the catalog URL redirects to expires no later than the credential
  presented, so a share link stays as short as it was.
- Logs, activity events and traces show `/app-remote/[grant]/...`, never the
  grant itself.
- Only the Nexus origins may frame the page.
- A `Location` or cookie `Path` that a browser could read as a dot segment
  (`%2e`, `\`) is dropped.
- Cookies: from the sandbox, `fetch()` sends no cookie at all; navigations and
  forms in the frame send only `SameSite=None; Secure` ones, for as long as the
  grant URL lasts. Apps keep no session in cookies. (The previous amendment
  said the sandbox sends only `SameSite=None; Secure` cookies.)

## Amendment (2026-10-14): only Nexus asserts the user
This replaces the consequence "The user id a module receives is asserted by
Nexus. It is as trustworthy as the service-token boundary (Stage 1: a secret
shared by the project)."

Modules no longer hold the project secret: each signs with a key for its own
module id (`20261014_module-identities.md`). The app host passes a `user_id` on
only from the `api` identity, which no module can sign for; a request from any
other caller that names a user is refused with `PERMISSION_DENIED`. The token
Nexus sends with a request is bound to the instance it calls and lasts five
minutes, so that instance cannot replay it to another module or to the
engine's services. The ASGI scope carries both: `request.scope["abi"]` is
`{"user_id": ..., "caller": ...}`. Discovery registers a module only under a
token for its own module id, so no other module can serve
`/app-html/remote/<module_id>/` either.

Not covered: modules share one broker user, so a module that subscribes to
another module's app subjects sees Nexus's requests there, and can replay the
token of one of them to that same module, within its five minutes, naming a
user (see the module identities ADR, "Still open").

## Amendment (2026-10-14): workspaces, revocation, and what survives the hops
From the review findings of 2026-10-13 (A5 to A32) and the grant review.

**Grants.** A grant names a workspace (`ws`) that the user can open and where
the app is enabled, as the catalog shows it; the module gets it with each
request, `request.scope["abi"]["workspace_id"]` (`HttpRequest.workspace_id`),
under the same rule as `user_id`: only Nexus may name one.
`POST /api/apps/remote-grant` takes `workspace_id`. The catalog URL takes
`?workspace_id=`, and without it opens the first of the user's workspaces that
enables the app (by slug), so old links still work.

A grant is bound to the user's session by revocation, not by the access
token's few minutes: it ends when the user logs out (on any device), changes
their password or calls `POST /api/apps/remote-grant/revoke`. Each request
checks the user's latest revocation (`revoked_tokens`, cached 5 s) against
the grant's issue time (`iat`); the row a logout writes for the grants lasts as
long as the longest grant, so no grant it ended works again once the cleanup
job runs. Nexus credentials carry a fractional `iat` too: one whose `jti` is
revoked, or issued before the user's latest revocation, mints no grant (a
logged-out browser's token or app-html cookie gets 401; the Apps page
refreshes its token and asks again). The Apps page's grant lasts
`remote_app_grant_expire_minutes` (8 hours), and the page opens the app again a
minute before it expires, never within five minutes of opening it, since a
reload loses the page's state. The catalog URL's grant still never outlives
the credential presented, so a share link stays as short as it was. This
replaces the 2026-10-13 rule that a grant expires with the credential it was
exchanged for, for the Apps page.

**The catalog URL** takes every method: a user's request is redirected with a
307, which keeps the method and body; an `ABI_API_KEY` caller (a script, no
user) is answered directly, with no user and no workspace. nexus-web forwards
`/app-html/remote/` to the API and points the redirect at the API's public
origin (`NEXUS_API_URL`); a remote app still never runs on the Nexus web
origin. The local Caddyfile sends `/app-html/remote/*` through nexus-web for
that reason. This replaces "nexus-web does not proxy `/app-html/remote/`".

**Headers.** Responses also pass the app's `x-` headers, but for those a
proxy, CDN or edge runtime in front of Nexus acts on (`X-Accel-*`,
`X-Sendfile`, `X-Lighttpd-*`, `X-LiteSpeed-*`, `X-Envoy-*`, `X-Middleware-*`,
`X-Nextjs-*`, `X-Vercel-*`, `X-Nf-*`, `X-Amz-*`, `X-Amzn-*`, `X-Goog-*`,
`X-Ms-*`, `X-Azure-*`, `X-Varnish*`, `X-Cache*`, `X-Original-*`,
`X-Rewrite-*`, `X-HTTP-Method-Override`, `X-Forwarded-*`, `X-Real-IP`) and
those Nexus sets itself (`X-Frame-Options`, `X-Content-Type-Options`). It is
a deny-list because an app's API has `x-` headers of its own (request ids,
rate limits) that no list could name; the deployments ABI ships (Caddy,
Cloudflare) act on no `x-` response header. A deployment behind another proxy
should check its control headers against the list. Also `Retry-After`,
`WWW-Authenticate`, `Link` and `Content-Length`, with
`Access-Control-Expose-Headers: *`. The `Location` of a response that is not a
redirect (a 201's) passes as sent: the browser does not go there. A
redirect's still stays in the app. A value HTTP cannot carry (outside
latin-1, a line break or another control byte) is dropped. A `Set-Cookie`
pair is cut at its first `;` and needs a valid name. A `Location` whose
resolved path holds `%2e` is dropped, the request's own path included. The
query reaches the module as the browser sent it, less a `token` that holds a
Nexus credential: one that authenticated the request, the `ABI_API_KEY`, or
any token Nexus signed. An app's own `token` parameter passes.

**Bodies.** A response that breaks off after it started raises in Nexus, so
the server aborts the connection and the browser sees a failed download, not a
short one; the app's `Content-Length` is forwarded (and a HEAD's). A body
that does not fit one broker message streams instead of failing to send, and
an answer that cannot be sent is followed by an error, so Nexus never waits
for its timeout. A stream stops when the browser leaves, even while idle, and
the module hears of it at once. When the module stops (SIGTERM), a response
still streaming ends with an error and the host waits 3 s at most for its
reader. A finished body lingers past the reader's pull timeout, so the retry
of a lost last reply is answered.

**Limits.** The module stops reading an upload at its app's
`max_upload_bytes` (default 1 GiB) whatever the request says. Uploads run on
16 slots of their own in the module (one more is refused at once, and Nexus
tries another instance), so slow uploads never hold the slots of other
requests. An upload the browser drops ends with an error the module gets at
once. Nexus caps the responses streaming from one module per worker (256).
An app's own `RPCError` is an app error (502), never retried on another
instance.

**Still as before.** A module caches an authorization for 5 s (discovery's
own snapshot adds up to 1 s), as the agent and model hosts do, never past
the caller token's expiry: an instance that loses READY may serve a request
within that window. A draining module refuses requests on its own. Asking
discovery on every request would double each request's round trips.

## Amendment (2026-10-15): a draining module finishes what it took

**Decision.** On SIGTERM the module drains its apps before it closes
(`AppHost.drain`, under the module's `drain_timeout_seconds`, 300 s by
default):

- Its subscriptions drain, so a new request finds no responder and Nexus
  sends it to another instance. A request still queued behind busy calls is
  refused with `MODULE_UNAVAILABLE`: the app never ran it, so Nexus may
  resend it.
- Requests in progress, uploads included, answer.
- A response still streaming may finish, and so may a Starlette background
  task that runs after its body: a response whose body ended is never cut.
- Two kinds of stream are ended at once with `MODULE_UNAVAILABLE`, and their
  readers reconnect to another instance. One is server-sent events
  (`text/event-stream`). The other is any stream whose app has sent nothing
  for `DRAIN_IDLE_SECONDS` (1 s) and is not waiting for its reader.

**Why the idle rule.** The module has to exit within its orchestrator's
grace period: Docker's default is 10 s before SIGKILL. An idle stream looks
the same as an endless one (a long poll, server-sent events served without
their content type). Waiting for it would hold every shutdown for the whole
drain timeout.

**Tradeoff.** A finite stream whose app pauses for more than 1 s is cut
during a drain, and its reader sees an error. Examples are an LLM answer
streamed as plain text, NDJSON progress, or an export that computes between
chunks. The reader retries, and Nexus sends the retry to a ready instance.
An app that needs such a stream to survive a rollout keeps it busy (a
progress line, or whitespace the format ignores) at least once a second. A
longer idle window would protect slower streams. It would also hold every
deploy for that long whenever a reader keeps a quiet stream open.

