# Stop the process when NATS is gone for good

Status: Accepted

Date: 2026-10-08

## Context

nats-py retries a lost server `max_reconnect_attempts` times (60, two seconds
apart, by default), then closes the connection and never reconnects it. No
connection in core or the SDK handled that close. After a broker outage of
about two minutes, an engine kept running with its lease, kernel endpoints,
job consumers and bus subscribers on closed connections: it served nothing,
while its HTTP health check stayed green. Only a manual restart helped.
SDK modules were in the same state.

Reconnecting in place would mean rebuilding every subscription, consumer and
lease renewal on a new connection, in every component that holds one.

## Decision

A process whose NATS connection closes for good stops, and its supervisor
starts a fresh one (`naas_abi_sdk/lifeline.py`).

- Every long-lived connection passes a `Lifeline`'s `closed` as nats-py's
  `closed_cb`: SDK `Transport`, and in core the shared engine connection
  (`nats_runtime`), the lease (`EngineOwnershipLoader`) and the bus adapter's
  publish, subscriber and worker connections.
- An owner closes its connection on purpose through `Lifeline.close(nc)`,
  which is not a loss. A connection nats-py already closed stays a loss, since
  its owner can react to the closed connection before `closed_cb` runs.
- Opting in is process-wide. Core's `api()` opts in when the engine runs in
  NATS mode without reload (the reloader would not restart a worker that
  exits). SDK `run_module` opts in for its run. Otherwise a loss is only logged.
- Stopping sends SIGTERM, so the usual shutdown runs. If the process is still
  alive after `HARD_EXIT_SECONDS` (20), it exits with status 1.

## Consequences

- A broker outage longer than the reconnect window restarts every engine and
  SDK module. Shorter outages still reconnect in place, as before.
- Deployments need a supervisor that restarts the process on exit (Docker
  `restart: unless-stopped` or `always`, Kubernetes). Zen's `abi` service has
  `unless-stopped`.
- With `api.reload: true` (development), the loss is only logged and the API
  must be restarted by hand.
- CLI engines (`abi chat`, scripts) do not opt in.
