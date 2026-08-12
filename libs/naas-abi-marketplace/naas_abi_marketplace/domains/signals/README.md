# S6 — signals

## The question this bucket answers

> *How does information move and get stored inside the organization?*

In the staff system, S6 owns communications and information systems — the means by which the
organization talks to itself and keeps what it knows. In a civilian organization it covers
engineering, IT, the data platform, knowledge management and internal comms tooling.

Signals is about the **plumbing**, not the message. It is defined by information flowing *inside*
the organization, which is what separates it from [`intelligence/`](../intelligence/).

## What's here

```
signals/
├── __init__.py                     # ABIModule, datastore_path = "signals"
└── agents/
    ├── DataEngineerAgent.py
    ├── DevOpsEngineerAgent.py
    └── SoftwareEngineerAgent.py
```

| Module | Component | What it delivers |
|---|---|---|
| `SoftwareEngineerAgent` | `agents/` | Code, architecture, review, testing, debugging |
| `DevOpsEngineerAgent` | `agents/` | CI/CD, infrastructure automation, monitoring, deployment |
| `DataEngineerAgent` | `agents/` | Pipeline design, ETL, data architecture, performance |

> `document/` and `ontology_engineer/` previously lived here under `pipelines/` and have been moved
> to [`../operations/modules/`](../operations/). Import paths and `config.local.yaml` still
> reference the old `domains.signals.pipelines.*` prefix — see the *Known issue* in
> [`../operations/README.md`](../operations/README.md). Note that
> [`../AGENT.md`](../AGENT.md) still records the standing decision placing them here.

## What belongs here

- Software engineering and code tooling
- Infrastructure, deployment, observability
- Data pipelines, warehousing, ETL
- Knowledge management: ingestion, indexing, retrieval, ontology infrastructure
- Internal communication and collaboration tooling

## Boundary tests

**vs [`intelligence/`](../intelligence/) (S2) — inside or outside.**
Signals moves information *within* the organization; intelligence is about the world *outside* it.
A document-ingestion pipeline serving every internal team is signals; a competitor-monitoring
module is intelligence — even though both end up producing searchable text.

**vs [`logistics/`](../logistics/) (S4) — information or materiel.**
S4 is explicitly physical: goods, transport, facilities. If the thing being moved or stored is
information, it is signals. This is the "bytes, not boxes" test.

**vs [`operations/`](../operations/) (S3) — capability or mission.**
Signals builds and runs the systems everyone else uses. Operations uses them to execute the current
mission. A deployment pipeline is signals; the product delivery it ships is operations. A module
that only exists to serve one execution team is probably operations.

**vs [`ai/`](../../ai/) and [`applications/`](../../applications/) — cross-cutting.**
An LLM provider or a generic third-party API wrapper serves every bucket equally and does not
belong in `domains/` at all. Technology is not function: a Postgres integration is signals only if
it serves the data platform; used for payroll queries it is [`personnel/`](../personnel/).

## Filing a module here

`signals/<component>/<module>/`, where `<component>` is the module's dominant deliverable.
Single-agent modules may sit flat as `agents/<Name>Agent.py`. See [`../AGENT.md`](../AGENT.md) for
the full filing rules and [`../README.md`](../README.md) for the framework.
