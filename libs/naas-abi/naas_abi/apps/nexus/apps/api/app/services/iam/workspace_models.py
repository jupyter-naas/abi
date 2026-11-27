"""The chat models a workspace uses: the Models section of its offer (ADR
``20261126_models_in_the_offer``).

IAM decides which models a person may use (``model_sets``: platform policies held by
the level groups, unscoped), so no workspace's bound narrows them. The offer "<W>
access" names the models W uses (``OfferModels``; ``*`` or no section: every model) and
the one an agent whose model it does not offer switches to (``OfferDefaultModel``).
Nexus keeps a turn to them where it knows the workspace the turn runs in, the
conversation's (never the agent's own):

* the chat's model picker and an agent's announced model (``/agents`` in W);
* a turn's model, picked or not, before it is announced and stored (chat streaming and
  completion), the in-process agent and each of its sub-agents switched, and the loan
  of an agent's own models (``provider_runtime``) narrowed to what W offers;
* a remote module's turn: the engine asks ``substitute`` (registered on the model
  registry, core ``ModelRegistryService.register_model_substitute``) with the request's
  container when the module resolves its model;
* an agent with its own provider (workspace keys, Ollama, inference servers): refused
  when its model is not offered, there being no model of that provider to switch to.

Embeddings are not chat models: search and a chat's files keep theirs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

EVERY_MODEL = "*"
# How long the engine waits for a workspace's models before it refuses the turn.
_READ_SECONDS = 10.0


class ModelNotOfferedError(PermissionDeniedError):
    """A model the workspace does not offer, and no default model to switch to (or a
    provider of its own, which cannot switch)."""

    def __init__(self, model_id: str | None) -> None:
        self.model_id = model_id
        super().__init__(
            f"The model {model_id or '(none)'} is not offered in this workspace: "
            "ask its administrators to add it to the workspace's models."
        )


@dataclass(frozen=True)
class WorkspaceModels:
    """``offered``: the models a workspace uses, None for every one; ``default``: the
    one a model it does not offer is switched to."""

    offered: frozenset[str] | None = None
    default: str | None = None

    @property
    def restricted(self) -> bool:
        return self.offered is not None

    def allows(self, model_id: str | None) -> bool:
        return self.offered is None or (model_id is not None and model_id in self.offered)

    def model_for(self, model_id: str | None) -> str | None:
        """The model a turn asking for ``model_id`` uses: itself when offered (or the
        workspace uses every model), else the default; refused without one."""
        if self.allows(model_id):
            return model_id
        if self.default is None:
            raise ModelNotOfferedError(model_id)
        return self.default

    def require(self, model_id: str | None) -> None:
        """Refuse a model that is not offered (a provider of its own cannot switch)."""
        if not self.allows(model_id):
            raise ModelNotOfferedError(model_id)

    def narrowed(self, model_ids: Iterable[str]) -> list[str]:
        """``model_ids`` the workspace uses, in order."""
        return [m for m in model_ids if self.allows(m)]


UNRESTRICTED = WorkspaceModels()


def models_of(offer: Any) -> WorkspaceModels:
    """What an offer (``workspace_offer.Offer``, or None: no allow-list yet) says of its
    models: every one when it names none, or names ``*``."""
    if offer is None:
        return UNRESTRICTED
    models = frozenset(getattr(offer, "models", ()) or ())
    default = getattr(offer, "default_model", None)
    if not models or EVERY_MODEL in models:
        return WorkspaceModels(None, default)
    return WorkspaceModels(models, default)


def validated(models: Iterable[str], default: str | None) -> tuple[frozenset[str], str | None]:
    """A setting of the Models section, as the offer holds it: ``*`` alone for every
    model (a default optional); else a list holding its default."""
    found = frozenset(str(m).strip() for m in models if str(m).strip())
    default = (default or "").strip() or None
    if EVERY_MODEL in found:
        return frozenset({EVERY_MODEL}), default
    if not found:
        raise ValueError("Name the models the workspace uses, or every model (*).")
    if default is None or default not in found:
        raise ValueError("A workspace limited to some models needs one of them as its default.")
    return found, default


# -- reading them --------------------------------------------------------------------------


async def models_in_container(container: str | None) -> WorkspaceModels:
    """The models of the workspace ``container`` (its offer, ``Authz.offer_of``'s cache);
    every model outside a workspace, or for one whose policy is no allow-list yet."""
    if not container:
        return UNRESTRICTED
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import is_workspace_container
    from naas_abi.apps.nexus.apps.api.app.services.iam.runtime import IAMUnavailableError

    if not is_workspace_container(container):
        return UNRESTRICTED
    try:
        return models_of(await AUTHZ.offer_of(container))
    except IAMUnavailableError:
        return UNRESTRICTED


async def models_in_workspace(workspace_id: str | None) -> WorkspaceModels:
    """The models of the workspace ``workspace_id`` (looked up)."""
    if not workspace_id:
        return UNRESTRICTED
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
    from naas_abi.apps.nexus.apps.api.app.services.iam.runtime import IAMUnavailableError

    try:
        container = await AUTHZ.container_of(workspace_id)
    except IAMUnavailableError:
        # No IAM: no offer to keep a turn to (and Nexus authorizes nothing anyway).
        return UNRESTRICTED
    return await models_in_container(container)


# The models of the turn running: set where the chat knows the conversation's workspace.
_TURN: ContextVar[WorkspaceModels | None] = ContextVar("nexus_turn_models", default=None)


@contextmanager
def for_turn(models: WorkspaceModels) -> Iterator[WorkspaceModels]:
    token = _TURN.set(models)
    try:
        yield models
    finally:
        _TURN.reset(token)


async def models_for_turn() -> WorkspaceModels:
    """The models of the turn running: those its chat gave it (``for_turn``), else its
    call context's container's."""
    given = _TURN.get()
    if given is not None:
        return given
    from naas_abi_core.engine.call_context import current_call_context

    return await models_in_container(current_call_context().container)


def set_for_turn(models: WorkspaceModels) -> None:
    """The models of the request's turn, for the rest of the request (as the chat binds
    the turn's container: a streamed answer runs after the handler returns)."""
    _TURN.set(models)


def turn_llm_model(
    models: WorkspaceModels,
    *,
    provider_type: str,
    endpoint: str | None,
    provider_model: str | None,
    llm_model: str | None,
    agent_models: Callable[[], set[str]] | None = None,
) -> str | None:
    """The model a turn runs on in a workspace using ``models`` (``llm_model``: the
    picked or routed one, None for the agent's own), by the provider of its agent:

    * an in-process agent: a picked model not offered is switched to the default; none
      picked, the default when the agent's own models (``agent_models``) are not all
      offered (its sub-agents are switched as the turn runs, ``provider_runtime``);
    * a remote module's agent: unchanged, the engine switches what it resolves
      (``substitute``);
    * an ABI server's agent, or an agent with a provider of its own (workspace keys,
      Ollama, inference servers): there is no model of theirs to switch to, so one not
      offered is refused (``ModelNotOfferedError``).
    """
    if not models.restricted:
        return llm_model
    if provider_type == "remote":
        return llm_model
    if provider_type == "abi":
        if not (endpoint or "").startswith("inprocess://"):
            raise ModelNotOfferedError(llm_model or provider_model)
        if llm_model:
            return models.model_for(llm_model)
        own = agent_models() if agent_models is not None else set()
        if not own or not all(models.allows(m) for m in own):
            return models.model_for(None)
        return None
    models.require(llm_model or provider_model)
    return llm_model


# -- the engine's substitute (a remote module's turn) -----------------------------------------


def substitute_with(read: Callable[[str], WorkspaceModels]) -> Callable[[str | None, str], str]:
    """The substitute the model registry asks (core ``register_model_substitute``):
    ``(container, canonical id) -> canonical id`` with ``read`` giving a container's
    models. Refuses (``ModelNotOfferedError``) when the model is not offered and there is
    no default."""

    def substitute(container: str | None, canonical_id: str) -> str:
        if not container:
            return canonical_id
        return read(container).model_for(canonical_id) or canonical_id

    return substitute


def blocking_reader(
    read: Callable[[str], Awaitable[WorkspaceModels]], loop: asyncio.AbstractEventLoop
) -> Callable[[str], WorkspaceModels]:
    """``read`` run on ``loop`` (Nexus's, where its database sessions live) from the
    engine's worker thread, which waits. Called on that loop's own thread it cannot
    wait: the cached offer, else every model (logged)."""

    def blocking(container: str) -> WorkspaceModels:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

            cached = AUTHZ._offers.get(container)
            if cached is None:
                logger.warning(f"Models of {container}: not read on the loop's own thread")
                return UNRESTRICTED
            return models_of(cached[0])
        return asyncio.run_coroutine_threadsafe(read(container), loop).result(_READ_SECONDS)

    return blocking


def install_substitute(registry: Any, loop: asyncio.AbstractEventLoop) -> None:
    """Register the workspaces' models with the engine's model registry, read on
    ``loop``. At start, once."""
    registry.register_model_substitute(substitute_with(blocking_reader(models_in_container, loop)))


__all__ = [
    "EVERY_MODEL",
    "UNRESTRICTED",
    "ModelNotOfferedError",
    "WorkspaceModels",
    "blocking_reader",
    "for_turn",
    "install_substitute",
    "set_for_turn",
    "turn_llm_model",
    "models_for_turn",
    "models_in_container",
    "models_in_workspace",
    "models_of",
    "substitute_with",
    "validated",
]
