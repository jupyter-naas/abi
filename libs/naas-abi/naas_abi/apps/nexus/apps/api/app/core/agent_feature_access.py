"""Per-caller visibility of the naas_abi feature office agents.

``agent_configs.enabled`` is workspace-scoped: it answers "does this
workspace run this agent", which the ``agents:`` roster seed decides. It
cannot answer "may *this* user see it", because two members of the same
workspace hold different roles and therefore different feature access.

So the role rule is applied when a listing is rendered, never by writing
``enabled``. A member who cannot open Ontology does not get the Ontology
agent in the picker, and the right pane falls back to the workspace
default there, while the owner in the same workspace still sees it.

The rule covers the ``naas_abi`` office agents only: every other module's
agents (and naas_abi's own Abi orchestrator) pass through untouched, since
no feature flag governs them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TypeVar

from naas_abi.agents.feature.registry import spec_for_class_name
from naas_abi.apps.nexus.apps.api.app.services.iam import authz

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
    deployment's ``role_baseline``, the org overlay, the workspace overrides),
    so the agents a user is offered match the sections they can open.
    """
    return {
        key: await authz.allowed("UseFeature", user=user, workspace=workspace_id, id=key)
        for key in sorted(set(keys))
    }


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
