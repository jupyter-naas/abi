# Workflows domain

Durable workflows over REST at `/api/workflows`, for scripts (`Authorization: Bearer <ABI_API_KEY>`) and super admins. A workflow is a job with `kind="workflow"`, typed input and output schemas and a journal of steps: it runs on the jobs runtime and shows in the System → Jobs tab. This domain is a thin use-case layer over [`sysadmin`](../sysadmin/AGENTS.md)'s jobs admin, which owns the ports (catalogs, run records, steps, control, audit, input validation) and their adapters; read its Jobs section first.

## Layout

- `workflows.py`: values (`Caller`, `WorkflowList`, `WorkflowRunView`, `Started`), `MAX_WAIT_SECONDS` (120) and the idempotency key check (at most 200 printable ASCII characters).
- `service.py`: `WorkflowsService(jobs: JobsAdminService)`.
  - `list`: the workflows of every catalog, with schemas and triggers, and how each source answered.
  - `start`: `JobsAdminService.trigger(workflow_only=True)`: the input is checked against the input schema (`InvalidInput`, nothing audited or sent), the start is audited, then the trigger is sent with the idempotency key. `wait` (seconds) then reads the run record, quickly at first and about once a second after, until the run is terminal or the time is up; the run goes on either way, and a run store failing mid-wait answers with what was last known.
  - `status`: the run's record with its whole result and its steps. A run no host has recorded yet reads as QUEUED when its workflow exists; a plain job's run, an unknown workflow or a malformed id is `RunNotFound`.
  - `cancel`: `JobsAdminService.cancel(workflow_only=True)`: audited, cooperative; a cancelled parent cancels the children it waits for (the SDK does that).
- `adapters/primary/workflows__primary_adapter__FastAPI.py`: the router (`handlers/` re-exports it, mounted in `app/api/router.py`).
- `factory.py`: `get_workflows_service` (one per API process, over `get_jobs_admin`).

## HTTP

Access is `require_superadmin_or_api_key` (`services/auth/.../auth__primary_adapter__dependencies.py`) on the router: the `Authorization: Bearer` header only, never a query parameter or a cookie. The key is the instance's shared key and stands for the operator; no valid key means the session rules of `require_superadmin` (401 without one, 403 for a user who is not a super admin). `main_public_routes_test.py` fails if a route loses it.

| Route | Answer |
|---|---|
| `GET /api/workflows` | `{workflows: [{key, module_id, name, description, location, instances, kind, input_schema, output_schema, max_concurrency, max_attempts, timeout_seconds, triggers: [{kind, spec, time_zone, input}]}], sources}` |
| `POST /api/workflows/{module_id}/{name}/runs` | The body is the input (a JSON object; empty is `{}`). 202 with the run (`status` QUEUED) or, with `?wait=<seconds>` (0 to 120) and a run that ended in time, 200 with its status, `result` and `steps`. `Idempotency-Key` makes a repeated start the same run (two minutes); it is a header-safe string, else 422. 404 when the name is a plain job or unknown. 422 `{source, reason, errors: [{path, message}]}` (JSON pointers) when the input does not match the schema. |
| `GET /api/workflows/{module_id}/runs/{run_id}` | `{key, module_id, workflow, run_id, status, attempt, max_attempts, fired_at, started_at, finished_at, duration_ms, error, trace_id, result, steps: [{key, kind, status, attempt, started_at, finished_at, duration_ms, error, child: {module_id, workflow, run_id, key} \| null, result_bytes}], steps_truncated}` |
| `POST /api/workflows/{module_id}/runs/{run_id}/cancel` | 202 `{ok: true}`; 409 when the run is not running; 404 for a plain job's run. |

A run's `status` is QUEUED, RUNNING, RETRYING, SUCCEEDED, SKIPPED, FAILED, TIMED_OUT or CANCELLED; a failed run answers 200 on `?wait` with its `status` and `error`: check `status`.

- Starts and cancels are audited exactly like the Jobs tab's (service `jobs`, operations `trigger` / `cancel`, resource `<module>/<workflow>` or `<module>/<run id>`), with `via` = `user` or `api_key`. A key caller has no user id: `audit_logs.user_id` is NULL and `details.via` = `api_key`. If the audit record cannot be written (503 `audit`) nothing is started or cancelled; a refused input is not audited, because nothing is triggered.
- Errors name their source: `{"detail": {"source", "reason"}}`: `workflows` (404, 409, 422), `audit`, `jobs` (the broker), `runs` and `steps` (the document service) for a 503.

```bash
curl -s -H "Authorization: Bearer $ABI_API_KEY" "$NEXUS/api/workflows"
curl -s -H "Authorization: Bearer $ABI_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: import-2026-10-02" -d '{"filter": "news"}' \
  "$NEXUS/api/workflows/acme.tweets/tweets/runs?wait=30"
curl -s -H "Authorization: Bearer $ABI_API_KEY" "$NEXUS/api/workflows/acme.tweets/runs/tweets:12"
curl -s -X POST -H "Authorization: Bearer $ABI_API_KEY" "$NEXUS/api/workflows/acme.tweets/runs/tweets:12/cancel"
```

## Tests

- `service_test.py`: audit with each caller, refused input, `wait` (fake clock), QUEUED reads, cancel.
- `adapters/primary/workflows__primary_adapter__FastAPI_test.py`: every route for a super admin, the API key, a user who is not one (403) and no credentials (401), over in-memory adapters.
- `sysadmin/adapters/secondary/jobs_integration_test.py` runs the service over the real adapters and an SDK job host on `nats-server -js`.
- Run: `uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/workflows libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/sysadmin`.
