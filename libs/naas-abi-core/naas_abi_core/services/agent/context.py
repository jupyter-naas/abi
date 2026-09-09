"""Request-scoped identity for agent invocations.

These ContextVars let any code running inside an agent call (or an awaited
coroutine in the same task) attach who/where/what to the events it emits, with
no constructor plumbing. They are typically set at the request boundary —
your FastAPI auth dependency, queue consumer, or CLI entrypoint — and read by
the agent's notification methods when publishing to the EventService.

``chat_id`` defaults to ``AgentSharedState.thread_id`` when unset, so the
generic ``Agent.as_api`` endpoints already produce chat-tagged events without
any extra wiring. ``user_id`` and ``workspace_id`` are auth-specific and must
be populated by the integrator. Example::

    @router.middleware("http")
    async def attach_identity(request, call_next):
        agent_user_id.set(request.state.user.id)
        agent_workspace_id.set(request.state.workspace.id)
        return await call_next(request)

Propagating across raw thread spawns requires ``contextvars.copy_context()``;
``asyncio`` tasks inherit automatically. ``Agent.stream_invoke`` already
handles the thread copy.
"""

from __future__ import annotations

from contextvars import ContextVar

agent_user_id: ContextVar[str | None] = ContextVar("agent_user_id", default=None)
# Display identity for the acting user, alongside agent_user_id. Populated at
# the same request boundary so tools that commit on the user's behalf (e.g.
# Slides' upsert_file/upsert_files) can attribute the commit's git author to
# the real connected user instead of the service account, without a second
# lookup back to the auth store.
agent_user_name: ContextVar[str | None] = ContextVar("agent_user_name", default=None)
agent_user_email: ContextVar[str | None] = ContextVar("agent_user_email", default=None)
agent_chat_id: ContextVar[str | None] = ContextVar("agent_chat_id", default=None)
agent_workspace_id: ContextVar[str | None] = ContextVar(
    "agent_workspace_id", default=None
)

# Coding-workspace bridge: base URL + bearer secret of the exec sidecar running
# inside the caller's Coder coding workspace. Set at the request boundary (the
# OpenAI shim, from the per-workspace token claims) and read by the workspace
# filesystem/terminal tools so a server-side agent acts on the right user's
# workspace. NOTE: distinct from ``agent_workspace_id`` (the Nexus tenant
# workspace) — this targets the Coder container ``coder-<user>-<ws>``.
coder_workspace_base: ContextVar[str | None] = ContextVar(
    "coder_workspace_base", default=None
)
coder_workspace_secret: ContextVar[str | None] = ContextVar(
    "coder_workspace_secret", default=None
)

# Open Slides deck in the Nexus UI (pane). Set at the chat stream boundary from
# client context so Abi tools default to this slug and never ask "which deck?".
slides_active_slug: ContextVar[str | None] = ContextVar(
    "slides_active_slug", default=None
)
slides_active_title: ContextVar[str | None] = ContextVar(
    "slides_active_title", default=None
)
slides_active_mode: ContextVar[str | None] = ContextVar(
    "slides_active_mode", default=None
)

# Open Code repo context in the Nexus UI. Set at the chat stream boundary so Abi
# tools default to this repo/branch sandbox (Slides-parity for Code).
coding_active_repo: ContextVar[str | None] = ContextVar(
    "coding_active_repo", default=None
)
coding_active_branch: ContextVar[str | None] = ContextVar(
    "coding_active_branch", default=None
)
# Managed coding harness (OpenCode serve) bound to the open sandbox checkout.
coding_harness_base: ContextVar[str | None] = ContextVar(
    "coding_harness_base", default=None
)

# Research gate for Slides briefs. Set at the chat stream boundary when the
# open deck needs web_search before HTML writes. web_search appends queries;
# write tools refuse until at least one query is recorded.
slides_research_required: ContextVar[bool] = ContextVar(
    "slides_research_required", default=False
)
slides_research_queries: ContextVar[list[str] | None] = ContextVar(
    "slides_research_queries", default=None
)

# The user's message for this turn, kept so a deck can be named after the topic
# it asks about. Set at the chat stream boundary alongside the research gate.
slides_brief: ContextVar[str | None] = ContextVar("slides_brief", default=None)

# The user asked for a deck from a surface with no deck open (main chat). Set at
# the chat stream boundary so the agent budgets a slides-sized run (create,
# research, then one batched write) instead of a normal chat turn.
slides_creation_intent: ContextVar[bool] = ContextVar(
    "slides_creation_intent", default=False
)

# Successful deck writes this turn (section indexes, "full deck", replace notes).
# The step-limit message uses this so the user hears what finished vs what did not.
slides_writes_completed: ContextVar[list[str] | None] = ContextVar(
    "slides_writes_completed", default=None
)

# Per-turn read budget. Qwen ignores "list once, do not read every section"
# and dumps every slide HTML into the checkpointer. The tools refuse the
# second list and the fourth unique section read.
slides_list_calls: ContextVar[int] = ContextVar("slides_list_calls", default=0)
slides_section_read_indexes: ContextVar[list[int] | None] = ContextVar(
    "slides_section_read_indexes", default=None
)

# LangGraph counts every node visit (IntentAgent setup plus call_model +
# call_tools per hop). Default LangGraph is 25. 80 was too low for an 8-32
# slide industry rewrite that listed, read, and wrote one section at a time.
# 160 is ~70 tool hops after IntentAgent overhead: enough for search + one
# batched write, and a thin margin if the model still writes a few sections.
# A 32-slide per-section rewrite can still need a second turn.
SLIDES_RECURSION_LIMIT = 160


def slides_turn_active() -> bool:
    """True when this turn edits an open deck or creates a new one."""
    if (slides_active_slug.get() or "").strip():
        return True
    return bool(slides_creation_intent.get())


def note_slides_write(label: str) -> None:
    """Record a successful deck write so a step-limit error can name it."""
    text = (label or "").strip()
    if not text:
        return
    bucket = slides_writes_completed.get()
    if bucket is None:
        slides_writes_completed.set([text])
        return
    bucket.append(text)


def slides_step_limit_message() -> str:
    """User-facing cap text: what finished vs what did not."""
    writes = [item for item in (slides_writes_completed.get() or []) if item]
    queries = slides_research_queries.get() or []
    finished: list[str] = []
    if queries:
        finished.append(
            f"{len(queries)} web search{'es' if len(queries) != 1 else ''}"
        )
    if writes:
        finished.append("wrote " + ", ".join(writes))
    done = (
        "Finished: " + "; ".join(finished) + "."
        if finished
        else "Finished: no searches and no slides written."
    )
    leftover = (
        "The remaining slides were not written."
        if writes
        else "The deck was not written."
    )
    return (
        f"The agent hit its {SLIDES_RECURSION_LIMIT}-step limit before finishing. "
        f"{done} {leftover} "
        "Open the deck and ask it to continue from the next unwritten slide."
    )
