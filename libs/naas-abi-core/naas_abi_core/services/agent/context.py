"""Request-scoped identity for agent invocations.

These ContextVars let any code running inside an agent call (or an awaited
coroutine in the same task) attach who/where/what to the events it emits, with
no constructor plumbing. They are typically set at the request boundary —
your FastAPI auth dependency, queue consumer, or CLI entrypoint — and read by
the agent's notification methods when publishing to the EventService.

``chat_id`` defaults to ``AgentSharedState.thread_id`` when unset, so the
generic ``Agent.as_api`` endpoints already produce chat-tagged events without
any extra wiring. ``user_id`` and ``container`` (the name of the container the
call is made in, ``CallContext.container``) are auth-specific and must be
populated by the integrator. Example::

    @router.middleware("http")
    async def attach_identity(request, call_next):
        agent_user_id.set(request.state.user.id)
        agent_container.set(request.state.workspace.container)
        return await call_next(request)

Propagating across raw thread spawns requires ``contextvars.copy_context()``;
``asyncio`` tasks inherit automatically. ``Agent.stream_invoke`` already
handles the thread copy.
"""

from __future__ import annotations

import weakref
from contextvars import ContextVar

from naas_abi_core.services.event.context import (
    CallContextField,
    event_actor_container,
    event_actor_user_id,
)

# The event service's views of the CallContext: identity set for an agent run
# is stamped on every event published during it (EventService.publish).
agent_user_id: CallContextField = event_actor_user_id
# Display identity for the acting user, alongside agent_user_id. Populated at
# the same request boundary so tools that commit on the user's behalf (e.g.
# Slides' upsert_file/upsert_files) can attribute the commit's git author to
# the real connected user instead of the service account, without a second
# lookup back to the auth store.
agent_user_name: ContextVar[str | None] = ContextVar("agent_user_name", default=None)
agent_user_email: ContextVar[str | None] = ContextVar("agent_user_email", default=None)
agent_chat_id: ContextVar[str | None] = ContextVar("agent_chat_id", default=None)
# The container the turn is made in (its name, ``CallContext.container``).
agent_container: CallContextField = event_actor_container
# Enabled agent registry keys (``module/Class``) for the current chat turn after
# workspace roster and per-caller feature gating. Abi uses this to attach only
# the office sub-agents the user may reach.
agent_workspace_enabled_class_names: ContextVar[frozenset[str] | None] = ContextVar(
    "agent_workspace_enabled_class_names", default=None
)
# The module scopes (``(type, module, name)``, IAM ``module_scopes``) of the
# workflows and pipelines the caller may run where the turn runs. An agent's tool
# that one of them exposes answers a refusal for any other (``tool_scope_refused``).
# None: the turn is not bound (a caller outside Nexus's routes).
agent_usable_module_scopes: ContextVar[frozenset[tuple[str, str, str]] | None] = (
    ContextVar("agent_usable_module_scopes", default=None)
)
# A tool's metadata key naming the object that exposed it (``Expose.as_tools``):
# a string, so tracing serializes it; ``exposer`` finds the object.
EXPOSED_BY = "abi_exposed_by"
_exposers: weakref.WeakValueDictionary[str, object] = weakref.WeakValueDictionary()
# The module scope of each module's workflow and pipeline classes, ``(type, module,
# name)``: an instance an agent builds itself is bounded like the module's own.
_scopes_by_class: dict[type, tuple[str, str, str]] = {}


def register_process_scope(cls: type, scope: tuple[str, str, str]) -> bool:
    """Record ``cls``'s module scope; False (kept as it was) when another module
    already declared the class under another scope."""
    known = _scopes_by_class.setdefault(cls, scope)
    return known == scope


def process_scopes() -> list[tuple[str, str, str]]:
    """Every registered workflow and pipeline scope."""
    return sorted(set(_scopes_by_class.values()))


def process_scope_of(owner: object) -> tuple[str, str, str] | None:
    """The module scope of a workflow or pipeline instance: its class's, or the
    nearest registered base class's (a subclass of a module's workflow)."""
    for cls in type(owner).__mro__:
        scope = _scopes_by_class.get(cls)
        if scope is not None:
            return scope
    return None


def remember_exposer(owner: object) -> str | None:
    """The key a tool of ``owner`` carries in its metadata; None for an object
    that cannot be referenced weakly."""
    key = f"{type(owner).__qualname__}:{id(owner)}"
    try:
        _exposers[key] = owner
    except TypeError:
        return None
    return key


def tool_scope_refused(tool: object) -> tuple[str, str, str] | None:
    """The module scope of a workflow or pipeline ``tool`` exposes, when the turn
    is bound and the caller may not run it there; else None."""
    usable = agent_usable_module_scopes.get()
    if usable is None:
        return None
    metadata = getattr(tool, "metadata", None) or {}
    key = metadata.get(EXPOSED_BY)
    owner = _exposers.get(key) if isinstance(key, str) else None
    scope = process_scope_of(owner) if owner is not None else None
    if scope is None or scope in usable:
        return None
    return scope


# Coding-workspace bridge: base URL + bearer secret of the exec sidecar running
# inside the caller's Coder coding workspace. Set at the request boundary (the
# OpenAI shim, from the per-workspace token claims) and read by the workspace
# filesystem/terminal tools so a server-side agent acts on the right user's
# workspace. NOTE: distinct from ``agent_container`` (the container of the
# call, e.g. a Nexus workspace) — this targets the Coder container
# ``coder-<user>-<ws>``.
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

# Open Documents file in the Nexus UI (pane). Set at the chat stream boundary from
# client context so Documents tools default to this slug.
documents_active_slug: ContextVar[str | None] = ContextVar(
    "documents_active_slug", default=None
)
documents_active_title: ContextVar[str | None] = ContextVar(
    "documents_active_title", default=None
)
documents_active_mode: ContextVar[str | None] = ContextVar(
    "documents_active_mode", default=None
)
documents_research_required: ContextVar[bool] = ContextVar(
    "documents_research_required", default=False
)
documents_research_queries: ContextVar[list[str] | None] = ContextVar(
    "documents_research_queries", default=None
)
documents_brief: ContextVar[str | None] = ContextVar("documents_brief", default=None)
documents_creation_intent: ContextVar[bool] = ContextVar(
    "documents_creation_intent", default=False
)
documents_writes_completed: ContextVar[list[str] | None] = ContextVar(
    "documents_writes_completed", default=None
)
documents_list_calls: ContextVar[int] = ContextVar("documents_list_calls", default=0)
documents_section_read_indexes: ContextVar[list[int] | None] = ContextVar(
    "documents_section_read_indexes", default=None
)
DOCUMENTS_RECURSION_LIMIT = 160


def documents_turn_active() -> bool:
    """True when this turn edits an open document or creates a new one."""
    if (documents_active_slug.get() or "").strip():
        return True
    return bool(documents_creation_intent.get())


def note_documents_write(label: str) -> None:
    """Record a successful document write so a step-limit error can name it."""
    text = (label or "").strip()
    if not text:
        return
    bucket = documents_writes_completed.get()
    if bucket is None:
        documents_writes_completed.set([text])
        return
    bucket.append(text)


def documents_step_limit_message() -> str:
    """User-facing cap text: what finished vs what did not."""
    writes = [item for item in (documents_writes_completed.get() or []) if item]
    queries = documents_research_queries.get() or []
    finished: list[str] = []
    if queries:
        finished.append(f"{len(queries)} web search{'es' if len(queries) != 1 else ''}")
    if writes:
        finished.append("wrote " + ", ".join(writes))
    done = (
        "Finished: " + "; ".join(finished) + "."
        if finished
        else "Finished: no searches and no document sections written."
    )
    leftover = (
        "The remaining sections were not written."
        if writes
        else "The document was not written."
    )
    return (
        f"The agent hit its {DOCUMENTS_RECURSION_LIMIT}-step limit before finishing. "
        f"{done} {leftover} "
        "Open the document and ask it to continue from the next unwritten section."
    )


# Open Sheets workbook in the Nexus UI (pane).
sheets_active_slug: ContextVar[str | None] = ContextVar(
    "sheets_active_slug", default=None
)
sheets_active_title: ContextVar[str | None] = ContextVar(
    "sheets_active_title", default=None
)
sheets_active_mode: ContextVar[str | None] = ContextVar(
    "sheets_active_mode", default=None
)
sheets_research_required: ContextVar[bool] = ContextVar(
    "sheets_research_required", default=False
)
sheets_research_queries: ContextVar[list[str] | None] = ContextVar(
    "sheets_research_queries", default=None
)
sheets_brief: ContextVar[str | None] = ContextVar("sheets_brief", default=None)
sheets_creation_intent: ContextVar[bool] = ContextVar(
    "sheets_creation_intent", default=False
)
sheets_writes_completed: ContextVar[list[str] | None] = ContextVar(
    "sheets_writes_completed", default=None
)
sheets_list_calls: ContextVar[int] = ContextVar("sheets_list_calls", default=0)
sheets_section_read_indexes: ContextVar[list[int] | None] = ContextVar(
    "sheets_section_read_indexes", default=None
)
SHEETS_RECURSION_LIMIT = 120


def sheets_turn_active() -> bool:
    if (sheets_active_slug.get() or "").strip():
        return True
    return bool(sheets_creation_intent.get())


def note_sheets_write(label: str) -> None:
    text = (label or "").strip()
    if not text:
        return
    bucket = sheets_writes_completed.get()
    if bucket is None:
        sheets_writes_completed.set([text])
        return
    bucket.append(text)


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
        finished.append(f"{len(queries)} web search{'es' if len(queries) != 1 else ''}")
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
