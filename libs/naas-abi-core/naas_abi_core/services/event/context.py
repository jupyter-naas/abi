"""Request-scoped identity stamped on every published event.

The actor, workspace and trigger of an event come from the call's
``CallContext`` (``naas_abi_core.engine.call_context``), the one source of who
is calling. ``EventService.publish()`` copies them onto any ``LogProcess`` that
did not set its own, so services emitting events never plumb identity.

The three names below are views of that context, kept for the code that reads
or sets them like ContextVars:

* ``event_actor_user_id``: the call's user (``CallContext.user``); setting it
  sets ``on_behalf_of``;
* ``event_actor_workspace_id``: ``CallContext.workspace_id``;
* ``event_triggered_via``: ``CallContext.triggered_via``.

``set`` returns a token that ``reset`` takes back, like a ContextVar's. A
reset restores that one field, so tokens can be reset in any order.

``asyncio`` tasks inherit the context; raw threads need
``contextvars.copy_context()``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
    set_call_context,
    user,
)


@dataclass(frozen=True)
class FieldToken:
    """What ``CallContextField.reset`` puts back: the field's previous value."""

    field: CallContextField
    previous: Any


class CallContextField:
    """One field of the current ``CallContext``, read and set like a ContextVar.

    Two differences from a ContextVar:

    * ``reset`` writes the field's saved value into the context current at
      reset time; it does not bring back the whole earlier context. Other
      fields changed in between keep their new values.
    * ``event_actor_user_id`` reads the call's user but writes
      ``on_behalf_of``. When the actor is itself a user, ``set(None)`` clears
      ``on_behalf_of`` only, and ``get()`` still returns the actor.
    """

    def __init__(
        self,
        attribute: str,
        read: Callable[[CallContext], str | None],
        convert: Callable[[str | None], Any],
    ) -> None:
        self.attribute = attribute
        self._read = read
        self._convert = convert

    def get(self, default: str | None = None) -> str | None:
        value = self._read(current_call_context())
        return default if value is None else value

    def set(self, value: str | None) -> FieldToken:
        current = current_call_context()
        token = FieldToken(self, getattr(current, self.attribute))
        set_call_context(replace(current, **{self.attribute: self._convert(value)}))
        return token

    def reset(self, token: FieldToken) -> None:
        if token.field is not self:
            raise ValueError(f"{token!r} was not created by {self!r}")
        set_call_context(
            replace(current_call_context(), **{self.attribute: token.previous})
        )

    def __repr__(self) -> str:
        return f"<CallContextField {self.attribute}>"


def _user_id(context: CallContext) -> str | None:
    served = context.user
    return served.id if served is not None else None


# Id of the user the work is done for (e.g. the Nexus users.id).
event_actor_user_id = CallContextField(
    "on_behalf_of", _user_id, lambda value: user(value) if value else None
)
# Id of the workspace/tenant the work happens in (e.g. the Nexus workspaces.id).
event_actor_workspace_id = CallContextField(
    "workspace_id", lambda context: context.workspace_id, lambda value: value or None
)
# How the work was triggered: "api", "configuration", "system", ...
event_triggered_via = CallContextField(
    "triggered_via", lambda context: context.triggered_via, lambda value: value or None
)
