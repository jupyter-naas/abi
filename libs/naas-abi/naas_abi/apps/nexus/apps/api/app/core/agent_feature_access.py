"""Which of a workspace's agents a caller may use.

Office agents follow their Nexus feature, per caller, at list and chat time: a
member without Ontology does not see OntologyAgent in the picker, and Abi drops
that sub-agent for their turn. Non-office agents (client modules, Abi itself)
are not feature-gated.

Every agent of a module, naas_abi's own included, also needs its module
scope (``module:UseAgent`` in the workspace, ``services/agents/scopes.py``), and
an agent the workspace built needs ``nexus:UseAgent`` on it:
``caller_usable_agents`` is the roster a caller's turn may run and reach as
sub-agents, and the agents listing shows the same. There is no on/off state of a
workspace's own: IAM decides alone.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeVar

from naas_abi.agents.feature.registry import spec_for_class_name
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope

AgentT = TypeVar("AgentT")


def feature_keys_of(agents: Iterable[object]) -> set[str]:
    """The feature keys the office agents among ``agents`` depend on."""
    keys: set[str] = set()
    for agent in agents:
        spec = spec_for_class_name(getattr(agent, "class_name", None))
        if spec is not None:
            keys.update(spec.feature_keys)
    return keys


async def caller_feature_flags(
    user: object, workspace_id: str, keys: Iterable[str]
) -> dict[str, bool]:
    """Whether the caller may use each of ``keys`` in this workspace, from IAM.

    IAM's ``UseFeature`` is what the workspace listing sends the frontend (the
    policies granting a feature), so the agents a user is offered match the
    sections they can open.
    """
    return {
        key: await authz.allowed("UseFeature", user=user, workspace=workspace_id, id=key)
        for key in sorted(set(keys))
    }


async def caller_usable_agents(
    agents: Iterable[AgentT], user: object, workspace_id: str, flags: Mapping[str, bool]
) -> list[AgentT]:
    """The roster entries the caller may use in this workspace: the office agents
    of features it holds, the module agents it holds a scope for, and the agents
    the workspace built that it may use (``nexus:UseAgent``: one turned off before
    is denied there)."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import scope_resolver

    scope_of: Callable[[Any], ModuleScope | None] = scope_resolver()
    usable = await authz.filter_scopes(
        filter_feature_agents(agents, flags),
        user=user,
        workspace=workspace_id,
        scope_of=scope_of,
    )
    built = [getattr(agent, "id", "") for agent in usable if scope_of(agent) is None]
    if not built:
        return usable
    may = await authz.allowed_ids("UseAgent", user=user, workspace=workspace_id, ids=built)
    return [
        agent
        for agent in usable
        if scope_of(agent) is not None or getattr(agent, "id", "") in may
    ]


def caller_usable_class_names(
    agents: Iterable[AgentT],
    flags: Mapping[str, bool],
) -> frozenset[str]:
    """The registry keys of ``agents`` (those the caller may use) within the
    caller's features."""
    names = [
        class_name
        for agent in filter_feature_agents(agents, flags)
        if (class_name := getattr(agent, "class_name", None))
    ]
    return frozenset(names)


def feature_agent_visible(class_name: str | None, flags: Mapping[str, bool]) -> bool:
    """True unless ``class_name`` is a naas_abi office agent the caller cannot reach.

    An agent that serves several features (Settings, Agent Catalog) stays
    visible while the caller holds any one of them.
    """
    spec = spec_for_class_name(class_name)
    if spec is None:
        return True
    return any(flags.get(key, False) for key in spec.feature_keys)


def filter_feature_agents(
    agents: Iterable[AgentT],
    flags: Mapping[str, bool],
    *,
    keep_ids: Iterable[str] = (),
) -> list[AgentT]:
    """Drop the office agents whose feature the caller cannot reach.

    ``keep_ids`` pins rows that must survive regardless (the workspace
    default): losing the default would leave the picker with no agent to
    fall back on.
    """
    kept = set(keep_ids)
    return [
        agent
        for agent in agents
        if getattr(agent, "id", None) in kept
        or getattr(agent, "is_default", False)
        or feature_agent_visible(getattr(agent, "class_name", None), flags)
    ]


async def bind_usable_agents(agent_service: Any, user: object, workspace_id: str) -> frozenset[str]:
    """Set, for the rest of this request, the agent classes the caller may run
    and reach as sub-agents in ``workspace_id`` (the in-process runtime runs no
    other: the workspace's roster, its features, its module scopes), and the module
    workflows and pipelines its agents may run as tools."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (  # noqa: E501
        workspace_roster,
    )
    from naas_abi_core.services.agent.context import agent_workspace_enabled_class_names

    roster = await workspace_roster(agent_service, workspace_id)
    flags = await caller_feature_flags(user, workspace_id, feature_keys_of(roster))
    usable = await caller_usable_agents(roster, user, workspace_id, flags)
    allowed = caller_usable_class_names(usable, flags)
    agent_workspace_enabled_class_names.set(allowed)
    await bind_usable_processes(user, workspace_id)
    return allowed


async def bind_usable_processes(user: object, workspace_id: str | None) -> None:
    """Set the module workflows and pipelines this request's agents may run as
    tools: those the caller may run in ``workspace_id``; none without one."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import usable_process_scopes
    from naas_abi_core.services.agent.context import agent_usable_module_scopes

    agent_usable_module_scopes.set(
        await usable_process_scopes(user, workspace_id) if workspace_id else frozenset()
    )
