# Remote callers run the engine's tools over NATS

## Status

Accepted. Step 4 of the tool registry's NATS work
(`docs/adr/20260923_tool-registry-and-agent-composition.md`, "Contracts"). The catalog is
`docs/adr/20261021_tool-catalog-over-nats.md`; tools published by SDK modules, whose
invoke messages this step reuses, are `docs/adr/20261022_remote-module-tools.md`. Client
engines running a tool through a proxy in `resolve` is deliberately not part of it (see
"Not done").

## Date

2026-10-23

## Context

The engine's tools are live Python objects in the serving engine's registry: a GitHub
integration built from a module's token, a workflow, a workspace tool. An SDK module, or a
client engine, could find them (the catalog) but not run them. Giving the caller the tool
is not an option (it is code, with credentials in its closure), and running it in the
caller means copying its configuration there. The engine must run it, resolve its
configuration and secrets itself and decide who may.

This is the step with the most risk: the caller is another process, possibly third-party
code, and what it asks for can name a credential. The constraints:

- **The caller's rights come from its verified identity**, never from its request. The
  broker has one `module` user for every module; what tells modules apart is the service
  token, a claim signed with a key derived for one module id
  (`docs/adr/20261014_module-identities.md`).
- **Engine secrets never reach a caller**, not as a value in a request, a result, an
  error or a log.
- **Nothing is trusted by default.** A module that was never configured runs nothing.
- Tools are written for in-process agents. Several publish with no `required_scopes`
  (the GitHub module's about thirty, with the module's own personal access token as
  their default configuration, among them destructive ones), which the default policy
  treats as public.

## Decision

### The contract

`abi.svc.tool_registry.v1.invoke_tool` (`naas_abi_proto/tool_registry/v1/tool_registry.proto`),
a unary call to the serving engine. Its request has the fields, numbers and meaning of
`abi.tool.v1.InvokeToolRequest` (the call to a tool a module serves) and one more:

| Field | Meaning |
|---|---|
| `context` | `trace_id`; `timeout_ms` is the deadline (60 s when zero, at most 300 s); `principal_id` and `workspace_id` are honored from `api` and `engine` only |
| `tool`, `version` | `<namespace>/<name>[@<version>]`; the version when `tool` has none, else the highest |
| `arguments_json` | a JSON object, validated against the tool's input schema |
| `config_json` | plain values for configuration keys the definition declares and does not mark secret |
| `secret_refs` (new) | configuration key the definition marks secret -> the **name** of an engine secret |

The response is a JSON result or a `CallError`. No pickle, no callable, no binding value,
no engine secret crosses the wire: the engine runs the tool (`EngineToolInvoker`) and
only JSON comes back. `tool.proto` says why it has no `secret_refs`: none reaches a module.

Error codes are stable: `UNAUTHENTICATED`, `PERMISSION_DENIED`, `TOOL_NOT_FOUND`,
`INVALID_ARGUMENT`, `PAYLOAD_TOO_LARGE`, `RESOURCE_EXHAUSTED` (retryable),
`DEADLINE_EXCEEDED`, `TOOL_ERROR`.

### What a call goes through, on the engine

`EngineToolInvoker` (`services/tool_registry/`, technology agnostic) receives the decoded
call and an `InvokeCaller` that the NATS primary built from the verified token, and checks
in this order:

1. size limits, and who may name an end user or a workspace;
2. the tool: not discoverable by the caller is `TOOL_NOT_FOUND` (a caller cannot tell it
   exists); a tool a module serves (`remote`) is `PERMISSION_DENIED` (the caller reaches
   that module directly, with its own identity; routing it through the engine would make
   the engine's identity speak for it); a tool that declares no scope runs only for a
   caller that was granted it; then the registry's access policy for `EXECUTE`;
3. the arguments against the tool's JSON Schema; the configuration (declared keys only,
   plain values, **no value for a key marked secret**: `PERMISSION_DENIED`, "reference an
   engine secret by name"); the secret references (the key must be one the definition
   marks secret; the name must be on the caller's allow list, checked **before any
   lookup**, so no secret's existence is revealed);
4. admission, then, on a worker thread under the deadline: resolve the secrets,
   `registry.resolve` (which applies the policy and the required configuration again) and
   run the tool.

The result, a `ToolException`'s message and the arguments' validation message are scrubbed
of the values of every secret the call used (the referenced ones and the credential
defaults of the binding) before they leave. Any other failure of a tool is `TOOL_ERROR`
with the message "Tool execution failed"; the exception is logged by type only (a message
may hold the credential an HTTP client put in it). A binding's failure to build is "The
tool could not be built". The activity log gets one event per call
(`tool_registry.invoke`, actor `service:<identity>`) with the tool, outcome, code and
duration; arguments, configuration and secret names are not recorded.

Limits (no Protovalidate; the proto's header and `EngineToolInvoker` state them): a
request of 512 KiB, arguments 256 KiB, configuration 64 KiB, 16 secret references of 128
characters, a result of 512 KiB (declared once, in `naas_abi_sdk.tools`, which the
engine and the SDK import). `nats.tool_registry.invoke.max_concurrent` (16) calls run
at once, and the engine **lowers it to half of `nats.max_concurrent_requests`** (at least one,
with a warning at startup; `NATSConfiguration.tool_invoke_concurrency`), so the catalog's
reads, which share the service's slots, always find one. A `default_timeout_seconds`
above `max_timeout_seconds` is lowered to it, so no call outlasts the cap. A call over
the limit is refused with `RESOURCE_EXHAUSTED`, never queued. A slot is held until the
tool returns, so a tool that outlives its deadline keeps it: a synchronous tool cannot be
cancelled, and hung tools lead to `RESOURCE_EXHAUSTED`, not to unbounded threads.

### Who can run what

The caller is the identity in the verified token (`verify_service_token`), as for the
catalog:

| Identity | Scopes | Secrets it may reference | Tools without a scope | Names a user |
|---|---|---|---|---|
| `api`, `engine` | every scope the registry's tools declare | any | all | yes |
| `dagster` | same | any | all | no |
| an SDK module `<id>` | `nats.tool_registry.module_scopes[<id>]`, none by default | `invoke.modules[<id>].secrets`, none by default | those matching `invoke.modules[<id>].unscoped_tools`, none by default | no |

```yaml
nats:
  tool_registry:
    module_scopes:
      my_company_module: ["github:read"]
    invoke:                         # all optional
      enabled: true                 # false: every call is PERMISSION_DENIED
      max_concurrent: 16
      default_timeout_seconds: 60
      max_timeout_seconds: 300
      modules:
        my_company_module:
          secrets: [GITHUB_ACCESS_TOKEN]
          unscoped_tools: ["naas_abi_marketplace.applications.github/get_*"]
```

The engine's own processes hold the project secret, so they can already do everything a
tool does; they are trusted with every scope and secret, and still go through argument,
configuration and secret-reference validation (a secret goes only to a key marked secret).
`invoke.modules` and `module_scopes` refuse a first-party identity as a key.

The `principal_id` and `workspace_id` of a call from any other identity are refused
(`PERMISSION_DENIED`): a module cannot run a tool as someone else's user or workspace.
`ToolHost` (tools a module serves) now refuses a workspace the same way as a user: a
first-party caller outside `user_callers`, `dagster`, gets `PERMISSION_DENIED` when it sets
either. The
tool receives the verified scopes, the user and the workspace in its `ToolContext`.

### The GitHub tools, and tools without a scope

The GitHub module publishes about thirty tools with no `required_scopes` and with the
module's token as default. Exposed as they are, any remote caller could run
`delete_repository` with the platform's token. The decision is the deny-by-default above:
**no SDK module runs a tool that declares no scope until an operator lists it** in
`unscoped_tools`, and the operator should pair it with a dedicated, least-privilege secret
the module may name (`secrets`) rather than the module default. A tool that must be
reachable by scope alone declares `required_scopes` when it publishes. This is enforced in
the engine; nothing about the tools changes for in-process agents.

### Threat model

| Threat | Mitigation |
|---|---|
| A module runs a tool it should not (a destructive one, with the platform token) | no scope, no run (above); scopes are the operator's per module, from the token's verified identity; tools of other modules are refused |
| A module forges another identity, or the engine's | a module key signs for its own id only; a module token cannot assert a first-party identity (`verify_service_token`); the request carries no identity field |
| A module claims to act for a user or a workspace | refused from every identity but `api` and `engine`; also in `ToolHost` for the modules' own tools |
| A module names an engine secret (`NATS_JWT_SECRET`, a provider key) to make a tool read it | per-module allow list, empty by default, checked before lookup; a name is only accepted for a key the tool marks secret; the project secret is not on any list the operator did not write |
| A module sends a credential inline | refused for keys marked secret; the message does not echo the value |
| A module reads a secret out of a tool's result or error | exact-value scrubbing of the referenced secrets and the binding's credential defaults; errors of unknown tools are generic; logs hold the tool id, identity, code and duration only |
| A module overloads the engine | bounded concurrency (RESOURCE_EXHAUSTED), a deadline (a slot is held until the tool returns), size caps, a separate worker pool, per-call validation before any thread |
| Malformed or hostile arguments | JSON object with finite numbers, validated against the schema before the binding is resolved |
| A tool of another module is run through the engine | `remote` tools are refused: the confused-deputy risk of the engine's identity |
| A module redirects a credential through plain configuration (a base URL) | not prevented by the engine, which cannot tell such keys apart; granting is per tool, and the ADR says to withhold tools that mix the two (Consequences) |
| Code or objects are shipped | arguments, config, result: JSON only; the tool and its binding never leave the engine |
| An unauthenticated or replayed call | the primary requires a valid token (`UNAUTHENTICATED`); a token bound to a module instance (`aud`) is refused here |

### SDK

`ToolRegistryService.invoke(ref, arguments, *, config, secrets, version, timeout)` (the
SDK facade over `ToolRegistryClient.invoke_tool`, whose generated method takes a
`timeout`, which the transport writes to `context.timeout_ms`, and a `grace`) returns the
JSON result and raises `ToolNotFound`, `ToolPermissionDenied`, `ToolExecutionError` or
`ServiceError`. The caller waits the deadline **plus 5 seconds** (`grace`), so a slow tool
ends with the engine's `DEADLINE_EXCEEDED`; a reply lost even then is a `ServiceError`
`DEADLINE_EXCEEDED` too ("the tool may still have run"), never a raw timeout.
It refuses before sending what the engine would. `as_tool` and
`naas_abi_sdk.engine_tools.engine_tool` wrap a definition, found by `get_tool` or
`search_tools`, as a LangChain `StructuredTool` whose schema is the definition's JSON
Schema and whose call is `invoke`; the configuration and the secret **names** are fixed
when it is built, so the model never sees them, and every failure of the call (a refusal, a
timeout, arguments over the limits, a lost connection: named without hosts or values)
reaches the model as the
tool's output. The proxy needs the extra `engine-tools` (`langchain-core`). An SDK
`Agent` binds what a search returned:
`tools=[await registry.as_tool(m, secrets=...) for m in await registry.search_tools(...)]`.
(The SDK agent now also calls tools whose `args_schema` is a JSON Schema dict; core's did
since the previous step.)

### Broker permissions

`MODULE_PERMISSIONS` needs no new entry: a module already publishes to `abi.svc.>` (the
engine decides from the token) and may not subscribe there, so it cannot answer
`invoke_tool`. `nats_permissions_test.py` and the broker integration test pin both.

### Not done: client engines

A client or standby engine's `resolve` of a tool it has not loaded still raises
`ToolResolutionError`. A NATS-backed proxy there would have to send the tool's
configuration, and the composer resolves `{secret: NAME}` against **the client's own
secret service** before it calls `resolve`: the proxy would receive credential values, and
sending them is the inline credential this contract refuses. Doing it right means the
composer passing secret references through for tools the process does not hold, so that
the serving engine resolves them against its own secrets and allow list: a change to the
composer and to the records' semantics, not to the transport. The contract and the SDK
proxy are ready for it. Until then a client engine's process can run an engine tool as
the `engine` identity through `ToolRegistryService.invoke` of the SDK, and a record binds
tools its own process loads or a module serves.

## Consequences

- An SDK module finds, binds and runs engine tools with its token's rights, and the
  engine's secrets stay in the engine. An operator opts a module in explicitly, in three
  places (`module_scopes`, `invoke.modules[<id>].secrets`, `unscoped_tools`).
- Until an operator lists them, the GitHub tools run for no module. The operator decides
  per module, and the GitHub module's destructive tools should declare scopes.
- Scrubbing is by exact value: a tool that transforms a credential (base64, a prefix cut)
  before returning it defeats it. Scopes and least-privilege secrets are the defence;
  scrubbing is the net.
- The caller's own end-user rights (`api`, `engine`) are the tool's context only: the
  registry's policy sees the engine's scopes for them, so a user's scopes must be applied by
  the caller, as for the catalog.
- **The secret allow list closes one door; the secret service was the other.** The engine's `secret`
  service was open over NATS to every authenticated caller, SDK modules included, so a module that may
  not name `NATS_JWT_SECRET` to a tool could still read it with `abi.svc.secret.v1.get`. It is closed to
  modules since `docs/adr/20261024_secret-service-closed-to-sdk-modules.md`: a module reads and writes
  only the names `nats.secret.modules` grants it.
- **Plain configuration can steer a credential.** A caller writes the non-secret values of a tool's
  configuration. A tool that takes both a credential and a value saying where to send it (a base URL, an
  endpoint) lets a granted caller point the credential at a server of its own; scrubbing cannot help once
  the engine has sent it. The engine cannot tell such keys apart: do not grant a module a tool that mixes
  them, or have the tool validate the value. The GitHub tools take only the token.
- A synchronous tool past its deadline keeps running; its slot stays taken until it returns.
- `api`, `engine` and `dagster` are not separated from each other in `module_scopes`, as
  in the catalog.
- Out of scope: per-module broker users, streaming results, client engines' `resolve` proxy
  (above), and the composer's own handling of secret references (records may still name any
  engine secret for a tool the process holds; restricting it to keys marked secret and to a
  per-tool allow list belongs with records).
