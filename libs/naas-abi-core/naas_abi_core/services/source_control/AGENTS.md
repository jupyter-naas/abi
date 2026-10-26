# SourceControl Service - AGENTS.md

## Purpose

Manage repositories, files, branches, proposals, reviews, and checks through interchangeable providers.

## Files

- `SourceControlPorts.py`: port, value types, and domain errors.
- `SourceControlService.py`: service orchestration and event publication.
- `SourceControlFactory.py`: composition helpers.
- `adapters/primary/`: NATS RPC server.
- `adapters/secondary/`: local/provider implementations and NATS RPC client.
- `tests/`: generic adapter contract tests.

## Port

Implement every abstract method of `ISourceControlAdapter` in `SourceControlPorts.py`.
Keep provider dependencies in secondary adapters and preserve typed domain errors.

Platform admin operations (the Nexus System app uses them): `delete_repo(repo_id=...)`
removes a repository irreversibly (RepoNotFoundError when missing; Forgejo
`DELETE /repos/{owner}/{repo}`, local git removes the checkout). Delete a file with
`upsert_files([FileWrite(path, b"", delete=True)], ...)`: one commit, and the
`delete` flag crosses NATS (`FileWrite.delete`, field 4).

## Service API

`SourceControlService(adapter)` authorizes each operation (below), delegates to the port and publishes domain events.
See its public methods for orchestration beyond the adapter contract.

## Authorization

Every operation is checked inside `SourceControlService` (`iam_catalog.py`)
once the service is wired with IAM, so in-process and NATS callers are checked
alike. A NATS facade is not wired and checks nothing itself: the owner it calls
does. The guard is described in [`services/iam/AGENTS.md`](../iam/AGENTS.md)
("Enforcing in a domain service").

Actions by resource (the NATS subject is the operation under
`abi.svc.source_control.v1.`, in snake case: `UpsertFile` is `upsert_file`):

| Level | Action: resource |
|---|---|
| list | `ListRepos`: each `repo`; `ListContents`, `ListCommits`, `ListWorkflowRuns`: `repo`; `ListBranches`: each `branch`; `ListProposals`: each `proposal`; `ListProposalCommits`, `ListComments`, `ListReviews`, `ListChecks`: `proposal` |
| read | `GetFile`, `GetDiff`: `repo`; `GetProposal`, `GetProposalDiff`: `proposal` |
| write | `EnsureRepo`: `repo` (creates; `create_repo` is the same action); `UpsertFile`, `UpsertFiles`: `branch/<repo>/<branch>`; `CreateBranch`, `DeleteBranch`: `branch`; `CreateProposal`: `proposal/<repo>/-` (creates); `AddComment`, `SubmitReview`, `Merge`: `proposal`; `MintGitToken`: `forge_user/<principal>` |
| admin | `DeleteRepo`, `AddCollaborator`: `repo`; `SetBranchProtection`: `branch`; `EnsureUser`: `forge_user/<principal>` |

- **Resources.** `repo/<owner>%2F<name>` is a placed container (the service's id,
  never a Nexus value); its branches `branch/<repo>/<name>` and proposals
  `proposal/<repo>/<number>` take its placement. `forge_user/<principal id>` is
  personal.
- **The principal is the call's**, never a request field: the call's user, or the
  actor when the call is on behalf of no one. `ensure_user` binds the forge user to
  it (`ISourceControlAdapter.find_user`, persisted by Forgejo in the user's local
  `login_name`); a username bound to another principal is refused
  (`AccessDeniedError`). `mint_git_token` mints for that forge user only:
  `user_id` and `external_id` in requests are ignored. Every user holds
  `EnsureUser` and `MintGitToken` on their own forge user (`builtin.self`).
  An existing forge account is the caller's only when it is bound to it, or
  when it predates the binding (its `login_name` is empty or its own login), a
  first party (`api`, `engine`: `vouched_by_first_party()`) vouches for the
  email it carries and it is the account's email, and the caller has no account
  yet; an account bound to another principal is never handed over, and neither
  is an administrator. One principal has one forge account: a new username renames it.
- **IAM names a repository by its lowercase id** (`repo_key`), because forges
  look repositories up case-insensitively.
- **`ensure_repo`** applies the create rule (see `services/iam/AGENTS.md`): placed in the call's target
  workspace (exact id and `<id>/*`), on the platform without one. A repository that
  exists with no placement predates IAM and is recorded on the platform, so no
  workspace can claim it. A target workspace IAM has no scope
  for places the repository on the platform. `delete_repo` drops its placements.
- **`create_repo` is create-only.** Unlike `ensure_repo` it never hands back a
  repository that exists (`RepoExistsError`, for one with that id in any
  letter case) and places nothing then, so a caller that places or grants access
  to what it gets back knows it created it. A repository's owner and name are
  plain segments (letters, digits, `.`, `_`, `-`); any other id is not found.
- **`add_collaborator` is `AddCollaborator`, an admin action.** Nexus grants a member
  write on a workspace repository after its own check, as `api`
  (`apps/nexus/.../coding_environment/repo_access.py`): only when the repository is
  placed in the route's workspace (or is the deployment's shared repository), the
  caller's role there is member or above, and IAM allows `source_control:UpsertFile`
  for them. Another workspace's repository answers as a missing one.
- Lists (`list_repos`, `list_branches`, `list_proposals`) keep the items the caller
  may list; branch and proposal lists first need the repository to be visible.
- Wire codes `PERMISSION_DENIED` and `NOT_FOUND`; an invisible repository, branch
  or proposal is `REPO_NOT_FOUND`, `BRANCH_NOT_FOUND`, `PROPOSAL_NOT_FOUND`.
- Audit events go through `EventService.emit`.
- Tests: `tests/source_control_authorization_test.py` (the `AuthorizationContract`
  for `GetFile` and `AddCollaborator`, forge-user binding, placement, lists).

## Adapters

ForgejoAdapter, LocalGitAdapter, InMemoryAdapter, plus `SourceControlSecondaryAdapterNATSClient`.
Unsupported methods must explicitly raise `NotImplementedError`.

## Factory

Use `SourceControlFactory` for the existing provider composition helpers.
Engine configuration can also construct adapters, including `nats_rpc`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/source_control/ --import-mode=importlib
```

## Adding a new adapter

1. Implement the complete port with constructor-injected configuration.
2. Add colocated tests and run the generic adapter contract tests.
3. Add the relevant factory/configuration wiring.

## NATS RPC adapters

`adapters/primary/source_control__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/SourceControlSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/source_control/v1/`.

A `NotImplementedError` in the wrapped adapter crosses NATS as the non-retryable
code `UNIMPLEMENTED` and is raised again as `NotImplementedError` by the client.
`adapters/secondary/SourceControlSecondaryAdapterNATSClient_broker_test.py` runs the
admin operations against a local `nats-server` (no Docker).

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and target workspace come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and workspace. The domain service then authorizes the call (see "Authorization").

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB; above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
