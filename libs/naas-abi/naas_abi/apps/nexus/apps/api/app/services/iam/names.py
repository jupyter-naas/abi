"""Nexus's names in IAM: its containers and the names of what they hold.

An organization is a container at the platform, ``abi:nexus:organization/<org>``.
A workspace is a container in its organization,
``abi:nexus:organization/<org>/nexus:workspace/<ws>``, or at the platform,
``abi:nexus:workspace/<ws>``, when it belongs to none (a signup's personal
workspace). Everything else Nexus names sits in one of them,
``<container>/nexus:<type>/<id>``, or at the platform, ``abi:nexus:<type>/<id>``.

Every name is built here, through core's ``names``: never by string formatting.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import TYPES_BY_NAME

# The old grammar's org of a workspace in none: only the start-up moves that
# predate container paths import it (``legacy_names``).
from naas_abi.apps.nexus.apps.api.app.services.iam.legacy_names import NO_ORG  # noqa: F401
from naas_abi_core.services.iam import names as core_names
from naas_abi_core.services.iam.names import (
    PLATFORM,
    below,
    container_name,
    container_of_scope,
    parse_container,
    resource_name,
)

SERVICE = "nexus"
ORGANIZATION = "organization"
WORKSPACE = "workspace"
# Ids that name no workspace: a path or query value of these never stands for one.
RESERVED_WORKSPACE_IDS = frozenset({"", "-", "*"})


def org_container(org_id: str) -> str:
    """An organization's container, where its own roles are attached:
    ``abi:nexus:organization/<org>``."""
    return container_name(SERVICE, ORGANIZATION, org_id)


def org_below(org_id: str) -> str:
    """Below an organization (``<org container>/*``): where its owners' and
    admins' roles are mirrored, reaching each of its workspaces."""
    return below(org_container(org_id))


def workspace_container(org_id: str | None, workspace_id: str) -> str:
    """A workspace's container, where its roles are attached: in its organization,
    or at the platform for a workspace in none."""
    parent = org_container(org_id) if org_id else PLATFORM
    return container_name(SERVICE, WORKSPACE, workspace_id, parent=parent)


def _steps(scope: str) -> tuple[core_names.Step, ...]:
    """The steps of a scope's container; none for anything else (the platform, a
    name of the old grammar)."""
    try:
        return parse_container(container_of_scope(scope))
    except (TypeError, ValueError):
        return ()


def org_of(scope: str) -> str | None:
    """The organization a Nexus container (or a scope at or below it) is or sits
    in; None for a workspace in none, the platform and anything else."""
    steps = _steps(scope)
    if steps and (steps[0].service, steps[0].type) == (SERVICE, ORGANIZATION):
        return steps[0].value
    return None


def workspace_of(scope: str) -> str | None:
    """The workspace a scope is at (a workspace's container); None for any other."""
    steps = _steps(scope)
    if steps and (steps[-1].service, steps[-1].type) == (SERVICE, WORKSPACE):
        return steps[-1].value
    return None


def is_org_container(scope: str) -> bool:
    """Whether ``scope`` is an organization's container itself (not below it)."""
    steps = _steps(scope)
    return (
        len(steps) == 1
        and not core_names.is_below(scope)
        and (steps[0].service, steps[0].type) == (SERVICE, ORGANIZATION)
    )


def is_workspace_container(scope: str) -> bool:
    return not core_names.is_below(scope) and workspace_of(scope) is not None


def nexus_resource(
    type_name: str,
    *,
    container: str = PLATFORM,
    id: str | Sequence[str] = (),
) -> str:
    """The canonical name of a Nexus resource in ``container`` (the platform by
    default; a platform type is always there).

    A container type (``organization``, ``workspace``) is decided where it is:
    without ``id`` its resource is ``container`` itself, which must be one of
    that type; with ``id`` it is a new one of that type in ``container`` (what
    its create action is checked on).
    """
    resource_type = TYPES_BY_NAME[type_name]
    kind = resource_type.id
    if resource_type.placement == "platform":
        container = PLATFORM
    if resource_type.container:
        if id:
            if not isinstance(id, str):
                raise ValueError(f"A {type_name}'s id is one value")
            return container_name(SERVICE, type_name, id, parent=container)
        steps = parse_container(container)
        if not steps or (steps[-1].service, steps[-1].type) != (SERVICE, type_name):
            raise ValueError(f"{container!r} is not a {type_name}")
        return container
    return resource_name(
        SERVICE,
        type_name,
        id if kind != "singleton" else (),
        kind=kind,
        container=container,
    )


__all__ = [
    "ORGANIZATION",
    "PLATFORM",
    "RESERVED_WORKSPACE_IDS",
    "SERVICE",
    "WORKSPACE",
    "is_org_container",
    "is_workspace_container",
    "nexus_resource",
    "org_below",
    "org_container",
    "org_of",
    "workspace_container",
    "workspace_of",
]
