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

AgentT = TypeVar("AgentT")


async def caller_feature_flags(db: object, workspace_id: str, role: str | None) -> dict[str, bool]:
    """Feature access this caller holds in this workspace, on an open session.

    Same resolution the workspace listing sends the frontend (deployment
    ``role_baseline``, org overlay, workspace overrides), so the agents a
    user is offered match the sections they can open. Callers that own a
    session pass it; the HTTP adapter opens one of its own.
    """
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
    from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
        OrganizationSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
    from sqlalchemy import select

    result = await db.execute(  # type: ignore[attr-defined]
        select(WorkspaceModel.slug, WorkspaceModel.organization_id).where(
            WorkspaceModel.id == workspace_id
        )
    )
    row = result.one_or_none()
    slug = row[0] if row else None
    organization_id = row[1] if row else None

    override = None
    if organization_id:
        org_service = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        record = await org_service.get_role_features(org_id=organization_id)
        override = record.role_baseline if record is not None else None

    return build_feature_flags(
        role=role or "member",
        feature_flags_config=live_settings().feature_flags,
        workspace_slug=slug,
        workspace_id=workspace_id,
        organization_id=organization_id,
        organization_override=override,
    )


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
