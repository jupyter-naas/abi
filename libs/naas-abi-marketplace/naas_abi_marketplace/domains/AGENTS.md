# Domain Modules — AGENTS.md

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/domains/`. Quick index of the modules in this tree.
>
> - **What the structure is and why** → [`README.md`](README.md)
> - **How to decide where a new module goes** → [`AGENT.md`](AGENT.md)
> - **Module shape and marketplace conventions** → [marketplace master guide](../../AGENTS.md)

## What's here

`domains/` is organized by the **continental staff system** — nine function-based buckets
(S1–S9) that map onto any organization, commercial or not. Modules are filed as:

```
domains/<bucket>/<component>/<module>/
```

`<component>` is the module's **primary component** (`agents/`, `apps/`, `pipelines/`,
`ontologies/`, …). Each module keeps its own internal structure — `finance/agents/accountant/`
still contains `accountant/agents/`, `accountant/workflows/` and so on.

## Capability legend

**A** = agent, **W** = workflows, **P** = pipelines, **O** = ontologies, **M** = pinned models,
**X** = apps.

## Module index

### S1 — `personnel/` · people, HR, staffing, records

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/human-resources-manager/`](personnel/agents/human-resources-manager/) | AWOM | `HumanResourcesAgent` | HR ops, hiring, policy |

### S2 — `intelligence/` · collection, analysis, situational awareness

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/osint-researcher/`](intelligence/agents/osint-researcher/) | AWOM | `OSINTResearcherAgent` | Open-source intelligence research |
| [`agents/private-investigator/`](intelligence/agents/private-investigator/) | AWOM | `PrivateInvestigatorAgent` | Investigative research workflows |
| [`agents/content-analyst/`](intelligence/agents/content-analyst/) | AWOM | `ContentAnalystAgent` | Content performance analysis |
| [`apps/wsr/`](intelligence/apps/wsr/) | AXO | `WSRAgent` | World Situation Room — global situational-awareness dashboard |
| [`ontologies/organizations/`](intelligence/ontologies/organizations/) | O | — | Organisation ontology (vocabulary only, no agent) |

### S3 — `operations/` · executing the current mission

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/account-executive/`](operations/agents/account-executive/) | AWOM | `AccountExecutiveAgent` | Mid-to-late funnel selling, deal management |
| [`agents/sales-development-representative/`](operations/agents/sales-development-representative/) | AWOM | `SalesDevelopmentRepresentativeAgent` | Outbound prospecting (SDR) |
| [`agents/business-development-representative/`](operations/agents/business-development-representative/) | AWOM | `BusinessDevelopmentRepresentativeAgent` | Inbound qualification (BDR) |
| [`agents/inside-sales-representative/`](operations/agents/inside-sales-representative/) | AWOM | `InsideSalesRepresentativeAgent` | Inside-sales execution |
| [`agents/customer-success-manager/`](operations/agents/customer-success-manager/) | AWOM | `CustomerSuccessManagerAgent` | Onboarding, retention, expansion |
| [`agents/support/`](operations/agents/support/) | AW | `SupportAgent` | Tier-1/2 customer support |
| [`agents/project-manager/`](operations/agents/project-manager/) | AWOM | `ProjectManagerAgent` | Project planning, tracking, comms |

### S4 — `logistics/` · procurement, supply, facilities, assets

*Reserved — no modules yet.* See [README](README.md#reserved-buckets).

### S5 — `plans/` · future operations, strategy, campaign design

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/content-strategist/`](plans/agents/content-strategist/) | AWOM | `ContentStrategistAgent` | Editorial calendars, content strategy |
| [`agents/campaign-manager/`](plans/agents/campaign-manager/) | AWOM | `CampaignManagerAgent` | Campaign planning, execution, measurement |

### S6 — `signals/` · engineering, IT, data & knowledge infrastructure

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/software-engineer/`](signals/agents/software-engineer/) | AWOM | `SoftwareEngineerAgent` | Code, architecture, code review, testing, debugging |
| [`agents/devops-engineer/`](signals/agents/devops-engineer/) | AWOM | `DevOpsEngineerAgent` | CI/CD, infrastructure, deployments, observability |
| [`agents/data-engineer/`](signals/agents/data-engineer/) | AWOM | `DataEngineerAgent` | Pipelines, warehousing, ETL, data modelling |
| [`pipelines/document/`](signals/pipelines/document/) | APXO | `DocumentAgent` | File → markdown → chunk → embed → vector store |
| [`pipelines/ontology_engineer/`](signals/pipelines/ontology_engineer/) | AWPO | `SevenBucketsAgent` | RDF/OWL design, BFO/CCO modelling, entity resolution |

### S7 — `training/` · onboarding, enablement, certification

*Reserved — no modules yet.* See [README](README.md#reserved-buckets).

### S8 — `finance/` · accounting, treasury, control, contracts

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/accountant/`](finance/agents/accountant/) | AWOM | `AccountantAgent` | Bookkeeping, journals, period close |
| [`agents/financial-controller/`](finance/agents/financial-controller/) | AWOM | `FinancialControllerAgent` | Controlling, reporting, compliance |
| [`agents/treasurer/`](finance/agents/treasurer/) | AWOM | `TreasurerAgent` | Cash management, liquidity |
| [`apps/financial_cockpit/`](finance/apps/financial_cockpit/) | X | — | P&L, treasury and performance dashboard (app only) |

### S9 — `external/` · community, brand, public affairs, partnerships

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/content-creator/`](external/agents/content-creator/) | AWOM | `ContentCreatorAgent` | Long-form writing, copy generation |
| [`agents/community-manager/`](external/agents/community-manager/) | AWOM | `CommunityManagerAgent` | Community engagement, moderation |

Total: **26 modules** across 7 populated buckets, 2 reserved.

## Module shape (recap)

Unchanged by the bucketing — only the path to the module changed.

```
domains/<bucket>/<component>/<module>/
├── __init__.py          # ABIModule(...) — only for loadable modules
├── agents/
│   ├── <RoleName>Agent.py
│   └── <RoleName>Agent_test.py
├── workflows/           # role-specific multi-step automations
├── pipelines/           # (when present) reusable data pipelines
├── apps/                # (when present) launchable web apps + manifest.json
├── ontologies/          # role vocabulary (.ttl files + generated .py classes)
├── models/              # (when present) pinned ChatModel overrides
└── on_load_test.py      # smoke test for ABIModule.on_load()
```

`domains/`, every bucket and every component folder are PEP 420 namespace packages — no
`__init__.py` is needed above the module directory.

Note: the 20 role modules have **no** `__init__.py` and are not imported as Python modules; they
are agent-definition folders. Only `document`, `ontology_engineer`, `organizations`, `support`,
`wsr` and `financial_cockpit` are loadable `ABIModule`s.

## Agent conventions

Every `<RoleName>Agent.py` exposes:

```python
NAME         = "Software Engineer"
SLUG         = "software-engineer"           # matches the module directory name
TYPE         = "domain-expert"
DESCRIPTION  = "..."                         # one-line catalog blurb
AVATAR_URL   = "https://.../<slug>.png"
MODEL        = "deepseek-r1"                 # canonical id resolved via ModelRegistryService
SYSTEM_PROMPT = """..."""                    # role prompt with expertise + style
INTENTS      = [Intent(...), ...]

def create_agent(
    shared_state: AgentSharedState | None = None,
    configuration: AgentConfiguration | None = None,
) -> IntentAgent:
    ...
```

`SLUG` values are **unchanged** by the reorganization — the bucket is a filing decision, not a
rename. The agent is an `IntentAgent` (see [`services/agent/AGENTS.md`](../../../naas-abi-core/naas_abi_core/services/agent/AGENTS.md)) so prompts route to intent-matched workflows / tools instead of free-form replies.

## Configuration example

```yaml
modules:
  - module: naas_abi_marketplace.domains.operations.agents.support
    enabled: true
    config:
      default_repository: "jupyter-naas/abi"
```

Domain modules usually only need `datastore_path` — credentials are inherited from the LLM module
they depend on.

## Adding a new domain module

Read [`AGENT.md`](AGENT.md) first — it covers picking the bucket and the component folder. Then:

1. Create `domains/<bucket>/<component>/<module>/`.
2. Add `__init__.py` declaring `dependencies.modules = ["naas_abi_marketplace.ai.<provider>"]`
   and the services you need (commonly `ObjectStorageService`, `TripleStoreService`).
3. Add `agents/<RoleName>Agent.py` with the conventional constants and `create_agent`.
4. Add `workflows/` for canonical role tasks (e.g. `CodeReviewWorkflow`).
5. Add `ontologies/<Topic>.ttl` for role-specific vocabulary; let `BaseModule.on_load()` generate
   the Python classes.
6. Add tests: `<RoleName>Agent_test.py` and `on_load_test.py`.
7. Reuse `signals/agents/software-engineer/` or `finance/agents/accountant/` as a scaffold.
8. Add a row to the map in [`README.md`](README.md) and to the index above.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/signals
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/signals/agents/software-engineer/agents/SoftwareEngineerAgent_test.py -v
```
