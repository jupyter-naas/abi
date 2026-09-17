# Abi is always enabled, and naas_abi agents are packed in the chat roster

## Status

Proposed (implemented on `nexus-build-app`, awaiting review)

## Date

2026-09-17

## Context

Two problems surfaced once the naas_abi office agents were put on the
workspace roster (see
[20260916_office-agent-visibility-by-role.md](20260916_office-agent-visibility-by-role.md)).

**1. The orchestrator could be switched off.** `POST /api/agents/sync`
aligns `agent_configs.enabled` to the workspace roster — the `agents:` seed
when present, otherwise the engine default alone
(`_reconcile_workspace_agents`). Abi is not special-cased anywhere in that
path, so a workspace whose seed does not name `naas_abi AbiAgent` ends up
with `enabled = false` on the one agent every other agent hands off to. The
`dcg-pilot` and `apl-test` workspaces were in exactly that state: their seed
lists Axi as default plus six office agents, and Abi was off.

This is not merely cosmetic. `pick_workspace_chat_agent_id` and
`pickWorkspaceDefaultAgent` both fall back to Abi when a workspace has no
usable default, and both require `enabled`. A disabled Abi removes the
platform's last-resort orchestrator and leaves the fallback to "first
enabled agent", which is whatever sorts first.

**2. The chat roster filled up with agents nobody chats with.** The sidebar
Chat section lists enabled agents, default first, and packs the rest behind
"Show N more" at a preview of five. On `dcg-pilot` that preview read: Axi
Agent, Agent Catalog, Apps, Counter-UAS Report, Files — four of the five
occupied by office agents that are reached from their own section pane and
bound automatically there. Osint and the report agents, the ones a user
actually opens a conversation with, were pushed behind the fold.

## Decision

1. **Abi joins every roster, unconditionally.** `_roster_alignment` adds the
   naas_abi `AbiAgent` registry key to the roster that sync aligns `enabled`
   against, whatever the workspace seeded. Workspaces do not need to list it,
   and a workspace that omits it no longer disables it.

2. **Abi is added *after* the alignment decision, never as its trigger.**
   Sync only rewrites `enabled` when the roster is non-empty or the seed is
   explicitly empty — the guard that stops a workspace absent from the loaded
   config from having every row disabled. Adding Abi before that test would
   turn "no seed, no resolvable default" into `roster = {Abi}` and disable
   everything else. `_roster_alignment` returns the roster and the alignment
   flag together so the ordering is one function's contract and is unit
   tested directly.

3. **The match is exact.** `_nexus_abi_class_name` accepts only
   `naas_abi.…/AbiAgent`, mirroring `_is_nexus_abi_agent`. An `AbiAgent`
   class from another module is never force-enabled in a workspace that did
   not ask for it.

4. **The sidebar Chat section packs naas_abi agents behind "Show N more".**
   `partitionChatRosterAgents` splits the sorted roster in two: every agent
   whose class comes from `naas_abi.` goes to the packed half, everything
   else stays in the preview. Expanding appends the packed half after the
   preview half, so "Show less" never reorders the list.

5. **The workspace default is the one exception.** It is what "Auto" runs, so
   it stays at the top of the preview even when it is Abi. A workspace that
   defaults to Abi therefore sees Abi first and its office agents packed; a
   workspace that defaults to Axi sees no naas_abi agent in the preview at
   all.

6. **Packed, not hidden.** The office agents remain selectable — this is a
   ranking rule, not an access rule. Access stays with the role filter from
   the 2026-09-16 ADR, which runs server-side on `GET /api/agents` and in the
   agent tools.

## Consequences

- Abi appears in every workspace's agent list after the next sync, including
  workspaces that had deliberately left it out of `agents:`. That is the
  intent — it is the orchestrator, not an optional feature agent — but it is
  a visible change for those workspaces.
- Abi can still be toggled off by hand in Settings → Agents; the next
  `POST /api/agents/sync` turns it back on. Making the toggle refuse would
  need a guard in `update_agent`, which the workspace default does not have
  either. Left consistent with the default's behaviour rather than special-
  casing one row in two places.
- `isNaasAbiAgent` matches the whole naas_abi family by module prefix, not a
  list of class names, so an office agent added later is packed without
  touching this code. The cost is that any future naas_abi agent genuinely
  meant for the chat roster would also be packed and would need an explicit
  exception.
- The preview can now be shorter than five rows when a workspace's roster is
  mostly naas_abi agents. That is the point, but it means `AGENTS_PREVIEW_COUNT`
  is an upper bound on the preview, not the number of rows shown.
- The role filter and this rule compose: a role that cannot open Ontology
  never receives the Ontology agent from the API at all, so it is neither
  previewed nor packed.
