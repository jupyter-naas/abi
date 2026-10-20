---
sidebar_position: 2
title: "Deploy with Docker"
---

# Deploy with Docker

`abi deploy local` writes a Docker Compose stack for your project, and
`abi stack start` runs it. It is the way to run the full set of backing services
(PostgreSQL, Fuseki, Qdrant, MinIO, Redis) on one machine: a laptop, a workstation, a
single server. For a server with a domain and certificates, use
[Dokploy](/user-guide/deploy/dokploy) or the [production guide](/user-guide/deploy/production).

You need [Docker](https://docs.docker.com/get-docker/) with Compose v2 and 8 GB of
RAM or more. See [Install and prerequisites](/user-guide/get-started/install).

---

## 1. Write the stack

From the root of a project made by `abi new project` (which already ran this unless you
passed `--without-local-deploy`):

```bash
abi deploy local                        # asks for the base domain: localhost by default
abi deploy local --regenerate           # re-render from the CLI's current templates
```

It writes `docker-compose.yml`, `.deploy/docker/` (Caddy, Postgres init scripts, the
NATS broker's `nats.conf`) and the variables the stack needs in `.env`: generated
passwords, `NATS_JWT_SECRET`, `NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`, the admin's
password (`NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`) and `ABI_API_KEY`.

- A project with a `nats:` block in its config gets the **NATS stack**: a `nats`
  service the engine waits for, no Dagster, and RabbitMQ only behind the Compose
  profile `rabbitmq`.
- A project without one keeps the classic stack ([legacy](/user-guide/get-started/legacy-mode):
  Dagster, RabbitMQ), and `abi deploy local` adds the `naas-abi-core[dagster,rabbitmq]`
  extras to its `pyproject.toml`: commit the change.
- `--regenerate` backs the previous files up first (`--no-backup` skips it), keeps the
  values already in `.env`, and never touches `docker-compose.override.yml`, where
  [remote modules](/user-guide/build/sdk/build-a-remote-module) live. Regenerate after
  each CLI upgrade.
- `-e/--env` picks the config environment (`local` by default: `config.local.yaml`).
- Optional extras: `--coding` (Coder, Forgejo and Actions CI workspaces) and
  `--headscale` (a Headscale service).

The stack's `abi` service runs with `ENV=local`, so it reads `config.local.yaml`:
PostgreSQL for the document service, Fuseki for the triple store, Qdrant, MinIO and
Redis. `config.yaml` is what `abi dev up` reads. See
[Configuration](/user-guide/get-started/configuration#environment-files).

---

## 2. Start it

```bash
abi stack start                         # start, then wait until every service is ready
abi stack status                        # readiness of each service
abi stack logs api                      # logs of one service (no argument: all)
abi stack tui                           # a live terminal view
abi stack stop                          # stop; -v also removes the volumes
```

`abi start`, `abi stop` and `abi logs` are shortcuts. Underneath they are
`docker compose`: the same stack starts with `abi deploy local-up -d` (which also reads
`docker-compose.override.yml`), and `abi deploy local-logs` and
`abi deploy local-down [-v]` follow and stop it.

The first start pulls the images and builds `abi`. The engine then loads every module and
runs the Nexus migrations: allow a few minutes.

| Service | Where |
|---|---|
| Nexus web | http://localhost:3042 (or `nexus.<domain>` through Caddy) |
| API (Swagger at `/docs`) | http://localhost:9879 (or `api.<domain>`) |
| NATS monitoring | http://localhost:8222 (this machine only) |
| Fuseki (SPARQL) | http://localhost:3030 |
| MinIO console | http://localhost:9001 |
| MCP server | http://localhost:8000 |
| Service portal, YasGUI, Redis Commander | http://localhost:8080, 3000, 8082 |

Sign in to Nexus as `admin@example.com` with the password from `.env`:

```bash
grep NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD .env
```

---

## Remote modules

`abi new module <name>` adds a service for the module to `docker-compose.override.yml`
and its key to `.env` (`ABI_MODULE_KEY_<NAME>`), so `abi stack start` builds and runs it
in its own container, next to the engine. Its agent shows up in Nexus once it logs `READY`.

---

## Models: Ollama on Linux

A stack that uses [Ollama](https://ollama.com) reaches the host through
`host.docker.internal`. On Linux, Ollama listens on `127.0.0.1` only, which the Docker
bridge cannot reach: bind it to an address the bridge can reach (`OLLAMA_HOST=0.0.0.0:11434`
on a trusted network, or the bridge address and a firewall rule), then restart it. Docker
Desktop on macOS needs nothing. To use an Ollama elsewhere, set `ABI_OLLAMA_BASE_URL`.

---

## Snapshots

```bash
abi stack snapshot create -m "before upgrade"
abi stack snapshot list
abi stack snapshot restore <id>         # destructive; takes a safety snapshot first
abi stack snapshot export <id> backup.tar.gz
abi stack snapshot import backup.tar.gz
abi stack snapshot prune --keep 5
```

A snapshot archives the data volumes (including `nats_data`) and `storage/`.

---

## Reset

```bash
abi stack stop -v                       # removes the volumes: the data is gone
```

If "Incorrect email or password" appears after a reset, read the password again from
`.env`: it may have just been rotated.

## Next

- [Dokploy](/user-guide/deploy/dokploy): the same stack on a server with Traefik and Let's Encrypt.
- [Production and remote deployments](/user-guide/deploy/production).
- [Deployment models](/user-guide/deploy/deployment-models).
