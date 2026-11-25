"""What each group of the access model is for: the ``description`` IAM keeps for a group
(schema 9), shown on its page.

A group the access model makes (a level group, an organization's or a workspace's groups,
a capability group, a workspace's Platform Files group) is given its sentence when it is
made; one made before descriptions existed is given it by each start
(``describe_groups``), once: a description someone wrote is kept. A group a person makes
is theirs to describe (``described`` answers None for it).
"""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.names import PLATFORM

VIEWERS = (
    "The Viewer level: in each workspace they belong to, its people open the apps the "
    "workspace offers, and read the rest."
)
MEMBERS = (
    "The Member level: in each workspace they belong to, its people use what the "
    "workspace offers, but its settings."
)
PLATFORM_ADMINS = "The platform's administrators: they may do everything, everywhere."
ALL_WORKSPACE_ADMINS = (
    "Everyone in an organization's or a workspace's admins group, kept in step by Nexus: "
    "they use every model."
)
MODELS_ALL = "Who may use every model of the platform, beyond a workspace's own."
WORKFLOW_RUNNERS = "Who may run the organization's workflows, within what it offers."
PLATFORM_FILES = (
    "The people of a workspace given Platform Files, kept in step by Nexus: they read "
    "(or also write) the platform's files."
)
WORKSPACE = (
    "Everyone who belongs to the workspace: they use what it offers, at their level "
    "(Viewer or Member)."
)
WORKSPACE_ADMINS = "The workspace's administrators: they manage its people, groups and settings."
ORG_ADMINS = (
    "The organization's administrators: they administer it and every one of its workspaces."
)
ORG_PEOPLE = (
    "People of the organization who belong to none of its workspaces: they stay in its "
    "Users list, and see the organization."
)


def described(
    name: str | None,
    *,
    owner: str | None,
    membership_of: str | None = None,
    level: bool = False,
) -> str | None:
    """The sentence of a group of the access model, told by its name at its owner and its
    markers; None for any other group (a person's: theirs to describe)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import capabilities, levels
    from naas_abi.apps.nexus.apps.api.app.services.iam.platform_files import GROUP_PREFIX

    name = name or ""
    owner = owner or PLATFORM
    if owner == PLATFORM:
        if name == levels.VIEWERS and level:
            return VIEWERS
        if name == levels.MEMBERS and level:
            return MEMBERS
        if name == levels.PLATFORM_ADMINS:
            return PLATFORM_ADMINS
        if name == levels.WORKSPACE_ADMINS:
            return ALL_WORKSPACE_ADMINS
        if name == capabilities.MODELS_ALL:
            return MODELS_ALL
        if name.startswith(GROUP_PREFIX):
            return PLATFORM_FILES
        return None
    if is_workspace_container(owner) and membership_of == owner:
        if name.endswith(" workspace"):
            return WORKSPACE
        if name.endswith(" admins"):
            return WORKSPACE_ADMINS
        return None
    if is_org_container(owner):
        if name == capabilities.WORKFLOW_RUNNERS:
            return WORKFLOW_RUNNERS
        if membership_of == owner and name.endswith(" people"):
            return ORG_PEOPLE
        if membership_of is None and name.endswith(" admins"):
            return ORG_ADMINS
    return None


def describe_groups(iam: Any) -> int:
    """Give each group of the access model with no description its sentence, as ``api``:
    the groups made before descriptions existed. One that has one keeps it. Returns how
    many were described; a group that cannot be is logged and left."""
    done = 0
    with as_service_account("api"):
        after: str | None = None
        while True:
            page = iam.list_groups(limit=500, after=after)
            for group in page.items:
                if group.status == "deleted" or group.description:
                    continue
                sentence = described(
                    group.name,
                    owner=group.owner_scope,
                    membership_of=group.membership_of,
                    level=bool(group.level_group),
                )
                if sentence is None:
                    continue
                try:
                    iam.update_group(group.id, description=sentence)
                    done += 1
                except Exception:  # noqa: BLE001 - a description, never a failed start
                    logger.warning(f"Group {group.id} could not be described", exc_info=True)
            after = page.next_after
            if not after:
                break
    return done
