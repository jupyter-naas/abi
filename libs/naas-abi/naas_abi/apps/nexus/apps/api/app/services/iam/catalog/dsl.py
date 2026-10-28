"""How a router declares what it authorizes (one module per router).

A module of this package exports ``TYPES`` (its resource types) and ``ACTIONS``
(its actions), built with ``rtype`` and ``action``. ``__init__`` aggregates them
into the ``nexus`` catalog, registered with IAM at startup.

Level is what the built-in roles are generated from:

* ``list`` and ``read``: viewers and up. A viewer reads everything it may see;
* ``write``: members and up. Every state change is at least ``write``;
* ``admin``: admins and up (owners alone for the deletes of
  ``naas_abi_core.services.iam.roles``).

``feature`` is the ``FeatureKey`` whose ``UseFeature`` the action also needs
(see "Roles, features and platform types" in ``services/iam/AGENTS.md``), checked first by ``authz``.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_core.services.iam.catalog import ActionSpec, Level, ResourceType
from naas_abi_core.services.iam.names import IdKind


@dataclass(frozen=True)
class NexusAction:
    spec: ActionSpec
    feature: str | None = None


def rtype(
    name: str,
    *,
    id: IdKind = "opaque",
    personal: bool = False,
    platform: bool = False,
    description: str = "",
) -> ResourceType:
    return ResourceType(
        name=name,
        id=id,
        placement="platform" if platform else "placed",
        personal=personal,
        description=description,
    )


def action(
    name: str,
    level: Level,
    resource_type: str,
    *,
    feature: str | None = None,
    description: str = "",
) -> NexusAction:
    return NexusAction(
        ActionSpec(
            name=name,
            level=level,
            resource_types=(resource_type,),
            description=description,
        ),
        feature=feature,
    )
