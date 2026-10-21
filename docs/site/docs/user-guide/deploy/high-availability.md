---
sidebar_position: 7
---

# High Availability & Disaster Recovery

How an ABI deployment behaves when a process, a host or a backing service fails, and what you have to provide around it. ABI 3.0 gives you the engine side: one serving engine that hands over by lease, deploys without downtime, remote modules that scale and restart on their own, and durable jobs. The availability of the stores (PostgreSQL, object storage, the triple store, Redis, Qdrant) and of the NATS broker is the availability of the infrastructure you run them on.

:::info Professional Services Implementation
Multi-zone and disaster-recovery designs are customized to each environment and implemented with dedicated support. Contact our enterprise team at [support@naas.ai](mailto:support@naas.ai) to discuss your needs and implementation timeline.
:::

## What the engine does

These behaviours are in `naas-abi-core` 3.0 and apply to a project in NATS mode (one with a `nats:` block, which `abi new project` creates). They are explained in [NATS and the kernel services](/developer-guide/architecture/nats).

### One serving engine, by lease

Exactly one engine serves the kernel services per NATS account. It holds a lease (the key `owner` in the `ABI_ENGINE` bucket of JetStream) that it renews every quarter of `nats.engine.lease_seconds` (20 s by default).

- A second engine that tries to serve fails at start with `EngineAlreadyServing`, so two replicas never split the requests between two copies of each service.
- An engine that crashed is replaced after at most one lease period. A holder that cannot renew for half a lease stops serving at once (fencing).
- `role: client` engines (scripts, notebooks) never serve and open no backend.

### Deploys without downtime

Set `ABI_ROLLOUT_ID` (the image tag, for example) on every deploy. A new engine with a different rollout id **stands by**: it loads, reports ready, and takes the lease when the old engine releases it. The old engine stops its jobs, releases the lease, stops taking calls, and finishes the calls and transfers it already holds, for up to `nats.engine.drain_seconds` (60 s). For a moment both serve, rather than neither.

This needs **shared backends**. An engine started with a rollout id refuses to start if a service it owns keeps its data on local disk or in the process (SQLite, embedded Oxigraph or Qdrant, the `fs` adapters): the next engine would answer from another copy. Use PostgreSQL, S3 or MinIO, Redis, a Fuseki or Oxigraph server and a Qdrant server. Development and single-host setups keep the file backends and deploy by stopping, then starting.

A standby that has not taken over within `nats.engine.standby_timeout_seconds` (900 s) stops its process, so a deploy that never stops the old engine shows up.

On Kubernetes, use one `ABI_ROLLOUT_ID` per deploy, `maxSurge: 1` and `maxUnavailable: 0`, count a standby as ready, and set `terminationGracePeriodSeconds` above the jobs' run time plus `drain_seconds`. ABI does not ship Kubernetes manifests; the Compose stack of `abi deploy local` is the reference.

### When the broker is lost

The API process and SDK modules reconnect for about two minutes (60 attempts, 2 s apart). After that, the API process stops (SIGTERM, then exit status 1 after 20 s) and so does a module. Run them under a supervisor that restarts them: Docker `restart: unless-stopped` (what the generated stack uses), or Kubernetes. With `api.reload: true` the loss is only logged.

Cross-service calls have no local fallback in NATS mode: while the broker is down, they fail.

### Remote modules

A remote module scales and fails on its own:

- Several replicas of a module share its agent runs and its jobs (one replica takes each job trigger).
- A module's instance holds a lease in discovery (180 s in a generated project) and renews it; a clean stop unregisters at once, a crash is cleaned up when the lease expires. Callers use only `READY` instances.
- Instances started with the same `ABI_ROLLOUT_ID` cut over together: the previous generation stays ready until the new one is up, then drains.
- On `SIGTERM` a module stops taking new work, finishes the runs and jobs it started, and unregisters. Give it a grace period longer than its longest job.

See [Remote modules and jobs](/developer-guide/architecture/remote-modules).

### Jobs and agent runs

- Module jobs are **at least once**: a handler may run again after a crash. Write handlers that tolerate a repeat. A run is a record in the Document Service, so its state survives a restart.
- A missed cron tick fires once when the broker comes back, not once per missed tick.
- An agent run is a durable record too: it can be reattached after a lost reply, and a conversation's memory lives in the Document Service, shared by replicas. Repeating a submission with the same invocation id returns the stored run.

## What you provide

| Component | What runs it in the generated stack | What to plan |
|---|---|---|
| **NATS and JetStream** | One `nats` container, JetStream data on the `nats_data` volume. | It holds the bus, job schedules, the module registry and the engine lease. The engine and the modules stop when it is gone for two minutes. ABI does not ship a clustered broker configuration. If you run a NATS cluster, point `nats.nats_url` at it and reproduce the `engine` and `auth` users and the auth callout of the generated `nats.conf`; test the failover with your own procedure. Put the data on a persistent disk and back it up. |
| **PostgreSQL** | `postgres` container. | Nexus data, the documents (agent memory, job runs, the activity log in the Document Service) and the dataset catalog. Use your platform's replicated or managed PostgreSQL, with point-in-time recovery. |
| **Object storage** | MinIO. | Files and datasets' data. Use S3, or MinIO in a mode you operate. |
| **Triple store** | Fuseki (Apache Jena TDB2). | The knowledge graph. One server in the stack; the stack runs a compaction sidecar and has a backup script (below). Plan a standby host or restore procedure. |
| **Qdrant, Redis** | `qdrant`, `redis` containers. | Embeddings and key-value data. Use the replication of each product, or accept restoring them from a snapshot. |
| **Entry point** | Caddy. | Put a load balancer or your platform's ingress in front, and your own certificates or ACME. |

Whatever you choose, keep the data on storage that outlives the host.

## Health and monitoring

- The generated stack has health checks: the `abi` service requests `http://localhost:9879/`, NATS answers `/healthz` on port 8222, and Fuseki is probed with a real query against its dataset (a corrupt dataset marks it unhealthy). Dependent services wait for them.
- The Nexus **System** app shows what is serving, which modules are registered and in what status, the jobs and their runs, and the broker's connections and streams. See [Observability](/developer-guide/architecture/observability).
- The broker's monitoring endpoint (`/healthz`, `/connz`, `/jsz`) has no authentication: keep it on the private network.
- `abi stack status` and `abi stack tui` show the Compose stack; `docker compose logs -f abi` follows the engine.

Alerting is yours: wire the container health, the broker's `/healthz`, the API and your databases into your monitoring system. A useful set of alerts: the API or a module restarting repeatedly, the broker down, a lease that changes holder often, a job run stuck in `RETRYING`, and the disk space of the volumes.

## Disaster recovery

ABI does not set an RTO or RPO: they come from how you replicate and back up each store. Decide them first, then check that your design meets them.

- **RTO**: how long the service may be down. It is bounded by how fast you can bring the stores and the broker back, and by the engine's boot (2 to 3 minutes for the API).
- **RPO**: how much data you can lose. It is the age of your newest usable copy of each store.

### Snapshots of the Docker stack

`abi stack snapshot` takes a cold, consistent copy of the stack:

```bash
abi stack snapshot create --note "before the upgrade"
abi stack snapshot list
abi stack snapshot export <id> /backups/abi-<id>.tar    # one archive for another host
abi stack snapshot import /backups/abi-<id>.tar
abi stack snapshot restore <id>
abi stack snapshot prune --keep 5
```

It stops the stack, archives the stateful volumes (`postgres_data`, `minio_data`, `fuseki_data`, `qdrant_storage`, `redis_data`, `nats_data`, and the legacy and Headscale ones when present) and the project's `storage/` folder, then restarts the stack. Because the stack is stopped, the archives agree with each other: the dataset catalog in PostgreSQL and the data files in `storage/` come from the same moment. Restore the whole snapshot, not one store.

Snapshots are stored in `.snapshots/` of the project. A restore is destructive, and takes a safety snapshot of the current state first (`--no-safety-snapshot` turns that off). A snapshot stops the stack briefly, so it is a cold backup, not a continuous one: it does not give you a short RPO by itself. Copy the exported archives off the host.

### Backups of the stores

For a deployment on managed or replicated services, back up each store with its own tooling instead:

- **PostgreSQL**: base backups with WAL archiving (point-in-time recovery), or your platform's managed backups.
- **Object storage**: bucket versioning and replication on S3, or backups of the MinIO volume.
- **Knowledge graph**: `.deploy/docker/fuseki/backup.sh` dumps the Fuseki dataset to the Fuseki volume through the admin API (and compacts it with `--compact`); a compaction sidecar already compacts it daily. Copy the dump off the host.
- **Configuration and secrets**: the project is a git repository; keep `.env` in your secret manager, not in git.

Keep copies in at least one other location, encrypted, and keep the retention you need for compliance.

### Recovering

1. Declare the incident and decide the target: the same host or another.
2. Bring up the stores and the broker from your latest copies (a snapshot restores all of them together).
3. Start the engine. It loads every module and runs migrations, so allow a few minutes. With the data in place, the lease is free and the engine takes it.
4. Start the remote modules. They re-register in discovery.
5. Check the System app (services serving, modules `READY`), sign in, chat, and run a job from the Jobs tab.
6. If the broker's data (`nats_data`) was lost, what was queued in the bus and the job triggers is gone. The engine that hosts discovery creates the jobs stream and the claim-check store again at start, and the modules register again; check the Jobs tab and trigger what is missing.

Rehearse the recovery on a spare host on a schedule you can keep: backup restores often, a full recovery at least once a year, and after every major upgrade.

## Known limits

- The generated stack is a single host with one broker, one database, one triple store. It restarts what crashes (`restart: unless-stopped`) and hands over without downtime on shared backends, but a lost host is a restore.
- The engine that serves the kernel services is one process at a time. Replicas of it are standbys for a deploy or a failure, not extra capacity; remote modules are what you scale out.
- Calls are at most once, and jobs at least once. After a crash, a request the engine had already received may or may not have run: reconcile before you retry.
- The broker's own limits (no TLS, no authentication on monitoring, modules as trusted code) are in the [Security model](/developer-guide/architecture/security).
