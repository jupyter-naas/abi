"""Request-scoped identity stamped on every published event.

Set these at the request boundary (an HTTP middleware, a queue consumer, a
CLI entrypoint). ``EventService.publish()`` copies them onto any ``LogProcess``
that did not set its own, so services emitting events never plumb identity.

``asyncio`` tasks inherit ContextVars; raw threads need
``contextvars.copy_context()``.
"""

from __future__ import annotations

from contextvars import ContextVar

# Id of the user the work is done for (e.g. the Nexus users.id).
event_actor_user_id: ContextVar[str | None] = ContextVar("agent_user_id", default=None)
# Id of the workspace/tenant the work happens in (e.g. the Nexus workspaces.id).
event_actor_workspace_id: ContextVar[str | None] = ContextVar(
    "agent_workspace_id", default=None
)
# How the work was triggered: "api", "configuration", "system", ...
event_triggered_via: ContextVar[str | None] = ContextVar(
    "event_triggered_via", default=None
)
