# Abi Doctrine — Capabilities as BFO Dispositions in the Graph

- **Status:** Proposed
- **Date:** 2026-08-03
- **Scope:** `naas_abi_core` agent runtime + triple store (primary), `naas_abi` AbiAgent, Nexus skills layer (secondary)

## Context

`AbiAgent` (the default orchestrator) binds its full leaf-tool surface on every
turn (SPARQL agent-recommendation tools, Nexus admin tools, Slides tools, …)
and the Nexus chat layer injects the **entire** skills catalog — including full
prompt bodies — into the system prompt on every turn. Both are always-resident.

Measured impact on the local default model (`qwen-2.5-3b`, CPU), prompt
"What can you do?": first-call prompt ~4,225 tokens, ~73 s wall clock; the leaf
tools alone are ~67% of that prompt. Beyond latency, a large flat option set
degrades routing quality on small models.

The deeper problem is representational, not just size. Capabilities are modelled
as prompt text (tool descriptions, `when_to_use` strings) and matched by the
model reading that text. But this platform is ontology-grounded: it already
ships `BFO7Buckets.ttl` (`.../nexus/ontology/BFO7Buckets.ttl`) and a triple
store. Matching capabilities by prose is strictly weaker than querying the
graph.

## The BFO 7 buckets (already in-tree)

`BFO7Buckets.ttl` tags the seven top-level categories with interrogatives:

| Bucket | BFO class | Interrogative |
|---|---|---|
| Process | `BFO_0000015` | WHAT happens |
| Temporal region | `BFO_0000008` | WHEN |
| Material entity | `BFO_0000040` | WHO |
| Site | `BFO_0000029` | WHERE |
| Generically dependent continuant / ICE | `BFO_0000031` | HOW WE KNOW |
| Quality | `BFO_0000019` | HOW IT IS |
| Realizable entity — Role `BFO_0000023`, Disposition `BFO_0000016` | | WHY |

Key relations (all defined in that TTL): `bearer of` (`BFO_0000196`) /
`inheres in` (`BFO_0000197`); `has realization` (`BFO_0000054`) / `realizes`
(`BFO_0000055`); `is concretized by` (`BFO_0000058`) / `concretizes`
(`BFO_0000059`); `generically depends on` (`BFO_0000084`).

## Decision

Adopt as Abi doctrine: **a capability is a disposition, encoded in the graph;
Abi's only innate knowledge is the 7 buckets and the realization relations; Abi
resolves what to do by querying the graph, not by carrying capabilities in its
prompt.**

### Principle 1 — Capabilities are dispositions realized in processes

Every tool, skill, workflow, and sub-agent is projected into the graph as:

- a **material entity** (WHO) that is `bearer of`
- a **disposition** (WHY, `BFO_0000016`) that `has realization`
- a **process** (WHAT, `BFO_0000015`).

The "why you would use this" is the disposition; the "what it does" is the
process it realizes. A capability's instructions/schema (a skill prompt, a tool
signature) is an **ICE / generically dependent continuant** (HOW WE KNOW) that
is concretized in that process and referenced by IRI — never inlined into Abi's
standing prompt.

### Principle 2 — Abi is a graph-querying router (API-first)

Abi holds the 7-bucket ontology and **one** parameterised capability-discovery
query. Given the user's intended process, it returns the bearers whose
disposition realizes that process (or a subprocess):

```sparql
SELECT ?bearer ?disposition WHERE {
  ?bearer      <http://purl.obolibrary.org/obo/BFO_0000196> ?disposition .  # bearer_of
  ?disposition <http://purl.obolibrary.org/obo/BFO_0000054> ?process .      # has_realization
  ?process     (abi:subProcessOf)* ?INTENDED .                              # process closure
}
```

Because a small local model cannot reliably author SPARQL, Abi never writes it:
it fills the single `?INTENDED` parameter (resolved against the process
taxonomy — APQC PCF is the natural controlled vocabulary) and runs the vetted
query through `templatablesparqlquery`. This MUST live in the **core agent
runtime** and be exposed via the **`/agents/*` API**, so the CLI (`abi chat`)
and the Nexus client inherit identical resolution with no client-specific code.
(`find_coding_agents` / `find_fastest_agents` already prove templated SPARQL
routing; this generalises them to all capabilities and grounds them in BFO.)

### Principle 3 — Progressive disclosure falls out of the query

Abi loads only the capabilities the discovery query returns for the intended
process. Skill bodies (ICEs) are fetched by IRI only when their disposition
matches; sub-agent tool scoping is a `bearer_of` query per agent. There is no
separate keyword/search mechanism — disclosure is graph retrieval.

### Principle 4 — Deterministic capability/meta answers

"What can you do?" is answered by summarising the dispositions/processes the
graph returns for the current workspace — deterministically, without enumerating
tool schemas. (It is Abi's own first suggestion; it must be correct and fast.)

### Principle 5 — Protect the prompt cache; bound result growth

The stable, cacheable prompt prefix is the small 7-bucket ontology. Volatile
capability sets come from query results, not from rewriting the system prompt
every turn. Large tool results are ICEs: store/offload them and reference by
IRI so working context does not grow unbounded.

### Source of truth

Code-defined tools/agents/skills MUST project their capability triples
(WHO `bearer_of` WHY `has_realization` WHAT) into the graph at load, so the
graph never drifts from code. The existing per-module ontology generation
(`onto2py`) is the projection point.

### Model tiering

Graph-driven disclosure is mandatory for small/local/CPU models. Capable cloud
models may still opt into a broader inline surface where quality allows.

## Consequences

- **Positive:** near-zero standing prompt; capabilities become first-class,
  composable, inferable graph citizens (BFO/PCF subsumption); one core
  mechanism serves API, CLI, and Nexus; disclosure, lazy skills, coordinator
  scoping, and cache stability all follow from the same model.
- **Cost / risk:** requires a capability-projection pass (code → triples), a
  vetted templated discovery query, and per-turn tool (re)binding driven by
  query results (a generalisation of the existing workspace-tool gating). Query
  and process-taxonomy quality must be tuned — a mis-modelled disposition is a
  capability Abi cannot find.
- **Supersedes:** the `ABI_THIN_ROUTER` experiment and any keyword/embedding
  tool-search framing. The `num_predict` generation cap is retained as an
  independent safety net.

## Implementation plan (incremental, API-first)

1. Fix the capability ontology: `capability ⊑ disposition`, projected as
   WHO `bearer_of` WHY `has_realization` WHAT, aligned to the process taxonomy.
2. Project code-defined tools/agents/skills into the graph at load (`onto2py`).
3. Add the parameterised discovery query to `templatablesparqlquery`; give Abi
   that one query + the 7-bucket ontology as its standing knowledge.
4. Resolve Abi's active tool set per turn from query results in the core
   runtime; verify **via `/agents/Abi/completion`**, then confirm CLI + Nexus.
5. Answer capability/meta questions from query results (Principle 4).
6. Migrate Nexus skills to metadata/IRI references (Principle 3) and add
   result offload + cache-friendly deltas (Principle 5).
