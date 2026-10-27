# Workflows domain

Durable workflows over REST: at `/api/workflows` for platform admins and their scripts, and at
`/api/workspaces/{workspace_id}/workflows` for any user of a workspace, by module scope ("In a workspace" below). At `/api/workflows`, for platform admins and their scripts (`Authorization: Bearer abi_pk_...`, a personal API key). A workflow is a job with `kind="workflow"`, typed input and output schemas and a journal of steps: it runs on the jobs runtime and shows in the System → Jobs tab. This domain is a thin use-case layer over [`sysadmin`](../sysadmin/AGENTS.md)'s jobs admin, which owns the ports (catalogs, run records, steps, control, audit, input validation) and their adapters; read its Jobs section first.

## Layout

- `workflows.py`: values (`Caller`, `WorkflowList`, `WorkflowRunView`, `Started`), `MAX_WAIT_SECONDS` (120) and the idempotency key check (at most 200 printable ASCII characters).
- `service.py`: `WorkflowsService(jobs: JobsAdminService)`.
  - `list`: the workflows of every catalog, with schemas and triggers, and how each source answered.
  - `start`: `JobsAdminService.trigger(workflow_only=True)`: the input is checked against the input schema (`InvalidInput`, nothing audited or sent), the start is audited, then the trigger is sent with the idempotency key. `wait` (seconds) then reads the run record, quickly at first and about once a second after, until the run is terminal or the time is up; the run goes on either way, and a run store failing mid-wait answers with what was last known. Run ids reuse stream sequences, so a record fired before the start (by more than `CLOCK_SKEW`, 30 s, plus `DUPLICATE_WINDOW`, 2 minutes, when an idempotency key was sent: a repeat answers with the first start's run) is an old run under a reused id, after the jobs stream was recreated: the start reports QUEUED instead, with and without `wait`.
  - `status`: the run's record with its whole result and its steps. A run no host has a record of (pruned, mistyped, not taken yet) is `RunNotFound` (404), as are a plain job's run, an unknown workflow and a malformed id; only `start` reports the run it just started as QUEUED before a host records it.
  - `cancel`: `JobsAdminService.cancel(workflow_only=True)`: audited, cooperative; a parent that ends cancelled, timed out or failed for good cancels the children it waits for (the SDK does that).
  - `start_in`, `own_run`, `own_runs`: a start from a workspace, recorded as the caller's there (`port.py` `RunOwnersPort`), and the runs a user started there.
- `port.py`: `RunOwner`, `RunOwnersPort`; `WorkflowSwitch`, `WorkflowVisibilityPort` (on or off per workspace); `adapters/secondary/sql.py` (`workflow_run_owners`, migration `0063`; `workflow_visibility`, migration `0064`) and `in_memory.py`.
- `visibility.py`: `WorkflowsVisibility`, the reader `services/visibility` asks for workflows and pipelines: one switched off is refused when used.
- `scopes.py`: `workflow_scope(module_id, name)`: a `pipeline.<slug>` is a pipeline, any other a workflow.
- `adapters/primary/workflows__primary_adapter__FastAPI.py`: `router` and `workspace_router` (`handlers/` re-exports both, mounted in `app/api/router.py`).
- `factory.py`: `get_workflows_service` (one per API process, over `get_jobs_admin` and the SQL run owners), `get_workflow_visibility`.

## HTTP

Access is `require_superadmin` (`services/auth/.../auth__primary_adapter__dependencies.py`) on the router: IAM decides `nexus:ReadSystem` for a read and `nexus:ManageSystem` for a start or a cancel, which only `builtin.platform_admin` holds. A script sends its user's personal API key (`abi_pk_`, made in Nexus under Account, API keys) as `Authorization: Bearer`: it is that user, bounded by the key's own scope. 401 without a credential, 403 for a user IAM refuses. `main_public_routes_test.py` fails if a route loses it.

| Route | Answer |
|---|---|
| `GET /api/workflows` | `{workflows: [{key, module_id, name, description, location, instances, kind, input_schema, output_schema, max_concurrency, max_attempts, timeout_seconds, triggers: [{kind, spec, time_zone, input}]}], sources}` |
| `POST /api/workflows/{module_id}/{name}/runs` | The body is the input (a JSON object; empty is `{}`). 202 with the run (`status` QUEUED) or, with `?wait=<seconds>` (0 to 120) and a run that ended in time, 200 with its status, `result` and `steps`. `Idempotency-Key` makes a repeated start the same run (two minutes); it is a header-safe string, else 422. 404 when the name is a plain job or unknown. 422 `{source, reason, errors: [{path, message}]}` (JSON pointers) when the input does not match the schema. |
| `GET /api/workflows/{module_id}/runs/{run_id}` | `{key, module_id, workflow, run_id, status, attempt, max_attempts, fired_at, started_at, finished_at, duration_ms, error, trace_id, result, steps: [{key, kind, status, attempt, started_at, finished_at, duration_ms, error, child: {module_id, workflow, run_id, key} \| null, result_bytes}], steps_truncated}` |
| `POST /api/workflows/{module_id}/runs/{run_id}/cancel` | 202 `{ok: true}`; 409 when the run is not running; 404 for a plain job's run. |

A run's `status` is QUEUED, RUNNING, RETRYING, SUCCEEDED, SKIPPED, FAILED, TIMED_OUT or CANCELLED; a failed run answers 200 on `?wait` with its `status` and `error`: check `status`.

- Starts and cancels are audited exactly like the Jobs tab's (service `jobs`, operations `trigger` / `cancel`, resource `<module>/<workflow>` or `<module>/<run id>`), with the user and `via` = `user` (a session) or `api_key` (their personal key, `details.via`). If the audit record cannot be written (503 `audit`) nothing is started or cancelled; a refused input is not audited, because nothing is triggered.
- Errors name their source: `{"detail": {"source", "reason"}}`: `workflows` (404, 409, 422), `audit`, `jobs` (the broker), `runs` and `steps` (the document service) for a 503.

```bash
# ABI_PK: a platform admin's personal API key (abi_pk_...)
curl -s -H "Authorization: Bearer $ABI_PK" "$NEXUS/api/workflows"
curl -s -H "Authorization: Bearer $ABI_PK" -H "Content-Type: application/json" \
  -H "Idempotency-Key: import-2026-10-02" -d '{"filter": "news"}' \
  "$NEXUS/api/workflows/acme.tweets/tweets/runs?wait=30"
curl -s -H "Authorization: Bearer $ABI_PK" "$NEXUS/api/workflows/acme.tweets/runs/tweets:12"
curl -s -X POST -H "Authorization: Bearer $ABI_PK" "$NEXUS/api/workflows/acme.tweets/runs/tweets:12/cancel"
```

## In a workspace

`/api/workspaces/{workspace_id}/workflows` is open to the users of the workspace (`nexus:GetWorkspace`) and decided item
by item by module scope (core `services/iam/AGENTS.md`, "Module scopes"): `workflow/<module>/<name>` or
`pipeline/<module>/<name>` of the `module` catalog. Viewers and members hold none by default; admins and owners hold
all.

| Route | Answer |
|---|---|
| `GET ""` | The workflows and pipelines of the workspace's set the caller may start there (`module:RunWorkflow` / `RunPipeline`), as `GET /api/workflows` lists them, each with its `type`; one turned off there is left out. |
| `POST /{module_id}/{name}/runs` | As the platform route, for the caller: 403 without the scope. The run is recorded as theirs in this workspace; an `Idempotency-Key` is theirs alone (hashed with the workspace and the user). |
| `GET /runs` | `{runs: [{module_id, workflow, type, run_id, started_at}]}`: the runs the caller started here (50, newest first), of what they may still read (`ReadWorkflowRuns` / `ReadPipelineRuns`). |
| `GET /{module_id}/runs/{run_id}` | A run the caller started here, as the platform route answers it; 404 for any other run (another user's, another workspace's, an old run under a reused id), 403 without `Read*Runs`. |
| `GET /settings` | Workspace settings › Workflows (`nexus:ListWorkflowSettings`, admins): `{workflows: [{type, module_id, name, display_name, description, enabled}]}`, every workflow and pipeline of the set, the jobs catalogs' and those an engine module's agents run as tools (`modules/scopes.workflows`), off ones included; never filtered by the caller's own right to run each one (a Deny on running them, or a group granted only the settings actions, still lists and switches them). |
| `PUT /settings` | `{type, module_id, name, enabled}` (`nexus:UpdateWorkflow`, admins): on or off for everyone in the workspace. Turning one on outside the set is 403; off, always. |

**On or off.** One never switched is on. One switched off is refused to everyone in the workspace (403 "This
workflow is turned off in this workspace"): listing, start, an agent's tool (`services/visibility`, asked by
`authz` after IAM allows its use). The runs already started stay listed and readable (`/runs`, `/{module}/runs/{id}`):
turning a workflow off refuses starting it, not reading results someone has.

A start runs for the caller: the request's context names them (`identity_events/middleware.py`), and the job's host
checks `discovery:TriggerJob` for them, which members hold on every module's workflows (`workflow/*`, never a plain job); the module scope is what tells workflows apart.
There is no cancel here: a run is cancelled from the System tab.

## Tests

- `service_test.py`: audit with each caller, refused input, `wait` (fake clock), QUEUED only for a just-started run, cancel.
- `adapters/primary/workflows__workspace_routes_test.py`: the workspace routes by role and by grant (one workflow, one pipeline), own runs, idempotency keys per user, the set limiting the listing, the settings (by role, off refused for everyone, nothing outside the set turned on); `adapters/secondary/sql_test.py`: the run owners table.
- `adapters/primary/workflows__primary_adapter__FastAPI_test.py`: every route for a platform admin (session and personal key), a user who is not one (403) and no credentials (401), decided by a real IAM (`conftest.py`), over in-memory adapters.
- `sysadmin/adapters/secondary/jobs_integration_test.py` runs the service over the real adapters and an SDK job host on `nats-server -js`.
- Run: `uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/workflows libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/sysadmin`.
