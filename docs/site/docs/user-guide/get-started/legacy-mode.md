---
sidebar_position: 4
title: "Legacy mode: without NATS"
---

# Legacy mode: without NATS

:::warning Legacy
Everything on this page is **legacy**: opt-in since ABI 3.0 and removed in the next
major. New projects run on NATS. If you have a 2.x project, plan to move it:
[Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3).
:::

Before 3.0, ABI ran as one in-process engine, with Dagster for scheduled work and
optionally RabbitMQ for the message bus. 3.0 keeps that setup working, behind
explicit opt-ins, so a project can upgrade the code first and move to NATS later.

| Piece | In 3.0 by default | Legacy opt-in |
|---|---|---|
| Engine wiring | A NATS broker: kernel services, bus, jobs and module discovery go through it | In-process: no `nats:` block in the config |
| Scheduled work | [Module jobs](/user-guide/build/modules/module-jobs) on JetStream | [Dagster](/user-guide/build/applications/dagster) orchestrations |
| Message bus | NATS JetStream | `python_queue` (SQLite, no extra) or `rabbitmq` (needs the `naas-abi-core[rabbitmq]` extra) |
| Remote modules, remote apps | Yes | No: they need NATS |

## Create a legacy project

```bash
abi new project my_ai --without-nats
```

The project has no `nats:` block, a Compose stack with RabbitMQ and a `dagster`
service, and the `naas-abi-core[dagster,rabbitmq]` extras in its `pyproject.toml`.
`abi new module <name>` creates an in-engine module (add `--remote` to create a
remote module that runs once the project is on NATS), and `abi new orchestration
<name>` writes a Dagster orchestration.

A project with no `nats:` block that you create or deploy gets the same:
`abi deploy local` renders the classic stack, with a `nats` service behind the
Compose profile `nats`, and adds the `dagster` and `rabbitmq` extras to the
`pyproject.toml` for you (commit the change).

## Run it

| Command | What it does |
|---|---|
| `abi dev up` (no `nats:` block) | Oxigraph, the API, Dagster (only when the project installs the `dagster` extra), Nexus web. |
| `abi dev up --without-nats` | The same, for a project whose config has a `nats:` block. |
| `abi deploy local` then `abi stack start` | The classic Docker stack, with RabbitMQ and Dagster. |
| `abi stack start --legacy` | In the ABI repository only: also the `legacy` Compose profile (Dagster, RabbitMQ), and the engine without NATS through the overlay `.abi/stack/legacy.overlay.yaml`. A generated project refuses it. |

`abi dev up -d` returns at once in this mode: poll the API's `/docs` before you
use it (the first boot takes one to three minutes).

## Configure it

```yaml
services:
  bus:
    bus_adapter:
      adapter: "python_queue"      # the default: SQLite under storage/bus/
      # adapter: "rabbitmq"        # legacy: needs naas-abi-core[rabbitmq]
      # config:
      #   rabbitmq_url: "{{ secret.RABBITMQ_URL }}"
```

Without the extras, the RabbitMQ bus adapter, `DagsterOrchestration.New()` and the
Dagster app raise `MissingLegacyExtra` and print the command to fix it:

```bash
uv add 'naas-abi-core[all,dagster,rabbitmq]'
```

In NATS mode one engine serves the kernel services, so Dagster (a second engine)
cannot run next to the API: the NATS stack has no Dagster service.

## What does not exist here

A project without NATS has no module jobs, no discovery, no remote modules or
apps, no System-app Jobs tab and no `nats_rpc` adapters. Declared jobs are logged
and not run.

## Move to NATS

Follow [Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3): upgrade the code
with NATS off, turn NATS on, then separate the processes. Move each Dagster
orchestration to a job first ([From Dagster to module jobs](/user-guide/build/modules/module-jobs#from-dagster-to-module-jobs)).
