---
sidebar_position: 2.5
title: "Observability"
---

# Observability

Kernel services, remote modules, agents and jobs talk over NATS, often across
several processes. ABI gives operators one place to see what runs and what each
call does: the Nexus **System** app, backed by named NATS connections, an error
header on every failed call, and OpenTelemetry traces that follow a request
across processes.

## The System app

Super admins open it from the Nexus sidebar (**System**,
`/workspace/<id>/admin/system`). Every source can be down on its own; each view
says which one and why.

| Tab | Shows |
|---|---|
| **Overview** | Kernel services serving, remote modules by status, the engine and the broker at a glance. |
| **Services** | Each kernel service: its configured adapter kind (never its settings), its NATS instances and their request and error counts. |
| **Data** | What each service holds, as a tree: objects, documents, datasets, graphs, secrets (masked), key-value entries, bus streams, discovery records. Super admins can read, download, write and delete, with an audit row before each change and the resource id typed back to confirm. Revealing a secret is a separate, audited action. |
| **Jobs** | Every module's and the engine's jobs, their runs, logs and results, failures, and **Run now** with a JSON payload. Skipped runs are hidden unless asked for. |
| **Agents** | Remote agent runs across modules, newest first: caller, owner, events and trace. A running run can be cancelled (audited). |
| **Modules** | The engine modules loaded in the API's engine, and the remote modules registered in discovery: status, version, rollout, and their agents, jobs, models and apps. A crashed or stuck registration can be removed. |
| **NATS** | The broker, read from its monitoring endpoint (`nats.monitoring_url`): the server, every connection by name, and the JetStream streams and their consumers (discovery, jobs, bus). |
| **Live traffic** | Calls as they happen: service, method, caller, sizes, latency, status and trace id. Metadata only, never payloads. |
| **Traces** | Search traces (service, operation, window, duration, errors) and read one as a waterfall with each span's attributes and events. |

The routes behind it live under `/api/admin/system/` and need a super admin.
Jobs can be triggered from a script with
`POST /api/admin/system/jobs/<module>/<job>/trigger` and the body
`{"payload": {...}}`.

**Workflows** (jobs with a typed input and checkpointed steps) are in the Jobs tab
too: a "workflow" badge, a launch form generated from the input schema (a JSON
editor when the schema has no form), and a **Steps** tab on each run with the
attempts, durations, errors and links to child runs. Scripts use `/api/workflows`
with `Authorization: Bearer $ABI_API_KEY` (or a super admin's session):

```bash
# List, with each workflow's input and output schemas
curl -H "Authorization: Bearer $ABI_API_KEY" $NEXUS/api/workflows

# Start; ?wait=30 holds the call up to 30 s and answers 200 with the result if the
# run ends in time, else 202 with the run. A wrong input is a 422 and starts nothing.
curl -X POST -H "Authorization: Bearer $ABI_API_KEY" -H "Idempotency-Key: import-1" \
  -d '{"filter": "news"}' "$NEXUS/api/workflows/<module>/<workflow>/runs?wait=30"

# Status, result and steps; cancel
curl -H "Authorization: Bearer $ABI_API_KEY" $NEXUS/api/workflows/<module>/runs/<run_id>
curl -X POST -H "Authorization: Bearer $ABI_API_KEY" $NEXUS/api/workflows/<module>/runs/<run_id>/cancel
```

Every start and cancel is audited like a job trigger; a call with the API key has
no user, so its audit record says it came from the API key.

### Where live traffic comes from

With tracing configured, the System app reads recent spans from the tracing
backend (`telemetry.query_url`, else `ui_url`): one row per NATS call and per
job run, a chunked transfer counted as one row with its totals. Without a
reachable tracing backend, it falls back to a NATS tap that subscribes to ABI's
request subjects and reads headers and sizes only, and only while someone
watches. The stream says which source is live.

## Named connections and error codes

- Every NATS connection carries a name: `abi-engine`, `abi-<identity>:<domain>`,
  `abi-bus`, a module's id, `nexus-api-*`. The broker's `/connz` (port 8222)
  and the NATS tab tell processes apart.
- Every error reply of a kernel service carries an `Abi-Error-Code` header, so
  errors are visible without reading payloads.

## Tracing

ABI exports OpenTelemetry spans over OTLP/HTTP. W3C trace context
(`traceparent`) travels in NATS headers, so one request is one trace across
Nexus, the engine and every module it reaches:

- HTTP spans in Nexus and the API;
- a CLIENT span for each NATS call (in the SDK transport and the engine's RPC
  client) and a SERVER span in the kernel service that answers;
- a CONSUMER span for each job run, continuing a manual trigger's trace;
- spans for agent submissions and runs, and one span per transfer session.

Tracing needs the `otel` extras: `naas-abi-core[otel]` (in `naas-abi-core[all]`)
and `naas-abi-sdk[otel]` for modules. Without them, nothing changes.

### Natively

```bash
abi dev up --with-tracing
```

It runs Jaeger v2 (`jaeger` on `PATH`) with per-worktree ports and adds the
`telemetry:` block to the dev overlay. `abi dev ports` prints the Jaeger UI
port. Dev modules get `OTEL_EXPORTER_OTLP_ENDPOINT`.

### With Docker Compose

The generated stack has no tracing backend. Add one, for example Jaeger v2, to
`docker-compose.yml`:

```yaml
  jaeger:
    image: jaegertracing/jaeger:2.21.0
    restart: unless-stopped
    ports:
      - 127.0.0.1:16686:16686 # trace UI, from the host only
    networks:
      - abi-network
```

Then turn tracing on in the engine's config (`config.local.yaml`):

```yaml
telemetry:
  enabled: true
  otlp_endpoint: "http://jaeger:4318"
  service_name: "abi-engine"
  # The trace viewer the System app links to.
  ui_url: "http://localhost:16686"
  # Where the API reads spans for Live traffic and Traces (inside Compose).
  query_url: "http://jaeger:16686"
```

Remote modules export with the standard `OTEL_EXPORTER_OTLP_ENDPOINT`
(`http://jaeger:4318`) in their Compose service.

| `telemetry` key | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Export spans. |
| `otlp_endpoint` | none | OTLP/HTTP endpoint; without it, the standard `OTEL_EXPORTER_OTLP_*` variables apply. |
| `service_name` | `abi-engine` | The engine's service name in traces. |
| `sample_ratio` | 1.0 | Share of traces kept. |
| `ui_url` | none | The trace viewer the System app links to (`<ui_url>/trace/<id>`). |
| `query_url` | `ui_url` | Where the API reads recent spans (Jaeger's query API). |

## The broker

NATS has its own monitoring endpoint on port 8222 (no authentication: keep it
on the private network):

```bash
curl -s http://localhost:8222/healthz   # {"status":"ok"}
curl -s http://localhost:8222/connz     # connections, by name
curl -s http://localhost:8222/jsz       # JetStream streams and consumers
```

With the [NATS CLI](https://github.com/nats-io/natscli), `nats micro list`
shows the kernel services and their stats.

## Logs

- `abi dev logs <service> -f` follows a native service or dev module
  (`abi dev up` runs the API at `LOG_LEVEL=DEBUG` unless told otherwise).
- In Compose, `docker compose logs -f abi`.
- At `DEBUG`, the engine logs `EngineNATSLoader: exposed <service> over NATS`
  for each service it serves. Keep production at `INFO`: `DEBUG` logs model
  prompts.

→ [The Data Plane](./data-plane)
