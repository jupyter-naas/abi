# AGENT.md — How to file a module in the staff framework

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/domains/`.
> This file explains the **decision logic**. For the structure itself, read [`README.md`](README.md).
> For the module index, read [`AGENTS.md`](AGENTS.md).

Filing a module takes two decisions, in this order:

1. **Which bucket?** — determined by the *organizational function* the module serves.
2. **Which component folder?** — determined by what the module *primarily is*.

Result: `domains/<bucket>/<component>/<module>/`.

---

## Decision 1 — Which bucket?

### The question to ask

> **What organizational function does this serve?**

Not *what technology does it use*, not *which department would own it*, not *who asked for it*.

A Postgres integration is not "signals because it is a database". A Postgres integration used to
run payroll queries serves **personnel**; used to serve the data platform it serves **signals**.
Technology is not function. If you find yourself filing by tech stack, you are answering the
wrong question.

### The nine questions

Each bucket answers exactly one question. Find the one your module answers:

| Bucket | The question it answers |
|---|---|
| `personnel` | *Who is in the organization, and what is their status?* |
| `intelligence` | *What is true about the world outside us?* |
| `operations` | *How do we execute the mission we are on right now?* |
| `logistics` | *What physical or contracted resources do we need, and where are they?* |
| `plans` | *What should we do next, and how will we get there?* |
| `signals` | *How does information move and get stored inside the organization?* |
| `training` | *How do our people become capable of their work?* |
| `finance` | *Where does the money go, and what is it worth?* |
| `external` | *How do we relate to people and bodies outside the organization?* |

### Tie-breakers

These are the ambiguities that actually come up.

**`operations` vs `plans` — the timeline test.**
Operations is *now*; plans is *next*. Executing this quarter's campaign is `operations`;
designing next year's is `plans`. If the module acts on committed work, it is operations. If it
produces a decision about work not yet committed, it is plans.

**`intelligence` vs `signals` — inside or outside.**
Intelligence is about the world *outside* the organization. Signals is about information moving
*inside* it. A competitor-monitoring module is intelligence; a document-ingestion pipeline that
serves every internal team is signals — even though both end up producing searchable text.

**`signals` vs `logistics` — information or materiel.**
S4 in the staff system is explicitly physical: materiel, transport, facilities, medical. If the
thing being moved or stored is *information*, it is signals. If it is *goods, money-as-assets, or
physical space*, it is logistics. This is why `document` is signals: it moves bytes, not boxes.

**`external` vs `operations` — audience or customer.**
If the counterparty is a paying customer in a commercial relationship, it is operations
(sales, success, support). If the counterparty is a broader audience, community, partner body or
public, it is external.

**`intelligence` vs `plans` — analysis or decision.**
Intelligence tells you what is true. Plans decides what to do about it. A module that measures
content performance is intelligence; a module that decides the next content calendar is plans.

**Cross-cutting modules.** If a module genuinely serves every bucket equally — an LLM provider, a
generic storage adapter — it does not belong in `domains/` at all. Those live at the marketplace
top level (`ai/`, `applications/`).

**Still stuck?** A module that plausibly fits two buckets is usually doing two jobs. Prefer
splitting it over guessing. If it cannot be split, file it under the bucket that owns its
*output*, not its input.

---

## Decision 2 — Which component folder?

### The rule: primary component

File the module under the component folder matching **what the module principally is**. Look at
what the module actually contains and pick the dominant one.

```
<bucket>/agents/        module whose deliverable is a conversational agent
<bucket>/apps/          module whose deliverable is a launchable web app
<bucket>/workflows/     module whose deliverable is multi-step automations
<bucket>/pipelines/     module whose deliverable is data processing
<bucket>/integrations/  module whose deliverable is a third-party API wrapper
<bucket>/ontologies/    module whose deliverable is vocabulary / RDF schema
```

**The module keeps its own internal structure.** Filing a module under `agents/` does not flatten
it. `finance/agents/accountant/` still contains `accountant/agents/`, `accountant/workflows/`,
`accountant/ontologies/` and `accountant/models/`. The outer folder says *what kind of module
this is*; the inner folders are the module's own shape, unchanged.

### Worked examples

**Single-component modules — unambiguous.**

`financial_cockpit` contains only `apps/` (311 files, a P&L and treasury dashboard). Nothing else.
→ `finance/apps/financial_cockpit/`

`organizations` contains only `ontologies/`. Nothing else.
→ `intelligence/ontologies/organizations/`

**Multi-component modules — pick the dominant one.**

`accountant` contains 1 agent, 4 workflows, 1 model, 3 ontologies. The workflows and ontologies
exist to support the agent; the agent is the deliverable. This shape is shared by 20 role modules.
→ `finance/agents/accountant/`

`wsr` contains 125 files under `apps/` (a dashboard with its own API and web frontend) plus 1
agent and 2 ontologies. The dashboard is overwhelmingly the point.
→ `intelligence/apps/wsr/`

`document` contains 13 pipelines, 3 agents, 6 ontologies, 1 orchestration. It is a processing
chain — file → markdown → chunk → embed → vector store — with an agent bolted on top.
→ `signals/pipelines/document/`

`support` contains 3 agents and 2 workflows. Agent-dominant.
→ `operations/agents/support/`

### The genuinely balanced case

`ontology_engineer` has 2 agents, 2 workflows, 2 pipelines, 2 ontologies and 1 util — no
component dominates on file count. It is filed under `signals/pipelines/` because its centre of
gravity is transformation work (entity resolution, individual merging, ontology-to-YAML
conversion) with `SevenBucketsAgent` as the interface to it, rather than an agent with supporting
scripts. `signals/agents/` would also be defensible.

When a module is this balanced, ask: **if you deleted the agent, would the module still be
useful?** If yes, it is a pipeline/workflow module with an agent front-end. If no, it is an agent
module.

---

## Standing decisions

Judgment calls already made, recorded so they are not re-litigated:

**`document` is `signals`, not `logistics`.** Logistics in the staff system means materiel —
physical goods, transport, facilities. `document` moves information, not goods. Reading "supply
chain of documents" into S4 stretches the doctrine and would leave signals without its knowledge
layer. It sits with `data-engineer`, `devops-engineer` and `ontology_engineer`.

**The content cluster is split by function, not kept as a team.** `content-analyst` →
intelligence, `content-strategist` and `campaign-manager` → plans, `content-creator` and
`community-manager` → external. The staff system files by what work *is*. Grouping all five as
"marketing" would reintroduce exactly the department-based filing this framework replaces.

**`logistics` and `training` are empty on purpose.** They are scaffolded with no modules. Do not
fill them with loosely-related modules to make the tree look complete — an empty bucket is an
accurate statement that the marketplace has no coverage there yet. See the README for what
belongs in each.

**`ai/` and `applications/` stay at the top level.** LLM providers are cross-cutting: every
bucket depends on them, so they map to no single staff section. `applications/` was left in place
by decision; the README carries a non-binding index of which bucket each application serves.

---

## Adding a new module — checklist

1. Answer *what organizational function does this serve?* → pick the bucket.
2. Identify the dominant component → pick the component folder.
3. Create `domains/<bucket>/<component>/<module>/` following the standard module shape
   (see the [marketplace master guide](../../AGENTS.md)).
4. No `__init__.py` is needed at the bucket or component level — `domains/` and every level
   below it are PEP 420 namespace packages.
5. If the module is a loadable `ABIModule`, its `__init__.py` goes in the **module** directory.
   `module_root_path` resolves from the class file location, so nesting depth is irrelevant —
   `ontologies/` auto-loading and `apps/<name>/manifest.json` discovery both keep working.
6. Add a row to the module map in [`README.md`](README.md) with a one-line rationale.
7. Add a row to the index in [`AGENTS.md`](AGENTS.md).

## Moving an existing module

Moving a loadable module changes its dotted path. Sweep, in order:

1. `config.local.yaml` and `config.remote.yaml` — `module:` entries.
2. `libs/naas-abi/naas_abi/__init__.py` — the default `#soft` module list.
3. Intra-module self-imports — a module importing its own submodules by absolute path.
4. **Hardcoded filesystem paths in string literals** — these do not look like imports and are
   easy to miss. `SevenBucketsAgent.py` has an `ONTOLOGIES_DIR` constant; several workflows embed
   TTL paths. Grep for `naas_abi_marketplace/` with slashes, not just dots.
5. Regenerate `docs/reference/` — it is generated, never hand-edited.
6. Leave the `pyproject.toml` extras names alone — `domains-document` is a published install
   target, not an import path.

Be aware that app `app_id` values are `"<module_path>:<app_name>"` and are persisted per
workspace. Moving a module that ships an app orphans its stored enable/disable state.

## Further reading

- [Staff (military) — continental staff system](https://en.wikipedia.org/wiki/Staff_(military))
- [NCOR BFO-Process-Ledger — BPL process ontologies](https://github.com/NCOR-Organization/BFO-Process-Ledger/tree/master/src/ontology/bpl-processes)
