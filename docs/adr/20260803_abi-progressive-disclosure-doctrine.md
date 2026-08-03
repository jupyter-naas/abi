# Abi Doctrine — Progressive Disclosure of Tools and Skills

- **Status:** Proposed
- **Date:** 2026-08-03
- **Scope:** `naas_abi_core` agent runtime (primary), `naas_abi` AbiAgent, Nexus skills layer (secondary)

## Context

`AbiAgent` (the default orchestrator) binds its full leaf-tool surface on every
turn: ~6 SPARQL agent-recommendation tools, ~14 Nexus admin tools, the Slides
tool set, and the generic workspace tools — plus a long system prompt whose
`<slides_guidelines>` block is always resident. Every one of those tool JSON
schemas is re-sent to the model on every call.

Measured impact on the local default model (`qwen-2.5-3b`, CPU) for the prompt
"What can you do?":

| Configuration | First-call prompt | Wall clock |
|---|---|---|
| Full tool surface (current default) | ~4,225 tokens | ~73 s |
| Leaf tools removed (thin router probe) | ~1,384 tokens (−67%) | ~26 s (−64%) |

The leaf tools account for ~2,840 tokens (67%) of the first prompt and roughly
two-thirds of the latency. On a small/CPU-served model this also degrades
routing quality: too many simultaneous options push the model toward degenerate
output (a separate safety cap, `num_predict`, was added to stop the resulting
non-terminating generations).

The Nexus skills layer has the same shape: `ChatService._build_skills_block()`
injects the **entire** skills catalog — name, description, **and full prompt
body** — into the system prompt on every turn. Skill payload therefore grows
linearly with the number of saved skills, all of it always-resident.

Naively deleting tools is not the answer: the thin-router probe made
"What can you do?" return an empty answer, because that answer is derived from
the very tool list that was removed.

## Decision

Adopt **progressive disclosure** as Abi doctrine for capabilities (tools and
skills). Capabilities are advertised cheaply and loaded on demand, instead of
being bound in full on every turn.

### Principle 1 — Minimal core, tools disclosed on demand (API-first)

The agent binds only a small always-on core: sub-agent delegation, the generic
workspace tools, and a single `search_tools` meta-tool. All heavy/optional
leaf tools (admin, slides, SPARQL recommendation, MCP, …) are **deferred**:
advertised by name/one-line description only, with their full schema loaded
into the active tool set when the model explicitly requests them.

This MUST be implemented in the **core agent runtime** (`naas_abi_core`) and
surfaced through the **`/agents/*` API** so that every consumer inherits it
without client-specific code:

- API (`/agents/{name}/completion`, `/stream-completion`) works first.
- The CLI (`abi chat`) and the Nexus client both call that same agent path and
  therefore get the behavior for free.

Because Abi's default model can be a local model (Ollama) that lacks any
server-side deferred-schema API, discovery is implemented **client-side**: when
the model calls `search_tools`, the runtime expands the bound tool set and
re-binds for subsequent turns. The active tool set is derived from the
conversation transcript (a pure function of message history), so it survives
reconstruction and compaction. This is model-agnostic and works identically for
local and cloud models.

### Principle 2 — Skills are metadata-first, bodies load on invoke

Skill discovery injects **metadata only** (name + short `when_to_use`
description) under a bounded budget. The full skill prompt body is injected
**only when the skill is invoked** (explicitly via `/<slug>` or when the model
selects it). Skill payload no longer scales with the catalog size.

### Principle 3 — Abi is a coordinator; leaf tools belong to sub-agents

The orchestrator's job is routing. Concrete leaf tools (admin, slides, …)
should live on the sub-agents that own those domains; Abi delegates to them.
Sub-agents run with role-scoped tool subsets. (`CoordinatorAgent` already
encodes the strict-routing variant to build on.)

### Principle 4 — Deterministic answers for capability/meta questions

Capability and "what can you do" questions are answered from the advertised
metadata catalog deterministically, without making the model enumerate every
tool schema. (`"What can you do?"` is Abi's own first suggestion, so it must be
correct and instant.)

### Principle 5 — Protect the prompt cache; bound result growth

Volatile catalogs (available agents, deferred tool names, skill listings) are
delivered as incremental additions rather than by rewriting the whole system
prompt every turn, so the stable prompt prefix stays cacheable. Large tool
results are compacted/offloaded so working context does not grow unbounded in
long sessions.

### Model tiering

Progressive disclosure is mandatory for small/local/CPU models (where prompt
size dominates latency and large tool sets hurt routing). Capable cloud models
may opt into the full surface where quality allows.

## Consequences

- **Positive:** far smaller per-turn prompts and lower latency on local models;
  better routing (fewer simultaneous options); skill payload decoupled from
  catalog size; one implementation in core benefits API, CLI, and Nexus alike.
- **Cost / risk:** the runtime must support per-turn tool (re)binding driven by
  transcript state — a generalization of the existing per-request model-variant
  swap used for workspace-tool gating. Discovery quality must be tuned (poor
  discovery = a capability the model never finds). A `search_tools` round-trip
  adds one extra model hop when a deferred tool is first needed.
- **Supersedes:** the `ABI_THIN_ROUTER` experiment (blunt removal). The
  `num_predict` generation cap is retained as an independent safety net.

## Implementation plan (incremental, API-first)

1. Core runtime: add a `search_tools` meta-tool and per-turn tool-set
   resolution from transcript state in `naas_abi_core/services/agent/`.
2. Mark `AbiAgent` leaf tools as deferred; keep delegation + workspace + the
   meta-tool always-on.
3. Add the deterministic capability answer for meta questions.
4. Verify end-to-end **via the API** (`/agents/Abi/completion`), then confirm
   the CLI (`abi chat`) and Nexus client inherit it unchanged.
5. Apply Principle 2 to the Nexus skills block (metadata-first listing +
   load-on-invoke).
6. Follow up with Principle 3 (relocate leaf tools onto sub-agents) and
   Principle 5 (prompt-cache-friendly deltas + result compaction).
