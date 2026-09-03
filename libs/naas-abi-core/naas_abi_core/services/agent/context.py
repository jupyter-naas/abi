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
