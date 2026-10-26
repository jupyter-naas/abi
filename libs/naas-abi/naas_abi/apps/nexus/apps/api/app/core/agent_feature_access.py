"""Feature office agents: workspace roster + per-caller visibility.

On sync, naas_abi office agents are enabled when their Nexus feature is on
for the workspace (union across roles). That keeps ``agent_configs`` aligned
with Apps, Search, Ontology, and the other sections without listing every
office agent in YAML.

Per-caller filtering still applies at list/chat time: a member without
Ontology does not see OntologyAgent in the picker, and Abi drops that
sub-agent for their turn. Non-office agents (client modules, Abi itself)
are not feature-gated.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

from naas_abi.agents.feature.registry import feature_office_agent_specs, spec_for_class_name
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import resolve_agent_ref
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


async def _workspace_feature_inputs(
    db: object,
    workspace_id: str,
) -> tuple[str | None, str | None, dict[str, bool] | None, Mapping[str, list[str]] | None]:
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import parse_feature_overrides
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
    from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
        OrganizationSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
    from sqlalchemy import select

    result = await db.execute(  # type: ignore[attr-defined]
        select(
            WorkspaceModel.slug,
            WorkspaceModel.organization_id,
            WorkspaceModel.feature_overrides,
        ).where(WorkspaceModel.id == workspace_id)
    )
    row = result.one_or_none()
    slug = row[0] if row else None
    organization_id = row[1] if row else None
    workspace_override = parse_feature_overrides(row[2]) if row else None

    org_baseline = None
    if organization_id:
        org_service = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        record = await org_service.get_role_features(org_id=organization_id)
        org_baseline = record.role_baseline if record is not None else None

    return slug, organization_id, workspace_override, org_baseline


async def workspace_union_feature_flags(db: object, workspace_id: str) -> dict[str, bool]:
    """Features any baseline role may use in this workspace (for agent sync)."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
        BASELINE_ROLES,
        KNOWN_FEATURE_KEYS,
        build_feature_flags,
    )
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    slug, organization_id, workspace_override, org_baseline = await _workspace_feature_inputs(
        db, workspace_id
    )
    merged = dict.fromkeys(KNOWN_FEATURE_KEYS, False)
    for role in BASELINE_ROLES:
        flags = build_feature_flags(
            role=role,
            feature_flags_config=live_settings().feature_flags,
            workspace_slug=slug,
            workspace_id=workspace_id,
            organization_id=organization_id,
            organization_override=org_baseline,
            workspace_override=workspace_override,
        )
        for key, value in flags.items():
            merged[key] = merged.get(key, False) or bool(value)
    return merged


def feature_office_class_names_for_flags(
    flags: Mapping[str, bool],
    registry: Mapping[str, Any],
) -> set[str]:
    """Registry keys for naas_abi office agents whose feature is on."""
    resolved: set[str] = set()
    for spec in feature_office_agent_specs():
        if not any(flags.get(key, False) for key in spec.feature_keys):
            continue
        class_name = resolve_agent_ref(spec.roster_ref, registry)
        if class_name:
            resolved.add(class_name)
    return resolved


def caller_enabled_class_names(
    agents: Iterable[AgentT],
    flags: Mapping[str, bool],
) -> frozenset[str]:
    """Enabled registry keys visible to this caller (roster ∩ feature access)."""
    names = [
        class_name
        for agent in filter_feature_agents(agents, flags)
        if getattr(agent, "enabled", False) and (class_name := getattr(agent, "class_name", None))
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
