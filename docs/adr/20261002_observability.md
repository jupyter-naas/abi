# Observability of a NATS deployment: SysAdmin app, live traffic, OpenTelemetry

## Status
Accepted. Implemented with the Nexus SysAdmin "System" app.

## Date
2026-10-02

## Context
Kernel services, remote modules, agents and jobs now talk over NATS. Operators had
no single place to see what is configured, what is running, who is connected and
what each call does. `trace_id` was generated per RPC but never propagated or
logged, so a request crossing three processes left three unrelated traces;
domain errors travel in reply bodies, so NATS micro stats count almost none;
connections were unnamed, so the broker's `/connz` could not tell processes apart.

## Decision
- **Super-admin System app** (Nexus): kernel services (configured adapter kinds,
  never settings, merged with `$SRV.STATS`), engine and discovered modules, the
  broker through its HTTP monitoring endpoint (`nats.monitoring_url`), and live
  traffic. Every source can be down independently; views report which and why.
- **Named connections**: `<role>@<host>` (`abi-engine`, `abi-<identity>:<domain>`,
  `abi-bus`, `<module_id>`, `nexus-api-*`).
- **Live traffic, metadata only, from traces first**: when tracing is configured
  (`telemetry.query_url`, else `ui_url`), the System app polls recent spans from
  Jaeger's query API: one row per NATS call (CLIENT span: service, method, caller
  process, request/reply bytes, latency, status, trace id) and per job run. A
  chunked transfer (object get/put, model stream) is one span with its totals
  (`abi.transfer.bytes_sent`/`bytes_received`/`messages`), not one per chunk.
  Fallback without a reachable tracing backend: a NATS tap subscribing to ABI
  request subjects and `_INBOX.>` (headers and sizes only, transfer subjects
  excluded, caller = token `sub`), running only while someone watches. The
  stream reports which source is live. Business facts (an object put, a deletion)
  stay Events (`ObjectPut`, `ObjectDeleted`), not traffic.
- **`Abi-Error-Code` reply header** on every error reply of a kernel service, so
  errors are visible without reading payloads.
- **OpenTelemetry**: W3C trace context in NATS headers (`traceparent`). CLIENT
  spans in the SDK transport and the core RPC client, SERVER spans in every kernel
  service (`add_traced_service`), HTTP spans in Nexus, CONSUMER spans for job runs
  (continuing a manual trigger's trace) and spans for agent submits and runs.
  `naas_abi_sdk.telemetry` is the single implementation (stdlib plus optional
  OpenTelemetry API; no-op without a configured provider). Engines opt in with
  `telemetry:` (`enabled`, `otlp_endpoint`, `service_name`, `sample_ratio`,
  `ui_url`); SDK modules with the standard `OTEL_EXPORTER_OTLP_ENDPOINT`.
  Spans are exported over OTLP/HTTP; zen runs Jaeger v2 (an OpenTelemetry
  Collector distribution) and Nexus links traffic rows to `ui_url/trace/<id>`.
  Natively, `abi dev up --with-tracing` runs Jaeger v2 from a generated config
  (per-worktree ports) and adds the `telemetry:` block to the dev overlay.
  A transfer's trace is an explicit object passed to its chunk calls, never the
  current span: model streams are async generators advanced from several tasks.

## Consequences
- Tracing needs `naas-abi-core[otel]` / `naas-abi-sdk[otel]`; without them nothing
  changes. `CallContext.trace_id` stays as is (not the OTel trace id).
- While the tap runs, the API receives every reply on the bus; it starts with the
  first viewer and stops with the last. The monitoring endpoint has no auth:
  keep it on the private network.
- Destructive operations (deletes, purges, module eviction) are a follow-up with
  typed confirmation and audit events.
- `naas-abi-core` without `[nats]` has no SDK: job declarations fall back to inert
  stand-ins (`module/jobs_fallback.py`) so modules still import.
