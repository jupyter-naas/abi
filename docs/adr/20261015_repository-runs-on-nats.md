# The ABI repository runs on NATS; Dagster and RabbitMQ are a legacy profile

Status: Accepted

Date: 2026-10-15

## Context

ABI 3.0 makes NATS the default for generated projects. `abi new project`
writes a `nats:` block, `abi deploy local` renders a stack whose engine depends
on the `nats` service, and `abi dev up` leaves Dagster out in NATS mode.

The repository itself still ran the 2.x setup:

- its root `config.yaml` (the no-Docker `abi dev` runtime) had no `nats:` block
  and an explicit `python_queue` bus;
- its `config.local.yaml` (the Docker stack) put the bus on RabbitMQ;
- its `docker-compose.yml` started `dagster` and `rabbitmq` by default, made the
  engine wait for RabbitMQ, and kept `nats` behind a `nats` profile.

Contributors therefore ran a stack that customers no longer get. NATS-only code
paths (kernel services over the broker, the single serving engine, module jobs,
discovery) went unexercised in day-to-day development, and the repository's own
docs described RabbitMQ as a requirement.

## Decision

- Both root configs have a `nats:` block, shaped like the project templates.
  The bus block is gone: with NATS the bus is JetStream, and without it the
  engine's default `python_queue` applies. Discovery names the project `abi`.
- The secrets that block names (`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`,
  `NATS_JWT_SECRET`) are generated into `.env` on first run, as the admin
  password is. They are not prompted for, so this works without a TTY:
  - `abi dev up` generates them whenever the project config has a `nats:`
    block, also with `--without-nats`. The engine renders the whole config
    before it merges the overlay that turns the block off, and a missing
    `{{ secret.X }}` fails without a TTY.
  - `abi stack start` generates them before `docker compose up`, when the
    project config runs on NATS. The `nats` service refuses to start without
    its passwords.
- In `docker-compose.yml`, `nats` has no profile and the engine depends on it.
  `dagster` and `rabbitmq` move behind a `legacy` profile, and nothing in the
  default profile depends on them.
- The legacy setup stays reachable:
  - `abi dev up --without-nats` runs the in-process engine, with Dagster when
    the `naas-abi-core[dagster]` extra is installed.
  - `abi stack start --legacy` writes `.abi/stack/legacy.overlay.yaml`
    (`nats: null`, the bus on RabbitMQ, credentials from `.env`, mode 0600),
    then runs Compose with the `legacy` profile. The abi and dagster services
    read the overlay through `ABI_STACK_CONFIG_OVERLAY`, a variable of its own:
    a shell's `ABI_CONFIG_OVERLAY` is a host path, which the containers
    cannot read. It refuses a compose file that has no `legacy` profile,
    because a generated project picks its stack when it is created or
    deployed.
  - `docker compose --profile legacy up -d dagster` adds the containers alone.
    Dagster then runs with `ABI_ENGINE_ROLE=client`, so it never competes with
    the abi engine for the serving lease
    (`20261006_single-serving-engine.md`).
- `abi stack stop` also stops the `legacy` profile's containers.
- The repository keeps installing the `dagster` and `rabbitmq` extras, because
  it tests them and its legacy stack runs them.
- `abi stack snapshot` captures `nats_data` (JetStream: the bus, KV buckets,
  the module registry, job schedules).

## Consequences

- `abi dev up` in the repository needs `nats-server` 2.14+ on `PATH`. The
  hosted development environment's setup script lives outside the repository,
  so installing it there is an owner action.
- Anything that builds an engine from the root config outside `abi dev`, such
  as `abi chat`, `make api`, or a test that calls `Engine()`, needs a broker at
  `127.0.0.1:4222` (the Docker stack's). To load the engine in-process without
  one, point `ABI_CONFIG_OVERLAY` at a YAML file holding `nats: null`.
- The Makefile's `local-*` targets go through `abi stack start`, so the NATS
  secrets are seeded. They use the `legacy` profile for logs, stop and down, so
  legacy containers are included. The Dagster targets are labelled legacy.
- `config.remote.yaml` (the hosted API deploy) is unchanged; moving it to NATS
  is a deployment change of its own.
