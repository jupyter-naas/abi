"""The ``nexus`` action catalog, registered with IAM at startup.

Every Nexus authorization decision is an action of this catalog on a resource
``abi:<org>:<workspace>:nexus:<type>/<id>``. The built-in roles are generated
from it by level (``naas_abi_core.services.iam.roles``): viewers get ``list``
and ``read``, members ``write``, admins ``admin``.
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
    workflows,
    workspaces,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import NexusAction
from naas_abi_core.services.iam.catalog import ActionCatalog, ResourceType

SERVICE = "nexus"
# Raise when the catalog changes; IAM keeps the highest version it has seen.
VERSION = 6

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
    settings,
    platform,
    realtime,
)

RESOURCE_TYPES: tuple[ResourceType, ...] = tuple(t for module in _MODULES for t in module.TYPES)
NEXUS_ACTIONS: tuple[NexusAction, ...] = tuple(a for module in _MODULES for a in module.ACTIONS)

NEXUS_CATALOG = ActionCatalog(
    service=SERVICE,
    version=VERSION,
    resource_types=RESOURCE_TYPES,
    actions=tuple(a.spec for a in NEXUS_ACTIONS),
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
