# Apps published by remote modules

## Status
Proposed. Not implemented: this note asks for a decision first.

## Date
2026-10-12

## Context
Nexus builds its app catalog from the files of the modules the engine loads:
`apps__primary_adapter__FastAPI` walks every loaded module's
`apps/<app>/manifest.json`, caches the result for the life of the process, and
serves `html:` entry points and their assets (`.html`, `.js`, `.css`, images,
fonts, `.json`) under the authenticated `/app-html/<module path>/<app>/` route.

Remote modules (`naas-abi-sdk`, created by `abi new module`) run in their own
process or container. The engine never sees their files, so their `apps/`
folder, which the scaffold creates, never reaches Nexus. Their agents and jobs
already do: discovery carries `AgentDescriptor` and `JobDescriptor` in each
`ModuleDescriptor`, and Nexus lists remote agents through
`services/agents/remote` (a port, a discovery adapter, `provider = "remote"`).

Constraints:

- The discovery registry is one bounded snapshot: 256 live instances and
  512 KiB per project (20260923_module-discovery-registry.md). Replicas repeat
  their descriptor. App files cannot travel in it, and manifests only if small.
- A remote module reaches the engine only through NATS. Nexus must not need a
  network route to the module (no HTTP from Nexus to a module container).
- One NATS message is at most 8 MB; larger payloads use the chunked transfers
  (20260924_chunked-nats-transfers.md).
- Replicas of one contract must declare identical descriptors.

## Options

**A. Descriptor lists the apps; the module serves the files over NATS.**
`ModuleDescriptor.apps` (new field 8) holds an `AppDescriptor` per app. Nexus
proxies `/app-html/remote/<module_id>/<app>/<path>` to the module with a new
`app.assets.v1` request (an `AppHost` next to `AgentHost`, queue group per
module, chunked transfer above 8 MB).
Pro: always the running code's files; nothing to clean up.
Con: every page load and asset is a NATS round trip to a module process; the
app is down whenever the module is; new SDK host, new subject family, new
Nexus proxy with streaming.

**B. Descriptor lists the apps; the module publishes its files to the
engine's object storage, and Nexus serves them from there.**
Before it registers, the module uploads `apps/<app>/**` (browser asset suffixes
only) to object storage under a content-addressed prefix,
`apps/<module_id>/<digest>/<app>/<path>`, unless a marker object for that
digest exists. The descriptor carries the digest. Nexus serves
`/app-html/remote/<module_id>/<app>/<path>` by reading the digest of a READY
instance and then the object.
Pro: no new RPC: object storage over NATS exists, including chunked uploads;
replicas with the same files share one copy; assets are cacheable (the digest
is in the path); Nexus keeps a static-file shape.
Con: an upload on the first start of each version; old digests need pruning;
the module must declare `object_storage` when it has apps.

**C. The module runs an HTTP server and Nexus reverse-proxies to it.**
Rejected: it needs a network route from Nexus to each module and a second
transport with its own authentication, against the NATS-only boundary.

## Proposed decision
Option B.

- **SDK.** `AppDescriptor(name, title, description, category, icon_emoji,
  entry, manifest_json)`, where `manifest_json` is the manifest minus the
  fields Nexus already has, capped at 4 KiB per app and 8 apps per module so a
  descriptor stays small in the 512 KiB snapshot. `BaseModule` finds `apps/`
  next to the module's package (as core modules do) when `apps` is not
  declared. `run_module` publishes the files after `on_initialized` and before
  readiness, then registers with the digest. A module with apps but without
  the `object_storage` dependency fails at startup with a clear message.
- **Proto.** `ModuleDescriptor.apps = 8` (`repeated AppDescriptor`), and
  `apps_digest = 9`. Older engines ignore unknown fields.
- **Nexus.** An `apps/remote` port and discovery adapter, like
  `agents/remote`. The catalog merges the static scan with a live discovery
  read (cached briefly, not for the process lifetime). Remote apps carry
  `provider: "remote"`, an id `remote/<module_id>/<app>`, and
  `available = false` when no instance is READY. The `/app-html/` route
  accepts `remote/<module_id>/<app>/<path>`, checks the same access token,
  resolves the digest from a READY instance, and streams the object with the
  existing suffix allow-list and a long `Cache-Control` (the path is
  immutable).
- **Clean-up.** A kernel job (`naas_abi_core.apps`, daily) deletes digests that
  no registration has referenced for 7 days.
- **CLI.** `abi new app` stops printing its "not listed yet" note, and the
  remote module template declares `object_storage`.

## Consequences
- Remote modules ship apps the same way as in-engine ones: a folder with a
  manifest. The catalog shows them while the module is registered.
- An app keeps working while its module restarts or scales down, as long as a
  registration still names its digest; it disappears when the module
  unregisters for good.
- Object storage holds one copy per app version until the clean-up job
  removes it.
- Apps whose manifest `url` is an absolute URL need no upload: only the
  descriptor travels.
- Not covered: apps with a backend of their own (FastAPI routes). A remote
  module's backend logic is reached through its agents and jobs, or a later
  `app.call.v1` request type.

## Questions for approval
1. Option B (object storage) rather than A (live NATS proxy)?
2. Do the caps (4 KiB manifest, 8 apps per module) fit the apps you expect?
3. Clean-up after 7 days unreferenced, by a kernel job on the engine?
