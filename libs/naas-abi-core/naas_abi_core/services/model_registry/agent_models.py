"""An agent's own model is decided by the agent's scope, not the caller's model set.

A model set ("Models · <set>", a policy on ``model/<canonical id>``) says which
models a person may chat with directly. A module agent comes with its models: the
person who may use the agent may use them through it, whatever their set. The
caller that runs an agent's turn in process (Nexus, after it authorized the
agent's module scope) names, for the turn, each model the agent owns and the
agent scopes that own it::

    with agent_models("module:UseAgent", {"large-model": [agent_scope_name]}):
        agent.invoke(...)

Inside the block, resolving or chatting with (``Resolve``, ``Chat``,
``ChatStream``) a model it names is authorized as ``action`` on one of its
scopes, for the caller, instead of the model's own action: the agent's scope
decides. Any other model, and ``Embed``, stay the caller's own. A context
variable, so it follows the turn into its threads and tasks as the call context
does; set in process only (a remote caller holds nothing but its token).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

# The model actions an agent's scope decides for the models it owns.
AGENT_ACTIONS = frozenset({"Resolve", "Chat", "ChatStream"})


@dataclass(frozen=True)
class AgentModels:
    """``action`` on any of ``owners[canonical id]`` allows that model."""

    action: str
    owners: Mapping[str, tuple[str, ...]]


_CURRENT: ContextVar[AgentModels | None] = ContextVar("abi_agent_models", default=None)


def current_agent_models() -> AgentModels | None:
    return _CURRENT.get()


@contextmanager
def agent_models(
    action: str, owners: Mapping[str, Iterable[str]]
) -> Iterator[AgentModels]:
    """Lend, for the block, each model of ``owners`` to whoever may perform
    ``action`` on one of the agent scopes that own it."""
    lent = AgentModels(
        action,
        {
            str(canonical_id): tuple(dict.fromkeys(str(s) for s in scopes))
            for canonical_id, scopes in owners.items()
            if scopes
        },
    )
    token = _CURRENT.set(lent)
    try:
        yield lent
    finally:
        try:
            _CURRENT.reset(token)
        except ValueError:
            # Closed from another context (an async generator finalized elsewhere):
            # the context it was lent in is that block's alone, and ends with it.
            pass


def gated_model_ids(model: Any) -> set[str]:
    """The canonical ids of the registry's gates on ``model`` (a LangChain chat
    model the registry handed out): which models an agent was built with."""
    from naas_abi_core.services.model_registry.ModelRegistryService import _ChatGate

    base = getattr(model, "model", model) if not hasattr(model, "callbacks") else model
    callbacks = getattr(base, "callbacks", None)
    handlers = (
        callbacks
        if isinstance(callbacks, list)
        else getattr(callbacks, "handlers", None) or []
        if callbacks is not None
        else []
    )
    return {h.canonical_id for h in handlers if isinstance(h, _ChatGate)}


__all__ = [
    "AGENT_ACTIONS",
    "AgentModels",
    "agent_models",
    "current_agent_models",
    "gated_model_ids",
]
