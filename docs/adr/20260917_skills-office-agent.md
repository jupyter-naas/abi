# Skills are created by a Skills office agent, not drafted into the chat

## Status

Proposed (implemented on `nexus-build-app`, awaiting review)

## Date

2026-09-17

## Context

A skill is a reusable prompt a workspace member invokes with `/<slug>`
(`services/skills/`, `Settings > Skills`). Until now the only conversational
way to make one was a prompt fragment the chat service injected into **every**
turn of **every** agent (`_CREATE_SKILL_INSTRUCTIONS` in
`services/chat/service.py`): on a message starting with `/create-skill`, the
model was told to propose a name, slug, description and prompt, and to print
them as a fenced ` ```skill ` block holding a JSON object. The web rendered
that block as `SkillDraftCard` (`components/chat/chat-interface.tsx`), a card
with a scope picker and a Save button that called `POST /api/skills`.

Three problems came out of it.

1. **The instructions were resident in every conversation.** They shipped with
   the skills catalog on each turn, for agents that had nothing to do with
   skills, and they fired on their own: an assistant answering "ok" in an
   unrelated conversation volunteered the whole `/create-skill` protocol,
   fenced block included. That is the report that prompted this ADR.
2. **The contract lived in the transport.** A model had to emit valid JSON
   inside a code fence, streamed token by token; the card carried the logic for
   partial JSON, for drafts truncated by `max_tokens`, and for remapping a
   reserved slug — the same remapping the service already does
   (`suggest_skill_slug`). Two implementations of one rule, one of them in a
   React component.
3. **It only worked inside Nexus.** The OpenAI-compatible gateway deliberately
   withholds the block, because it points at a UI an editor client does not
   have (`openai_gateway__primary_adapter__FastAPI.py`). Any client without
   the card got instructions to produce a payload nobody would ever save.

Every other Nexus feature already answers this shape of request with an office
agent: one agent per section, on the roster, reached by Abi through handoff
intents, acting through tools that call the same service as the HTTP adapter
(`agents/feature/registry.py`, ADR 20260916). Skills was the exception — it had
no owner agent, only prompt text, and `AgentCatalogAgent` covered the *page*
read-only while the creation path lived in the orchestrator's system prompt.

## Decision

Skills becomes a feature with an office agent, like Apps.

- **`naas_abi SkillsAgent`** (`agents/SkillsAgent.py`) owns the `skills`
  feature key in `FEATURE_AGENTS` and in the web mirror
  (`lib/feature-office-agents.ts`). It binds the right pane in
  `Settings > Skills` and Abi hands skill requests to it through
  `handoff_intents` (English and French), exactly as for Apps.
- **`agents/tools/skills_tools.py`** gives it `list_workspace_skills`,
  `get_workspace_skill`, `create_skill`, `update_skill` and `delete_skill`.
  They call `SkillService` in-process under the caller's identity, so scope
  validation, reserved slugs, and "only the creator may change a user-scoped
  skill" stay in one place. `create_skill` **saves**; there is no draft.
- **`AgentCatalogAgent` keeps `agents` only.** Its skills tools moved out, and
  its prompt points at the Skills agent. One feature, one owner.
- **The chat preamble no longer teaches a format.** `_SKILLS_HANDOFF_NOTE`
  replaces `_CREATE_SKILL_INSTRUCTIONS`: it says creating, editing and deleting
  skills belongs to the Skills agent, and that a skill is never to be drafted
  as a payload for the user to save by hand. The catalog block itself is
  unchanged — enabled skills, with their prompts, still ride on every turn, so
  an agent applies a matching skill without being named.
- **`SkillDraftCard` and the ` ```skill ` branch are deleted.** `/create-skill`
  stays as a builtin slash command: it reaches the model as plain text and is
  handed off. After a write tool returns, the web refetches the catalog
  (`isSkillsWriteTool` / `noteSkillsToolResult` in `stores/skills.ts`, mirroring
  `SKILL_WRITE_TOOLS`), so `/<slug>` resolves in the very next message.

## Consequences

- A skill is saved by the agent that wrote it, in the conversation where the
  task actually happened — the recurring task is right there in context, which
  is what made the draft-and-paste round trip redundant in the first place.
- No agent volunteers a skill protocol any more. The resident text is two
  sentences of routing, not a format specification.
- Clients without the Nexus UI (the OpenAI gateway, the CLI) degrade to a
  sentence that names where skills live, instead of instructions for a card
  they cannot render.
- The slug and scope rules have exactly one implementation, the service's. The
  web keeps `normalizeSkillSlug` only where a human types a slug
  (`Settings > Skills`).
- A deployment that pins its workspace roster in `config.yaml` must add
  `"naas_abi SkillsAgent"` to `agents:`; the default seed in `naas_abi/__init__.py`
  already lists it. Without it the pane falls back to the workspace default and
  Abi has nobody to hand a skill request to.
- Delete is now reachable from the chat. It is guarded by the same creator rule
  as the API, and the prompt forbids deleting a skill the user did not name.
