# The runtime services enforce IAM in their domain services

Status: Accepted

Date: 2026-10-15

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §4.4, §5, §6.4 and §10.
Builds on: [`20261013_iam-kernel-service.md`](20261013_iam-kernel-service.md), [`20261015_iam-transitional-bootstrap.md`](20261015_iam-transitional-bootstrap.md), [`20261015_caller-identity-call-context.md`](20261015_caller-identity-call-context.md).

## Context

Subtask 5 of #44 makes the runtime services authorize every operation: event, activity_log, email,
model_registry, discovery (agents, models, apps, jobs), source_control and coding_environment. Before it:

- discovery let anyone invoke a READY agent, model or app, and its admin operations were hard-coded to the
  `api` and `engine` identities;
- remote agents ran as the shared `api` identity, so every Nexus user's runs had one owner;
- source_control and coding_environment took the user from the request (`mint_git_token(user_id=…)`);
- Nexus granted write on any client-supplied repository to any workspace member (bug (b));
- engine boot, CLI commands, Dagster runs and several Nexus background tasks ran with no caller, which
  IAM denies.

## Decision

1. **One guard per service, in the domain service.** `services/iam/guard.py` (`ServiceGuard`) builds
   canonical names placed by IAM, requires an action, filters lists (limits apply after filtering), applies
   the create rule of §4.4 and records placements as `engine`. Each service's catalog sits in
   `services/<name>/iam_catalog.py` and is registered at boot (`kernel_catalogs.py`).
2. **The owner checks, once.** A domain service checks when it is wired with IAM. Owners always are; the
   NATS facades of the dependency container and of client engines are not. A remote call is therefore
   checked once, by its owner, with the caller the request's credentials name. In process and over NATS
   give the same outcome and the same errors (`PERMISSION_DENIED`, the service's own not-found), which a
   generic contract test pins for every service (`services/iam/tests/authorization_contract.py`).
3. **Placement of new resources.** A create targeting a workspace places the resource there through
   `iam.workspace_org`. Until #65 registers Nexus's workspaces with `iam:PutScope`, a target workspace IAM
   has no scope for places the new resource on the platform (TRANSITIONAL). A name an existing placement
   covers keeps it, and a mismatching target workspace is refused.
4. **Kernel audit events are the engine's.** `EventService.emit` stamps the call's user, workspace and
   trigger, then appends as `engine` and never raises. The caller was authorized for the operation, not for
   writing the event log. `publish` stays the caller's, checked with `event:Append`.
5. **Every in-process entry point has an identity.**
   - `Engine.load` and the core API's boot run as `engine`.
   - `abi chat` and `abi run` run as `engine` for the local operator, keeping the terminal's identity on
     the events they record.
   - Dagster bodies run as `engine` (`as_engine`).
   - Nexus housekeeping (startup tasks, the identity-graph sync, the chat ingestion job) runs as `api`.
   - A verified `ABI_API_KEY` holder calls as `api` (TRANSITIONAL until #62 gives API keys their own
     service accounts).
   - Thread hops copy the caller's context; agent runs carry it to their tools, so platform tools act for
     the user who is chatting.
6. **Discovery checks the caller, not the provider.** A hosting module forwards its caller's token and
   `Abi-On-Behalf-Of` header in the `Authorize*` requests. Discovery builds the caller's context exactly as a
   kernel endpoint does and checks `InvokeAgent`, `GetAgentRun`/`CancelAgentRun` on the run, `ChatModel` or
   `OpenApp`. The lease checks stay. A run belongs to the call's user, else the actor. `caller_admin` is
   deprecated: the host relies on discovery's decision.
7. **Module names are bound to principals.** A module id is held by the principal of its live instances,
   and a `module/<project>/<module_id>` account (#60) registers only its own module. A strict
   "token subject equals module id" rule would break every existing module, whose generated ids are
   `<project>.<name>`. Renewing or unregistering an instance needs its lease. Until #60, a module id that
   nobody holds can still be registered by any module. `Evict` is a policy, `discovery:Evict`; the
   transitional module policy denies it, and a discovery with no IAM lets only `api` and `engine` evict.
8. **Jobs.** A manual trigger or a cancel carries its caller's credentials in the stored message. The job
   host asks discovery (`authorize_job`) before running it, with the token checked as of the time JetStream
   stored the message, since a trigger may be consumed after its token expired. Engine-hosted jobs run the
   same check in process. Scheduled and event triggers are the host's own and are trusted until #60's
   broker permissions restrict who may publish on trigger subjects.
9. **Models.** Resolving needs `Resolve` and lists are filtered by `ListModels`. In process, each chat
   invocation needs `Chat` in the invoking call's context, through a callback on the models the registry
   hands out, so an agent built at boot is still checked per user. Over NATS, `Chat`, `ChatStream` and
   `Embed` are checked per call. An in-process embedding is checked as `Resolve`.
10. **The user comes from the call.** source_control and coding_environment derive the user from the
    `CallContext` and find the forge or orchestrator account by the principal it was ensured for. Request
    `user_id` fields are ignored. `AddCollaborator` is an admin action. An existing forge or Coder account
    is the caller's only when bound to it, or when it predates the binding and a first party (`api`,
    `engine`) vouches for the email it carries; an administrator is never handed over.
11. **Bug (b).** Nexus grants write on a repository only when it is placed in the route's workspace (or is
    the deployment's configured shared repository), the caller's role there is member or above, and IAM
    allows `source_control:UpsertFile` for them. The grant itself runs as `api`. Another workspace's
    repository answers as a missing one. A repository is created with `create_repo`, a create-only
    operation that fails for one that exists in any letter case (forges look names up case-insensitively),
    and IAM names repositories by their lowercase id: Nexus places and grants only what it just created.

## Consequences

- A principal with no policy is denied by every runtime service, in process and over NATS alike, and cannot
  invoke a remote agent, model or app, or trigger a job.
- Nexus users keep working through `builtin.transitional.nexus_user` until #65 attaches their roles. Their checks
  are real only where Nexus binds a resource to a workspace itself (bug (b)), or under an explicit Deny.
  Users with IAM ids get real checks today.
- Activity log actors are principal ids (a Nexus id, `usr_…`, or a service-account name) instead of
  `user:<id>`. The System app reads both.
- Stage 1 caller tokens are stored inside job trigger messages. #60 and #62 should replace them with
  narrow delegated grants.
- Remaining work lands elsewhere: the data services switch their audit events to `emit` (#58); Nexus
  environment routes check ownership once roles are attached (#65); the transitional grants are removed
  (#60, #65).
