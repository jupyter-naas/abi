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
