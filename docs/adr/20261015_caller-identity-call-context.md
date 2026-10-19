# The caller of every kernel call travels in one CallContext

Status: Accepted

Date: 2026-10-15

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §10.

## Context

**Authorization will run inside the domain services** (RFC §5, §11). A check there needs to know who calls,
the same way for NATS, Nexus REST and in-process callers. Before this change:

- **Identity stopped at the transport.** Every NATS primary verified `Nats-Auth-Token` and then dropped its
  `sub`. The proto `CallContext` has `principal_id`, `workspace_id` and `tenant_id`, but nothing set or read
  them.
- **Events had their own identity.** `event_actor_user_id`, `event_actor_workspace_id` and
  `event_triggered_via` were ContextVars set by Nexus's middleware and chat. Only `EventService.publish`
  read them.
- **Three endpoints skipped their domain service.** The event, vector_store and cache primaries wrapped the
  raw secondary adapters, so a check in `EventService`, `VectorStoreService` or `CacheService` would never
  see their calls.
- **The end user never reached the engine.** Nexus called kernel services in process, and over NATS as the
  shared `api` identity.

## Decision

1. **One context variable, defined in the SDK.**
   - `naas_abi_sdk.call_context` holds `Principal`, `CallContext` and the variable.
   - `naas_abi_core.engine.call_context` re-exports it and adds `as_service_account`, so the engine and the
     SDK clients it runs read the same value.
   - The SDK is an optional extra of core (`nats`). Without it, core runs a verbatim copy of the module
     (`engine/call_context_types.py`); a test keeps the two files equal.
   - The default is `ANONYMOUS`.
2. **One shared helper builds it for NATS.**
   - `naas_abi_core.engine.nats_identity` builds it from the verified token, the `Abi-On-Behalf-Of` header
     and the request's `context` envelope (trace and target workspace only).
   - `DomainRPCDispatcher.call` runs the worker in a copy of the context holding it, so it ends with the
     call.
   - Discovery, the model registry and transfer sessions use the same helper. A transfer session runs as
     the caller who opened it, and only that actor acting for that same user may go on with it. Model
     registry chat streams follow the same rule (`same_caller`).
   - A client stream captures its user and trace once, when it opens: frames read later, or from another
     thread, still belong to it.
   - `nats_rpc.authenticate_request` authenticates a `nats.micro` request and answers a refusal itself, so
     the primaries share one path.
3. **Identity never comes from a request body.**
   - `principal_id` and `tenant_id` are reserved and ignored.
   - `workspace_id` is the target workspace of a create, an input like any other.
4. **The on-behalf-of header is refused, not ignored, from untrusted callers.**
   - Until delegated tokens (step 8), only `api` and `engine` may name a user.
   - From anyone else the call fails as unauthenticated before reaching the domain. A user can only narrow a
     call, so dropping the header would silently widen it.
   - A refusal says so (`on-behalf-of refused: …`) and is logged, so it is not mistaken for a bad token.
   - The core RPC client sends it only when its own identity is trusted; any other identity calls as itself,
     as before.
   - The SDK transport sends it only when built with `forward_user=True`. The engine's transports to kernel
     services set it; module transports and Nexus's transports to module hosts do not.
5. **Nexus runs each request as `api` on behalf of the signed-in user.** Its request middleware sets the
   context, and kernel calls carry it: directly in process, as the header over NATS. Work for no caller runs
   under `as_service_account`: engine-hosted jobs as `engine`, Nexus's configuration seeding as `api`.
   - The kernel trusts that user from `api`, so the middleware names one only as strictly as `AuthService`
     signs a user in: a session token (no `scope`) whose `jti` is not revoked. A failed revocation lookup
     names nobody.
   - A request with no such user (no token, a scoped link token, a revoked token) runs as `ANONYMOUS`, not
     as `api`: a public route must never get the rights of Nexus's own service account.
6. **The event actor variables are views of the context.**
   - `EventService.publish` stamps the call's user, workspace and `triggered_via`.
   - The old names keep a ContextVar-like `get`/`set`/`reset` for existing callers. Setting the user sets
     `on_behalf_of`, and a reset restores only its own field, so resets may come in any order.
7. **The event, vector_store and cache NATS endpoints call their domain services.** The wire contracts do
   not change.
   - `EventService` gains stored-level operations (`append_stored`, `max_seq`, cursors,
     `query_stored_for_consumer`). None of them broadcasts: the remote publisher already did.
   - `VectorStoreService` gains port-shaped methods (`create_collection`, `store_documents`, `search`,
     `update_vector`, `delete_vectors`, `list_vectors`) that take the port's arguments as given. Its
     convenience methods validate, then call them; the NATS endpoints call them directly, so the port's
     contract holds over NATS.
   - `SingleTierCacheService` gains `put_entry` and `put_entry_if_absent`. Each `tier.<index>` subject
     serves `CacheService.tier_at(index)`, by position, since two tiers may share a name.
   - The services emit the mutation audit events, once. The primaries no longer take an event publisher.

## Consequences

- **A domain service can read who calls with `current_call_context()`,** whatever the transport. A test
  checks that every kernel service sees the same context in process, through the core client and through
  the SDK transport.
- **Nothing is authorized yet.** Every caller that worked still works. The only new refusal is a user named
  by an untrusted identity, which no existing caller sends.
- **Events published by the engine for a NATS call now carry the user** the caller acted for, and its target
  workspace. Before, they carried no actor.
- **Events published during a Nexus request opened with a link token, or a revoked token, carry no actor.**
  Before, any token signed with the Nexus key labelled them with its `sub`.
- **Remote vector store calls keep the port's contract.** A remote `close` resets the service's
  initialization instead of leaving it holding a closed adapter.
- **Sync engine clients keep the caller.** `nats_runtime.run_coro` schedules through
  `run_coroutine_threadsafe`, whose callback handle copies the calling thread's context, so a coroutine run
  for a sync caller (the model registry client) sees that caller. A test drives that path.
- **Stage 1 tokens carry no audience, `jti`, groups or narrowing.** Those fields stay empty until step 6
  issues ES256 engine tokens. Step 8 replaces the header with delegated tokens and removes it.
