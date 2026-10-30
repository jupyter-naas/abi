"""The ``nexus`` action catalog, registered with IAM at startup.

Every Nexus authorization decision is an action of this catalog on a resource
in a container (``<container>/nexus:<type>/<id>``: an organization's or a
workspace's, both containers of this catalog), on a container itself, or at the
platform (``abi:nexus:<type>/<id>``). The built-in roles are generated
from it by level (``naas_abi_core.services.iam.roles``): viewers get ``list``
and ``read``, members ``write``, admins ``admin``. What they leave out is
flagged here: no role holds a feature (``policy_only``), and only owners
delete the workspace or the organization (``owner_only``); the platform
companions of the roles reach what ``PLATFORM_ACCESS`` names.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import (
    agents,
    apps,
    chat,
    code,
    datasets,
    features,
    files,
    knowledge,
    office,
    organizations,
    platform,
    realtime,
    search,
    settings,
    tasks,
    workflows,
    workspaces,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import NexusAction
from naas_abi_core.services.iam.catalog import (
    NAAS_ABI,
    ActionCatalog,
    PlatformAccess,
    ResourceType,
)

SERVICE = "nexus"
# Raise when the catalog changes; IAM keeps the highest version it has seen.
# 9: published by naas_abi (``publisher``).
VERSION = 9

_MODULES = (
    organizations,
    workspaces,
    features,
    chat,
    agents,
    files,
    datasets,
    search,
    office,
    knowledge,
    apps,
    workflows,
    code,
    tasks,
    settings,
    platform,
    realtime,
)

RESOURCE_TYPES: tuple[ResourceType, ...] = tuple(t for module in _MODULES for t in module.TYPES)
NEXUS_ACTIONS: tuple[NexusAction, ...] = tuple(a for module in _MODULES for a in module.ACTIONS)
PLATFORM_ACCESS: tuple[PlatformAccess, ...] = tuple(
    row for module in _MODULES for row in getattr(module, "PLATFORM_ACCESS", ())
)

NEXUS_CATALOG = ActionCatalog(
    service=SERVICE,
    version=VERSION,
    resource_types=RESOURCE_TYPES,
    actions=tuple(a.spec for a in NEXUS_ACTIONS),
    platform_access=PLATFORM_ACCESS,
    # naas_abi publishes it (core ``services/iam/AGENTS.md``, "Publishers and listing").
    publisher=NAAS_ABI,
)

# action name -> the feature whose UseFeature it also needs.
FEATURE_OF: dict[str, str] = {
    a.spec.name: a.feature for a in NEXUS_ACTIONS if a.feature is not None
}
# action name -> its (single) resource type.
TYPE_OF: dict[str, str] = {a.spec.name: a.spec.resource_types[0] for a in NEXUS_ACTIONS}
LEVEL_OF: dict[str, str] = {a.spec.name: a.spec.level for a in NEXUS_ACTIONS}
TYPES_BY_NAME: dict[str, ResourceType] = {t.name: t for t in RESOURCE_TYPES}

__all__ = [
    "FEATURE_OF",
    "LEVEL_OF",
    "NEXUS_CATALOG",
    "SERVICE",
    "TYPES_BY_NAME",
    "TYPE_OF",
    "VERSION",
]
