# Tools published by SDK modules, found and run over NATS

## Status

Accepted. Step 3 of the tool registry's NATS work
(`docs/adr/20260923_tool-registry-and-agent-composition.md`, sections 5 to 7; the
catalog is `docs/adr/20261021_tool-catalog-over-nats.md`). Running the engine's own
tools from a remote module is step 4 and reuses the invoke messages defined here
(`docs/adr/20261023_remote-callers-run-engine-tools.md`).

## Date

2026-10-22

## Context

An SDK module could declare agents, models, apps and jobs, never tools. The engine's
agents find tools in their process's tool registry, whose bindings are live Python
objects, so a module in another process had no way to offer one. Models already do
the equivalent: a descriptor in discovery, a handler bound with `expose_model`, a
unary request on an instance-addressed subject, and the provider authorizing the
caller (`docs/adr/20260924_remote-model-registry.md`, "Module-served chat models").
The engine had no discovery client; only Nexus reads discovery.

Three constraints shape it. A tool runs code with side effects, so a call is one
attempt and never replayed. Engine secrets must never reach a module, which is a
separate process with credentials of its own. And the broker cannot yet tell one
module from another (a single `module` user, `docs/adr/20261014_module-identities.md`),
so the module itself decides who may call it.

## Decision

### The contract

Declaring: `ModuleDescriptor.tools` (`discovery.proto`, field 9) is a list of the
portable `abi.tool_registry.v1.ToolDefinition` of the catalog. The module sets its
name, version, description, input schema (and optionally an output schema), tags,
configuration requirements and required scopes; `namespace` and `module` are its
module id, so a tool id is `<module_id>/<name>@<version>`. `remote` is set by the
engine, never trusted from a module. Discovery validates the descriptor at
registration and refuses (`INVALID_ARGUMENT`):

- a namespace or module that is not the module's own id, and a module id that is not
  a valid namespace (`[A-Za-z0-9_]+(.[A-Za-z0-9_]+)*`), a bad name, version or id;
- schemas that are not JSON objects with finite numbers, tags and scopes out of
  bounds, more than 32 tools, two versions of one name (the subject carries only the
  name), a tool above 8 KiB or tools above 32 KiB together (they travel in every
  lookup's reply, once per replica); an empty description, an input schema that
  does not describe an object or that `jsonschema` rejects;
- a **secret configuration requirement** and a **workspace requirement**: a tool
  another process runs holds no engine secret and has no engine workspace.

Replicas of a contract in one rollout must declare identical tools
(`DESCRIPTOR_CONFLICT`); the SDK serialises schemas canonically so they compare equal.

Calling: `naas_abi_proto/tool/v1/tool.proto`. A unary `InvokeToolRequest` on
`abi.mod.<project>.<instance>.tool.<name>.invoke`, to one ready instance, with a token
bound to it (`aud`). The request holds the tool name and version, **JSON arguments**,
**JSON configuration** (plain values), and the `CallContext`: `principal_id` is the end
user, `workspace_id` the workspace, `timeout_ms` the time the caller waits. The reply
is a JSON result or a `CallError`. No pickle, no callable, no binding value, no secret.
`InvokeTool*` are the messages the next step reuses.

Module-side limits (no Protovalidate, as for the other services): request 512 KiB as
sent (an overflow upload is refused), arguments 256 KiB, configuration 64 KiB, result
512 KiB. The handler's deadline is the caller's wait, at most 300 s (60 s when unset);
a synchronous handler runs on a thread, whose deadline stops the wait, not the thread.

Authorization is discovery's `authorize_tool` (like `authorize_model`): it checks the
provider's lease, that the instance declares the tool and is READY, and that the
caller's token is bound to this instance, and returns the verified caller identity.

### What a call goes through, in the module

1. size limits; 2. discovery's `authorize_tool` (a token for another instance, or none,
stops here); 3. the module's **`authorize_tool(name, caller)`** hook; 4. the end user
check; 5. **arguments validated against the declared input schema**, configuration
against the descriptor (unknown or missing required key); 6. the handler.
Malformed arguments never reach the handler.

`authorize_tool`'s default allows the engine's own processes (`api`, `engine`,
`dagster`) and refuses every other caller, other modules included. A module overrides it
to widen or narrow that; it replaces the default entirely, and only `True` allows. The
hook runs after discovery has verified who the caller is. `principal_id` is honoured only
from `api` and `engine` (the processes that authenticate users, the same rule as apps); any
other caller naming a user gets `PERMISSION_DENIED`.

Errors are sanitized: the host answers with a stable code (`UNAUTHENTICATED`,
`PERMISSION_DENIED`, `TOOL_NOT_FOUND`, `MODULE_UNAVAILABLE`, `INVALID_ARGUMENT`,
`PAYLOAD_TOO_LARGE`, `DEADLINE_EXCEEDED`, `TOOL_ERROR`). A handler reports a failure the
caller may read by raising `ToolError`; any other exception, an `RPCError` of the
handler's own included, is logged in the module and reported as a generic
`Tool execution failed`. A result must be JSON and match the output schema, if declared.

### SDK

`BaseModule.tools = (ToolDescriptor(...),)` (name, description, input schema, version,
output schema, tags, `ToolConfig` keys, required scopes), `expose_tool(name, handler)`
for sync (thread) and async handlers, `authorize_tool`, and `ModuleProxy.call_tool` for
a caller that holds a module. `run_module` requires a handler for every declared tool
before readiness, and starts a `ToolHost` that drains with the module. Serving needs the
SDK extra `tools` (`jsonschema`), imported at start with a clear error.

### Engine: discovery in, registry out

`RemoteToolSynchronizer` (`services/tool_registry/`) reads discovery on a schedule
(`nats.tool_registry.remote_modules.refresh_seconds`, 5 s) through a secondary port
(`IRemoteToolDirectory`, adapter `RemoteToolsSecondaryAdapterNATS`, as the engine's own
`engine` identity) and publishes the tools of every module with a READY instance to the
process's registry as `<module_id>/<name>@<version>`, with `remote=True`. A module with
no ready instance (stopped, draining, lease expired) is unpublished, and the index
follows: `ToolRegistryService` re-syncs on the next search and deletes what it indexed
itself. A failed read keeps what is published (discovery being down says nothing about
the modules). When a module's changed set is refused (an id another module
holds), the set it published before is unpublished too, so the registry never
advertises tools or a contract generation the module no longer serves; the
refusal is retried at every read and logged once. The first read runs in the
synchroniser's thread, so a slow discovery never holds up the engine's boot. A module whose id is a loaded module's name is not published (it would
replace it), nor a tool another module already holds.

Every role that composes agents does it (serving, standby, client): bindings are per
process, so a client engine holds the module's tools itself, as it does its own, and
the serving engine's catalog shows them to the processes that do not (`remote` is part
of the portable definition). Index ownership is unchanged: the serving engine is the
sole writer of the shared index and indexes remote tools like local ones; a client's
in-memory index is its own.

`resolve` builds a LangChain `StructuredTool` (`RemoteToolBinding`) whose schema is the
module's JSON Schema as is. A call looks up the module's READY instances in discovery,
picks one, and sends one `InvokeToolRequest` as the engine with the caller's user and
workspace (`ToolContext`). A module error becomes the tool's output
(`ToolException`), so the model can recover; no call is retried, and a timeout says the
tool may still have run. The access policy and required scopes are the registry's, as for
local tools, applied before the binding is built, and the catalog's discovery rules
(`DISCOVER`) apply to remote tools like any other.

### Credentials

Engine secrets never go to a module, and the layers back one another:

- discovery refuses a secret requirement, so a definition cannot ask for one;
- a remote binding's default configuration is empty, and it refuses configuration keys
  the module did not declare;
- the composer rejects a `{secret: NAME}` binding on a remote tool with one
  `AgentCompositionError` (also in a capability agent's `tool_config`), whether the tool
  is held locally or only known from the catalog; the message names the secret, never
  its value. The module holds its own credentials (its environment, its own services);
- a request carries arguments and plain configuration, the caller's user and workspace,
  and a token bound to the instance (a claim signed with the project key, not the key).

A test sends a call through a real broker and checks that nothing of the engine's secrets
is in what the module received.

### Broker permissions

`MODULE_PERMISSIONS` and the generated `nats.conf` need no new entry: they are deny
lists, a module may serve `abi.mod.>` and call `abi.svc.>` and discovery, and they still
refuse it the engine's subjects (`abi.svc.>`, `abi.discovery.>`, `abi.rpc.>`, `_INBOX.>`,
`$JS.>`, `$KV.>`), so a module cannot serve the tool catalog or answer for discovery. Tests
pin it: `nats_permissions_test.py` (a tool subject is open, the engine's are closed) and the
broker integration test. A module can still subscribe to another module's tool subjects
(`abi.mod.>`), as the identities ADR records for every module subject: it could replay a
token sent to that module, to that module only, for five minutes. Per-module users remain
the next step.

## Consequences

- An SDK module's tools are found by meaning, enabled by a `CapabilityAgent`, bound by a
  composed record and run by any agent, in any engine role, and disappear within
  `refresh_seconds` of the module's last ready instance going away.
- A remote tool that needs configuration (a `ToolConfig` the module declares) is
  "unavailable" until the record or the caller provides it, as a local one.
- Latency: a call costs a discovery lookup and the module round trip.
- Every engine process reads discovery every `refresh_seconds` (one page per 100
  instances), and keeps one more NATS connection for it and one for calls.
- A module cannot declare more than 32 tools or 32 KiB of descriptors. Every replica
  carries them in discovery's snapshot and in each `get_module` / `list_modules` reply
  (512 KiB bounds both), so eight replicas at the limit use half of it. Agents, models and
  apps have looser totals; this one is deliberately tighter. A module with more tools
  should group them or expose a general one.
- A caller waits at most `call_timeout_seconds` (120 s, at most 300 s); a longer job
  belongs to a module job or an agent.
- A synchronous handler cannot be cancelled: a deadline releases the caller, not the thread.
- Every call costs two discovery reads (the engine's `get_module`, the module's
  `authorize_tool`), and each engine process lists the instances every
  `refresh_seconds`.
- The engine signs every call as the identity `engine`, in every role, so a module's
  `authorize_tool` cannot tell `api` from `dagster`; it can tell the engine from another
  module, which is the boundary that exists today.
- Out of scope: per-module broker users, streaming tool results, and discovery push
  (the engine polls). Running the engine's tools from a module is
  `docs/adr/20261023_remote-callers-run-engine-tools.md`.
