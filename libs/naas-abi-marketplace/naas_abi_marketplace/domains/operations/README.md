# S3 — operations

## The question this bucket answers

> *How do we execute the mission we are on right now?*

In the staff system, S3 runs the **current** operation — everything needed to execute today. In a
civilian organization it covers revenue execution, delivery, customer support and project
execution.

Operations is the largest bucket, and that is expected: most of what an organization does at any
moment is executing already-committed work.

## What's here

```
operations/
├── __init__.py                                 # ABIModule, datastore_path = "operations"
├── agents/                                     # flat role agents
│   ├── AccountExecutiveAgent.py
│   ├── BusinessDevelopmentRepresentativeAgent.py
│   ├── CampaignManagerAgent.py
│   ├── ContentAnalystAgent.py
│   ├── CustomerSuccessManagerAgent.py
│   ├── InsideSalesRepresentativeAgent.py
│   ├── ProjectManagerAgent.py
│   └── SalesDevelopmentRepresentativeAgent.py
└── modules/                                    # nested loadable modules
    ├── document/
    ├── ontology_engineer/
    └── support/
```

### Revenue and delivery agents

| Agent | Role |
|---|---|
| `SalesDevelopmentRepresentativeAgent` | Outbound prospecting, lead generation, qualification |
| `BusinessDevelopmentRepresentativeAgent` | Partnerships, strategic alliances, market expansion |
| `InsideSalesRepresentativeAgent` | Remote and inbound sales execution |
| `AccountExecutiveAgent` | Closing, account growth, revenue optimization |
| `CustomerSuccessManagerAgent` | Onboarding, retention, expansion |
| `ProjectManagerAgent` | Planning, resourcing, risk, stakeholder comms on committed work |
| `CampaignManagerAgent` | Campaign **execution**, performance optimization, multi-channel coordination |
| `ContentAnalystAgent` | Content performance analysis, audience insight, SEO |

### Nested modules

| Module | Component | What it delivers |
|---|---|---|
| [`support/`](modules/support/) | `modules/` | Tier-1/2 support: capture feedback, draft GitHub issues, inspect open issues |
| `document/` | `modules/` | File → markdown → chunk → embed → vector store; 13 pipelines + `DocumentAgent` |
| `ontology_engineer/` | `modules/` | RDF/OWL modelling, entity resolution, ontology→YAML; `SevenBucketsAgent` |

> **In-flight move.** `document/` and `ontology_engineer/` were relocated here from
> `signals/pipelines/`. Their internal imports and `config.local.yaml` still reference
> `naas_abi_marketplace.domains.signals.pipelines.*`, which no longer exists on disk — see
> [Known issue](#known-issue) below. [`../AGENT.md`](../AGENT.md) still records the standing
> decision that `document` is a signals module; one of the two has to give.

## What belongs here

- Selling: prospecting, qualification, closing, account management
- Delivering committed work: projects, implementations, onboarding
- Customer support and incident handling
- Executing (not designing) campaigns and programmes
- Measuring the performance of work in flight

## Boundary tests

**vs [`plans/`](../plans/) (S5) — the timeline test.**
Operations is *now*; plans is *next*. Running this quarter's campaign is operations; designing next
year's is plans. `CampaignManagerAgent` sits here and `ContentStrategistAgent` sits in plans for
exactly this reason.

**vs [`external/`](../external/) (S9) — customer or audience.**
If the counterparty is a paying customer in a commercial relationship, it is operations. If it is a
broader audience, community, partner body or the public, it is external. Answering a support ticket
is S3; moderating the community forum is S9.

**vs [`intelligence/`](../intelligence/) (S2) — acting or knowing.**
Researching a prospect is intelligence; running the deal is operations. When a module does both,
file it by its output.

**vs [`finance/`](../finance/) (S8) — the deal or the ledger.**
Closing the contract is operations. Invoicing it, recognizing the revenue and chasing payment is
finance.

## Filing a module here

`operations/<component>/<module>/`, where `<component>` is the module's dominant deliverable. Flat
role agents sit directly in `agents/`; anything with its own `__init__.py`, workflows or pipelines
goes under `modules/`. See [`../AGENT.md`](../AGENT.md) for the full filing rules and
[`../README.md`](../README.md) for the framework.

## Known issue

Deep imports inside `modules/document/` and `modules/ontology_engineer/` still point at the old
`domains.signals.pipelines.*` path and currently raise `ModuleNotFoundError`. The same stale path
appears in `config.local.yaml` and in the default `#soft` module list in
`libs/naas-abi/naas_abi/__init__.py`. Resolving the move means rewriting those prefixes (or moving
the two modules back) — see the *Moving an existing module* checklist in
[`../AGENT.md`](../AGENT.md).
