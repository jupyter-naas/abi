# Domain Expert Modules — AGENTS.md

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/domains/`. Quick index for role-specific expert agents. See the [marketplace master guide](../../AGENTS.md) for module shape and conventions.

## What's here

Each subdirectory is a marketplace module modelling a **professional role**. Every module:

- Names the directory in `kebab-case` (e.g. `software-engineer`), the agent file in `PascalCase` (e.g. `SoftwareEngineerAgent.py`), and uses the kebab-case name as the agent `SLUG`.
- Declares one LLM module in `dependencies.modules` (commonly `ai.chatgpt`; some pin a specific model).
- Ships an `IntentAgent` with a role-flavoured `SYSTEM_PROMPT` and a curated set of `workflows/`.
- Carries an `ontologies/` folder with TTL files describing the role's vocabulary.

## Capability legend

**A** = agent, **W** = workflows, **P** = pipelines, **O** = ontologies, **M** = pinned models.

## Domain index

### Engineering & data

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`software-engineer/`](software-engineer/) | AWOM | `SoftwareEngineerAgent` | Code, architecture, code review, testing, debugging |
| [`devops-engineer/`](devops-engineer/) | AWOM | `DevOpsEngineerAgent` | CI/CD, infrastructure, deployments, observability |
| [`data-engineer/`](data-engineer/) | AWOM | `DataEngineerAgent` | Pipelines, warehousing, ETL, data modelling |
| [`ontology_engineer/`](ontology_engineer/) | AWPO | `SevenBucketsAgent` | RDF/OWL design, BFO/CCO modelling, ontology engineering |

### Sales & customer

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`account-executive/`](account-executive/) | AWOM | `AccountExecutiveAgent` | Mid-to-late funnel selling, deal management |
| [`sales-development-representative/`](sales-development-representative/) | AWOM | `SalesDevelopmentRepresentativeAgent` | Outbound prospecting (SDR) |
| [`business-development-representative/`](business-development-representative/) | AWOM | `BusinessDevelopmentRepresentativeAgent` | Inbound qualification (BDR) |
| [`inside-sales representative/`](inside-sales%20representative/) | AWOM | `InsideSalesRepresentativeAgent` | Inside-sales execution |
| [`customer-success-manager/`](customer-success-manager/) | AWOM | `CustomerSuccessManagerAgent` | Onboarding, retention, expansion |
| [`support/`](support/) | AW | `SupportAgent` | Tier-1/2 customer support |

### Marketing & content

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`campaign-manager/`](campaign-manager/) | AWOM | `CampaignManagerAgent` | Campaign planning, execution, measurement |
| [`community-manager/`](community-manager/) | AWOM | `CommunityManagerAgent` | Community engagement, moderation |
| [`content-analyst/`](content-analyst/) | AWOM | `ContentAnalystAgent` | Content performance analysis |
| [`content-creator/`](content-creator/) | AWOM | `ContentCreatorAgent` | Long-form writing, copy generation |
| [`content-strategist/`](content-strategist/) | AWOM | `ContentStrategistAgent` | Editorial calendars, content strategy |

### Finance & ops

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`accountant/`](accountant/) | AWOM | `AccountantAgent` | Bookkeeping, journals, period close |
| [`financial-controller/`](financial-controller/) | AWOM | `FinancialControllerAgent` | Controlling, reporting, compliance |
| [`treasurer/`](treasurer/) | AWOM | `TreasurerAgent` | Cash management, liquidity |

### Research & investigation

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`osint-researcher/`](osint-researcher/) | AWOM | `OSINTResearcherAgent` | Open-source intelligence research |
| [`private-investigator/`](private-investigator/) | AWOM | `PrivateInvestigatorAgent` | Investigative research workflows |

### People & projects

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`human-resources-manager/`](human-resources-manager/) | AWOM | `HumanResourcesAgent` | HR ops, hiring, policy |
| [`project-manager/`](project-manager/) | AWOM | `ProjectManagerAgent` | Project planning, tracking, comms |

### Reference / utility

| Module | Caps | Agent | Role |
|---|:---:|---|---|
| [`document/`](document/) | APO | `DocumentAgent` | Document parsing / extraction utilities |
| [`organizations/`](organizations/) | O | — | Organisation ontology (vocabulary only, no agent) |

Total: **24 domain modules**.

## Module shape (recap)

```
domains/<role-kebab>/
├── __init__.py          # ABIModule(dependencies=ModuleDependencies(modules=["ai.<provider>"], services=[...]))
├── agents/
│   ├── <RoleName>Agent.py
│   └── <RoleName>Agent_test.py
├── workflows/           # role-specific multi-step automations
├── pipelines/           # (when present) reusable data pipelines
├── ontologies/          # role vocabulary (.ttl files + generated .py classes)
├── models/              # (when present) pinned ChatModel overrides for this domain
└── on_load_test.py      # smoke test for ABIModule.on_load()
```

## Agent conventions

Every `<RoleName>Agent.py` exposes:

```python
NAME         = "Software Engineer"
SLUG         = "software-engineer"           # matches the directory name
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

The agent is an `IntentAgent` (see [`services/agent/AGENTS.md`](../../../naas-abi-core/naas_abi_core/services/agent/AGENTS.md)) so prompts route to intent-matched workflows / tools instead of free-form replies.

## Configuration example

```yaml
modules:
  - module: naas_abi_marketplace.domains.software-engineer
    enabled: true
    config:
      datastore_path: "software-engineer"
```

Domain modules usually only need `datastore_path` — credentials are inherited from the LLM module they depend on.

## Adding a new domain

1. Pick the kebab-case `<role>` and create `domains/<role>/`.
2. Add `__init__.py` declaring `dependencies.modules = ["naas_abi_marketplace.ai.<provider>"]` and the services you need (commonly `ObjectStorageService`, `TripleStoreService`).
3. Add `agents/<RoleName>Agent.py` with the conventional constants and `create_agent`. Match the agent class style of nearby roles.
4. Add `workflows/` for canonical role tasks (e.g. `CodeReviewWorkflow`, `ArchitectureDesignWorkflow`).
5. Add `ontologies/<Topic>.ttl` for any role-specific vocabulary; let `BaseModule.on_load()` generate the Python classes.
6. Add tests:
   - `<RoleName>Agent_test.py` — `create_agent().invoke(prompt)` over realistic role queries.
   - `on_load_test.py` — `ABIModule().on_load()` with minimal config.
7. Reuse existing `software-engineer/` or `accountant/` as a copy-from scaffold.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/software-engineer
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/software-engineer/agents/SoftwareEngineerAgent_test.py -v
```
