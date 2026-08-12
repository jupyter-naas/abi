# Domains — The 9-Bucket Staff Framework

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/domains/`.
> For **how to decide** where a new module goes, read [`AGENT.md`](AGENT.md).
> For the per-module index with agent names, read [`AGENTS.md`](AGENTS.md).

## Why this structure

`domains/` used to be a flat list of 24 job titles — `accountant`, `software-engineer`,
`osint-researcher`. A job title is a poor filing key: titles differ between a bank, a university
and an NGO even when the underlying *function* is identical, and a flat list gives no answer to
"where does this new module go?" or "what are we missing?".

This package is organized instead by the **continental staff system** (S1–S9), the structure
used by most NATO-aligned armed forces to divide the work of a headquarters. It is worth
borrowing for three reasons:

1. **It is function-based, not title-based.** A staff section is defined by the question it
   answers, not by who sits in it. `finance` means the same thing to a defence ministry, a
   research lab and a Series-B startup.
2. **It is complete and non-overlapping.** Nine sections cover everything an organization does
   to sustain itself and act. If a module fits nowhere, that is a genuine signal — either the
   module is doing two jobs, or a bucket needs to be re-read.
3. **It makes gaps visible.** Empty buckets are information. `logistics` and `training` are
   currently empty, which tells you exactly where this marketplace has no coverage yet.

The framework is deliberately **organization-agnostic**. Each bucket below carries both its
military definition and its civilian translation.

## The nine buckets

| # | Bucket | Staff definition | In a civilian organization |
|:--|---|---|---|
| S1 | [`personnel/`](personnel/) | Manpower & personnel. Administration, records, awards, staffing actions. | HR, recruiting, payroll, people ops, employee records |
| S2 | [`intelligence/`](intelligence/) | Intelligence & security. Collecting and analysing information about the environment and adversaries. | Market & competitor research, OSINT, due diligence, situational awareness, risk |
| S3 | [`operations/`](operations/) | Operations. Running the *current* mission — everything needed to execute today. | Revenue execution, delivery, customer support, project execution |
| S4 | [`logistics/`](logistics/) | Logistics. Materiel, transport, facilities, services, medical. | Procurement, supply chain, asset management, facilities, vendor management |
| S5 | [`plans/`](plans/) | Plans & strategy. *Future* operations — what happens after the current one. | Strategy, roadmapping, campaign design, planning cycles |
| S6 | [`signals/`](signals/) | Signal. Communications and information systems. | Engineering, IT, data platform, knowledge management, internal comms |
| S7 | [`training/`](training/) | Training. Organizing and supervising training of the force. | Onboarding, enablement, certification, internal education |
| S8 | [`finance/`](finance/) | Finance. Finance policy, resource management, contracts. | Accounting, treasury, controlling, FP&A, contracts |
| S9 | [`external/`](external/) | CIMIC / civil affairs. Relations with government, civilian and non-governmental bodies. | Community, brand, public affairs, partnerships, external comms |

The key distinction people get wrong is **S3 vs S5**: operations is *now*, plans is *next*.
Running this quarter's campaign is S3; designing next year's is S5.

## Layout

Inside each bucket, modules are filed under the **component folder matching what the module
primarily is**:

```
domains/<bucket>/<component>/<module>/
```

`<component>` mirrors the standard marketplace module shape — `agents/`, `apps/`, `workflows/`,
`pipelines/`, `integrations/`, `ontologies/`. A module keeps its own internal structure intact,
so `finance/agents/accountant/` still contains `accountant/agents/`, `accountant/workflows/`,
`accountant/ontologies/` and `accountant/models/`.

```
domains/
├── personnel/
│   └── agents/human-resources-manager/
├── intelligence/
│   ├── agents/{content-analyst, osint-researcher, private-investigator}/
│   ├── apps/wsr/
│   └── ontologies/organizations/
├── operations/
│   └── agents/{account-executive, business-development-representative,
│               customer-success-manager, inside-sales-representative,
│               project-manager, sales-development-representative, support}/
├── logistics/                                    # reserved — see below
├── plans/
│   └── agents/{campaign-manager, content-strategist}/
├── signals/
│   ├── agents/{data-engineer, devops-engineer, software-engineer}/
│   └── pipelines/{document, ontology_engineer}/
├── training/                                     # reserved — see below
├── finance/
│   ├── agents/{accountant, financial-controller, treasurer}/
│   └── apps/financial_cockpit/
└── external/
    └── agents/{community-manager, content-creator}/
```

## Module map

All 26 modules, with why each one sits where it does.

### S1 — personnel

| Module | Path | Rationale |
|---|---|---|
| `human-resources-manager` | `personnel/agents/` | The staffing, hiring and people-administration function itself |

### S2 — intelligence

| Module | Path | Rationale |
|---|---|---|
| `osint-researcher` | `intelligence/agents/` | Open-source collection — the core S2 discipline |
| `private-investigator` | `intelligence/agents/` | Targeted investigation and due diligence |
| `content-analyst` | `intelligence/agents/` | Analysis, not production — measures and interprets, feeds decisions |
| `organizations` | `intelligence/ontologies/` | Ontology-only module describing organizational entities; the vocabulary intelligence reasons over |
| `wsr` | `intelligence/apps/` | World Situation Room — a global situational-awareness dashboard (flights, conflict, earthquakes, satellites, news). Situational awareness is the S2 product |

### S3 — operations

| Module | Path | Rationale |
|---|---|---|
| `account-executive` | `operations/agents/` | Closing revenue — current mission execution |
| `sales-development-representative` | `operations/agents/` | Pipeline generation, executed now |
| `business-development-representative` | `operations/agents/` | Partnership and outbound execution |
| `inside-sales-representative` | `operations/agents/` | Inbound sales execution |
| `customer-success-manager` | `operations/agents/` | Retention and delivery on existing commitments |
| `support` | `operations/agents/` | Incident and issue handling — the most literal "operations" function |
| `project-manager` | `operations/agents/` | Coordinates execution of work already committed |

### S4 — logistics

Reserved. See [Reserved buckets](#reserved-buckets).

### S5 — plans

| Module | Path | Rationale |
|---|---|---|
| `content-strategist` | `plans/agents/` | Designs what will be produced — future-facing, not execution |
| `campaign-manager` | `plans/agents/` | A campaign is a planned operation with objectives and phases |

### S6 — signals

| Module | Path | Rationale |
|---|---|---|
| `software-engineer` | `signals/agents/` | Builds and maintains the information systems |
| `devops-engineer` | `signals/agents/` | Runs the infrastructure those systems sit on |
| `data-engineer` | `signals/agents/` | Moves and models data — the information plumbing |
| `document` | `signals/pipelines/` | File → markdown → chunk → embed → vector store. Knowledge-management infrastructure. **Not** logistics: S4 is materiel, and documents are information, not goods |
| `ontology_engineer` | `signals/pipelines/` | Knowledge architecture — RDF/OWL/BFO modelling, entity resolution, ontology-to-YAML conversion |

### S7 — training

Reserved. See [Reserved buckets](#reserved-buckets).

### S8 — finance

| Module | Path | Rationale |
|---|---|---|
| `accountant` | `finance/agents/` | Bookkeeping and statutory accounting |
| `treasurer` | `finance/agents/` | Cash and liquidity management |
| `financial-controller` | `finance/agents/` | Control, budgeting, financial reporting |
| `financial_cockpit` | `finance/apps/` | Apps-only module — a P&L / treasury / performance dashboard |

### S9 — external

| Module | Path | Rationale |
|---|---|---|
| `content-creator` | `external/agents/` | Produces the outward-facing artefacts |
| `community-manager` | `external/agents/` | Manages relations with the outside audience — the civil-affairs function |

### Note on the content cluster

The five marketing/content modules are deliberately **split by function** rather than kept
together as a "marketing" team, because the staff system files by what work *is*, not by which
department owns it:

- `content-analyst` → **intelligence** (analyses and measures)
- `content-strategist`, `campaign-manager` → **plans** (design future activity)
- `content-creator`, `community-manager` → **external** (produce and engage now)

## Reserved buckets

Two buckets exist with no modules. They are scaffolded on purpose — an empty bucket is a visible
gap, not an oversight.

**`logistics/` (S4)** — procurement and purchasing, supplier and vendor management, inventory and
asset tracking, facilities, shipping and fulfilment, expense and travel management.

**`training/` (S7)** — employee onboarding, skills assessment and enablement, certification
tracking, curriculum and course generation, internal knowledge testing.

## Reference index — modules NOT in this tree

`applications/` (47 third-party integrations) and `ai/` (19 LLM providers) are **not part of this
reorganization** and have not moved. They keep their own indexes:
[`applications/AGENTS.md`](../applications/AGENTS.md) and [`ai/AGENTS.md`](../ai/AGENTS.md).

The table below is a **non-binding reference** showing which staff function each application
serves. It is useful for finding the right integration for a bucket's work, and it pre-plans a
possible future move. **No files live at these paths.**

| Bucket | Applications that serve it |
|---|---|
| S1 personnel | — |
| S2 intelligence | `arxiv`, `datagouv`, `google_search`, `newsapi`, `openalex`, `openweathermap`, `pubmed`, `sanax`, `sec_gov`, `worldbank`, `yahoofinance` |
| S3 operations | `hubspot`, `salesforce`, `zoho`, `airtable`, `notion`, `google_calendar` |
| S4 logistics | `aws`, `google_maps`, `nebari` |
| S5 plans | `google_analytics`, `powerpoint` |
| S6 signals | `git`, `github`, `postgres`, `algolia`, `bodo`, `naas`, `openrouter`, `slack`, `gmail`, `google_drive`, `google_sheets`, `sharepoint`, `twilio`, `sendgrid` |
| S7 training | — |
| S8 finance | `agicap`, `exchangeratesapi`, `mercury`, `pennylane`, `qonto`, `stripe` |
| S9 external | `instagram`, `linkedin`, `spotify`, `whatsapp_business`, `x`, `youtube` |

`ai/` providers (`anthropic`, `chatgpt`, `gemini`, `mistral`, …) are **cross-cutting** — every
bucket depends on them. They map to no single staff section and should stay at the top level.

## Conventions

Unchanged by this reorganization:

- Bucket directories are lowercase single words and valid Python identifiers.
- Module directories keep their existing naming — `kebab-case` for role modules
  (`software-engineer`), `snake_case` for importable modules (`ontology_engineer`).
- Agent files stay `PascalCase.py`; tests stay `*_test.py`.
- `SLUG` values inside agents are **unchanged** — moving a module does not rename its agent.
- `domains/` and every bucket are PEP 420 namespace packages; no `__init__.py` is needed at the
  bucket or component level.

## Import paths

Modules that are importable ABI modules changed dotted path:

| Before | After |
|---|---|
| `naas_abi_marketplace.domains.document` | `naas_abi_marketplace.domains.signals.pipelines.document` |
| `naas_abi_marketplace.domains.support` | `naas_abi_marketplace.domains.operations.agents.support` |
| `naas_abi_marketplace.domains.ontology_engineer` | `naas_abi_marketplace.domains.signals.pipelines.ontology_engineer` |
| `naas_abi_marketplace.domains.organizations` | `naas_abi_marketplace.domains.intelligence.ontologies.organizations` |
| `naas_abi_marketplace.alpha.wsr` | `naas_abi_marketplace.domains.intelligence.apps.wsr` |
| `naas_abi_marketplace.alpha.financial_cockpit` | `naas_abi_marketplace.domains.finance.apps.financial_cockpit` |

The other 20 role modules have no `__init__.py` and are not imported — they are agent-definition
folders discovered by path.

`alpha/` no longer exists; both of its modules were promoted into buckets.

The pyproject extras `domains-document` and `domains-ontology-engineer` are **unchanged** — they
are published install targets, not import paths.

## Further reading

- [Staff (military) — continental staff system](https://en.wikipedia.org/wiki/Staff_(military))
- [NCOR BFO-Process-Ledger — BPL process ontologies](https://github.com/NCOR-Organization/BFO-Process-Ledger/tree/master/src/ontology/bpl-processes)
