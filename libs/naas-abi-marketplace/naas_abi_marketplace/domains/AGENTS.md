# Domain Modules — AGENTS.md

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/domains/`. Quick index of the modules in this tree.
>
> - **What the structure is and why** → [`README.md`](README.md)
> - **How to decide where a new module goes** → [`AGENT.md`](AGENT.md)
> - **Module shape and marketplace conventions** → [marketplace master guide](../../AGENTS.md)

## What's here

`domains/` is organized by the **continental staff system** — nine function-based subsystems
(S1–S9) that map onto any organization, commercial or not. Modules are filed as:

```
domains/<bucket>/<component>/<module>/
```

`<component>` is the module's **primary component** (`agents/`, `apps/`, `pipelines/`,
`ontologies/`, …). Many agent buckets now keep flat `*Agent.py` files directly under
`<bucket>/agents/` (no nested role module). Nested modules remain for apps, pipelines, and
signals agents that still carry workflows/ontologies.

## Capability legend

**A** = agent, **W** = workflows, **P** = pipelines, **O** = ontologies, **M** = pinned models,
**X** = apps, **Q** = templatable SPARQL queries exposed as agent tools.

## Module index

### S1 — `personnel/` · people, HR, staffing, records

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`personnel/`](personnel/) | AOQ | `PersonnelAgent` | HR ops, hiring, policy — bucket-level module, agent sits directly in [`personnel/agents/`](personnel/agents/) |

### S2 — `intelligence/` · collection, analysis, situational awareness

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/OSINTResearcherAgent.py`](intelligence/agents/OSINTResearcherAgent.py) | A | `OSINTResearcherAgent` | Open-source intelligence research |
| [`agents/PrivateInvestigatorAgent.py`](intelligence/agents/PrivateInvestigatorAgent.py) | A | `PrivateInvestigatorAgent` | Investigative research workflows |
| [`apps/wsr/`](intelligence/apps/wsr/) | AXO | `WSRAgent` | World Situation Room — global situational-awareness dashboard |
| [`ontologies/organizations/`](intelligence/ontologies/organizations/) | OQ | — | Organization vocabulary + alliance/restructuring process ontologies + 10 SPARQL query tools (no agent yet) |

### S3 — `operations/` · executing the current mission

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/AccountExecutiveAgent.py`](operations/agents/AccountExecutiveAgent.py) | A | `AccountExecutiveAgent` | Mid-to-late funnel selling, deal management |
| [`agents/SalesDevelopmentRepresentativeAgent.py`](operations/agents/SalesDevelopmentRepresentativeAgent.py) | A | `SalesDevelopmentRepresentativeAgent` | Outbound prospecting (SDR) |
| [`agents/BusinessDevelopmentRepresentativeAgent.py`](operations/agents/BusinessDevelopmentRepresentativeAgent.py) | A | `BusinessDevelopmentRepresentativeAgent` | Inbound qualification (BDR) |
| [`agents/InsideSalesRepresentativeAgent.py`](operations/agents/InsideSalesRepresentativeAgent.py) | A | `InsideSalesRepresentativeAgent` | Inside-sales execution |
| [`agents/CustomerSuccessManagerAgent.py`](operations/agents/CustomerSuccessManagerAgent.py) | A | `CustomerSuccessManagerAgent` | Onboarding, retention, expansion |
| [`modules/support/`](operations/modules/support/) | AW | `SupportAgent` | Tier-1/2 customer support |
| [`agents/CampaignManagerAgent.py`](operations/agents/CampaignManagerAgent.py) | A | `CampaignManagerAgent` | Campaign planning, execution, measurement |
| [`agents/ContentAnalystAgent.py`](operations/agents/ContentAnalystAgent.py) | A | `ContentAnalystAgent` | Content performance analysis |
| [`agents/ProjectManagerAgent.py`](operations/agents/ProjectManagerAgent.py) | A | `ProjectManagerAgent` | Project planning, tracking, comms |

### S4 — `logistics/` · procurement, supply, facilities, assets

*Reserved — no modules yet.* See [README](README.md#reserved-buckets).

### S5 — `plans/` · future operations, strategy, campaign design

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/ContentStrategistAgent.py`](plans/agents/ContentStrategistAgent.py) | A | `ContentStrategistAgent` | Editorial calendars, content strategy |

### S6 — `signals/` · engineering, IT, data & knowledge infrastructure

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/SoftwareEngineerAgent.py`](signals/agents/SoftwareEngineerAgent.py) | A | `SoftwareEngineerAgent` | Code, architecture, code review, testing, debugging |
| [`agents/DevOpsEngineerAgent.py`](signals/agents/DevOpsEngineerAgent.py) | A | `DevOpsEngineerAgent` | CI/CD, infrastructure, deployments, observability |
| [`agents/DataEngineerAgent.py`](signals/agents/DataEngineerAgent.py) | A | `DataEngineerAgent` | Pipelines, warehousing, ETL, data modelling |
| [`pipelines/document/`](signals/pipelines/document/) | APXO | `DocumentAgent` | File → markdown → chunk → embed → vector store |
| [`pipelines/ontology_engineer/`](signals/pipelines/ontology_engineer/) | AWPO | `SevenBucketsAgent` | RDF/OWL design, BFO/CCO modelling, entity resolution |

### S7 — `training/` · onboarding, enablement, certification

*Reserved — no modules yet.* See [README](README.md#reserved-buckets).

### S8 — `finance/` · accounting, treasury, control, contracts

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/AccountantAgent.py`](finance/agents/AccountantAgent.py) | A | `AccountantAgent` | Bookkeeping, journals, period close |
| [`agents/FinancialControllerAgent.py`](finance/agents/FinancialControllerAgent.py) | A | `FinancialControllerAgent` | Controlling, reporting, compliance |
| [`agents/TreasurerAgent.py`](finance/agents/TreasurerAgent.py) | A | `TreasurerAgent` | Cash management, liquidity |
| [`apps/financial_cockpit/`](finance/apps/financial_cockpit/) | X | — | P&L, treasury and performance dashboard (app only) |

### S9 — `external/` · community, brand, public affairs, partnerships

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`agents/ContentCreatorAgent.py`](external/agents/ContentCreatorAgent.py) | A | `ContentCreatorAgent` | Long-form writing, copy generation |
| [`agents/CommunityManagerAgent.py`](external/agents/CommunityManagerAgent.py) | A | `CommunityManagerAgent` | Community engagement, moderation |

Total: filed modules across populated buckets. Several buckets (`personnel`, `operations`,
`plans`, `intelligence`, `finance`, `external`, `signals`) carry agents flat under
`<bucket>/agents/`.

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

Note: every bucket and every filed module carries an `__init__.py` declaring an `ABIModule`, so
all of them are loadable. `personnel` has no filed module — `PersonnelAgent.py` sits directly
in `personnel/agents/` and is discovered by the bucket module.

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
  - module: naas_abi_marketplace.domains.operations
    enabled: true
    config:
      datastore_path: "operations"
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
7. Reuse `personnel/agents/PersonnelAgent.py` or `finance/agents/AccountantAgent.py` as a scaffold.
8. Add a row to the map in [`README.md`](README.md) and to the index above.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/signals
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/signals/agents/SoftwareEngineerAgent_test.py -v
```
