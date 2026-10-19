# Delegated tokens, token exchange and personal API keys

Status: Accepted

Date: 2026-10-19

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §8.1, §9.3, §9.4 and §10.2.
Builds on: [`20261013_engine-tokens-service-accounts-broker.md`](20261013_engine-tokens-service-accounts-broker.md), [`20261015_caller-identity-call-context.md`](20261015_caller-identity-call-context.md), [`20261015_runtime-services-enforce-iam.md`](20261015_runtime-services-enforce-iam.md), [`20261015_nexus-oidc-sessions.md`](20261015_nexus-oidc-sessions.md).

## Context

Step 8 makes every narrow credential an engine-signed token derived from an identity that was
already verified, with an audience of its own, so that none of them is ever read as a session. Before it:

- the coding-agent token was an HS256 session token with no scope and a 30-day life, minted in four
  places, and it opened every `/api/*` route as the user (the rest of bug (a));
- app-html links, preview tokens and remote app grants were signed with keys derived from `secret_key`,
  could not be revoked, and lived up to 24 hours;
- Nexus called remote agents, apps and jobs as the shared `api` identity, naming the user in the transitional
  `Abi-On-Behalf-Of` header, which the kernel trusted from `api` and `engine` without any check, and the live
  `api` token reached every module Nexus called;
- `revoke_all_user_tokens` revoked refresh tokens only, and the `api_keys` table was a client-side mock.

## Decision

1. **One mechanism: RFC 8693 token exchange in IAM** (`IAMService.exchange_token`, `abi.iam.v1.exchange_token`,
   `services/iam/exchange.py`). The subject is a verified identity: an IdP ID token (`abi:session`), a signed-in
   user a first party (`api`, `engine`) vouches for (Nexus names its users this way, because its sessions are
   not engine tokens), an engine token, a personal key (`abi_pk_`) or a link grant (`abi_gk_`). The output is a
   token of at most ten minutes with one audience: `abi:session` or `abi:delegated:{agent,app,preview,coding,api-key}`.
   An exchange only narrows: a session reaches every delegated audience, never the reverse; a delegated token
   never becomes another one; a key reaches its own audience only; a scope (`abi_scope`) narrows and is not
   narrowed twice. The requester needs `iam:ExchangeToken` on the audience; only `api` and `engine` hold it.
2. **The `Abi-On-Behalf-Of` header is removed.** A caller acting for a user sends an `abi:delegated:agent` token:
   `sub` the user, `act` the acting service (with its account name). Kernel endpoints accept `abi:nats` and this
   audience, build the context from it exactly as before (principal = actor, on behalf of = user) and refuse a
   request that still carries the header. `NatsRPCClient` and the SDK `Transport` of `api` and `engine` obtain
   the token from a delegate (`RenewingTokenSource.token_for`, cached per user, scope and recipient); one that
   cannot get a delegation fails the call and never calls as the account alone, which would drop the user.
3. **The actor of a call to a module is the module.** Nexus's transports name the module behind the host being
   called, so the host holds a token good for that module acting for that user, ten minutes, and nowhere else;
   never `api`'s own token. Discovery accepts such a token only from the host whose account it names, and the
   module's own side of the check (`builtin.module_bootstrap`: `OwnHosted`, `OwnRuns`) lets it serve what it
   hosts, without opening a broker subject (the broker turns an `InvokeAgent` grant into every agent subject of
   the project, so these statements are kept out of the derivation, `roles.DELEGATION_SIDS`).
4. **A run outlives its token by renewing it.** `SubmitRequest.delegated_token` hands the run its delegation; the
   host keeps it only if it names the run's owner and runs the invocation in a call context that carries it.
   The SDK sends it, in place of the module's own token, on the kernel calls the run makes for the user, and
   renews it through the module's service key: the module exchanges its own delegation (same audience, an
   expired one too) until eight hours after it began (`abi_since`). Job triggers store a host token that names
   the user (`sub`) and the caller (`act`), addressed to the job's host alone.
5. **Links are IAM grants** (`kind=grant`, `abi_gk_`): of the user who opened them, for the audience app or
   preview, bound to what they open (`resource`), narrowed to what opening needs (`scope`: `discovery:OpenApp` on
   that app, or nothing), stored hashed, eight hours at most, revocable, ended with their owner. Each request
   that presents one asks IAM again, so revocation is immediate. This replaces the `secret_key`-derived HS256
   links; no secret of Nexus signs a link any more.
6. **A coding environment's agent holds a personal key** of its owner, made for it (audience
   `abi:delegated:coding`), bound to its sidecar, narrowed to its workspace, revoked with the environment. The
   OpenAI gateway (`/api/v1/*`) is the only route that takes it, and finds the exec sidecar from the key's
   `resource` and the `coding_environments` row, never from a claim a client could supply. The 30-day session
   token is gone from all four mint sites.
7. **Personal API keys** (`abi_pk_`, `audience=api-key`) live in IAM's key table: hashed, five active, required
   expiry of a year at most, revocable, scoped (read-only, or statements of the owner's writing, never beyond the
   owner's policies). Nexus manages them for the signed-in user (`/api/iam/api-keys`, session-only) and exchanges
   them for scripts (`POST /api/iam/token`, `client_credentials`); the Nexus `api_keys` table is replaced by
   IAM's. The engine's own HTTP routes (`/agents`, `/pipelines`, `/workflows`, `/tools`) take the deployment's
   `ABI_API_KEY` and nothing else: they run an agent, pipeline, workflow or tool and make no IAM decision of their
   own (only the core-service calls made further down are checked), so a personal key's limit and its owner's
   policies would not bound the invocation, nor what it does with the deployment's credentials. Neither
   personal nor service keys are accepted there until those routes enforce IAM (step 11); a service key still
   serves its account over NATS.
8. **Nexus reads a credential's kind from its audience and honours it where it belongs**
   (`services/auth/credentials.py`): a session everywhere and on the WebSocket; an API key on `/api/*` but the
   account and the key management (`/api/auth/`, `/api/iam/`); a coding key at the gateway. Nexus's own session
   token carries `aud=abi:session` and `decode_token` returns that and nothing else, so every token the secret
   once signed for another purpose is refused.
9. **Revocation.** `revoke_tokens(principal)` sets a floor: every token of the principal issued at or before it
   is refused, by the verifier and by the authorizer (a context whose `token_issued_at` is at or before it is
   suspended); its grants and coding keys are revoked, its API keys with `include_keys`. A token made after the
   floor carries a later `iat`. `revoke_all_user_tokens` calls it. Suspension denies a principal's tokens at
   once, as before.
10. **Groups in a token are only groups.** `grp` ids that are not active groups are ignored (step 3 review): the id
    of a user or an account never lends its policies.

## Consequences

- Nothing that is not a session can be a session: tests refuse a coding key, an app-html link, a preview link, a
  remote app grant and an agent delegation on `/api/*` and on the WebSocket, and a call from Nexus to a remote
  agent is decided as that module for that user.
- `Abi-On-Behalf-Of` is gone from the clients, the hosts, discovery, the job triggers and the proto
  (`caller_on_behalf_of` is reserved). A module still sending it is refused with a message that says why.
- Sessions Nexus signed before sessions had an audience stop working at upgrade, as does every earlier link,
  preview token and coding token: users sign in again, links are reopened, environments are reprovisioned or
  their key is remade. This is a major release.
- A key narrows what the kernel allows; Nexus's own routes still decide by role until step 11 puts them on IAM, so
  an API key's scope does not yet narrow a Nexus-only route. The scope travels with every call the key makes,
  in process and over NATS.
- IdP groups (`grp`) travel with a session; a personal key carries none (it is not a session), so what a user
  holds only through an IdP group claim does not reach their API keys until it is a stored membership (step 10).
- `ABI_API_KEY` stays as the one credential of the engine's invocation routes until they enforce IAM (step 11);
  scripts that call Nexus use a personal key on `/api/*`, and scripts that call the kernel use a service key
  over NATS.
- `api` and `engine` must keep `iam:ExchangeToken` when step 11 enumerates their policies.
- The delegation cache holds a token per user, scope and recipient for half its life (at most 2048); a
  delegation for a suspended user is refused at issue, and an issued one is denied at the next check. The
  exchange that makes or renews one runs outside the source's lock (it calls IAM, which calls with the source's own
  token), and a delegation that cannot be renewed fails the call: the held token is not handed out on the
  strength of an exchange that no longer says yes.
- A key's limit (`abi_scope`) travels the whole way: with a NATS stream (captured with its user when the stream
  opens, read by whichever thread reads the frames) and into the host token stored with a job trigger, so what
  a job runs for the user stays within what the key may do.
- A session token Nexus signs right after the user's tokens were revoked (a password change signs them in again in
  the same second) gets an `iat` at the first second the floor lets through, not the second it was made in.
- A key may be exchanged without naming an audience (`audience=""`, key subjects only): the token is the one of
  the key's own audience, so a caller that cannot tell an API key from a coding key authenticates it once. The
  requester then needs `iam:ExchangeToken` on every audience (`api` and `engine` do).
- Links are IAM grants and are made at every click: making one forgets the user's links that expired or were
  revoked more than a day ago (`IAMStore.delete_keys`), and the limit of 1000 live links is a refusal
  (`LinkLimitReached`, answered 429 by the routes), not a server error.
- `app_html_access_token_expire_minutes`, `app_preview_token_expire_minutes` and `remote_app_grant_expire_minutes`
  keep their old ceiling of a day, so a deployment that set more than eight hours still boots; the link made is
  clamped to eight hours.
- A module host carries a delegation only when it names the host's own account as the actor.
