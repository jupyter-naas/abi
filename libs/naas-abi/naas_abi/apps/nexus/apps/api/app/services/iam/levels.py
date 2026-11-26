"""Levels as groups (#1585; ADR ``docs/adr/20261120_access_levels_and_groups.md``).

**Where** someone works is a membership group ("<W> workspace", ``container_defaults``);
**what** they do there is a level, written once and owned by the platform:

| Group | Holds |
|---|---|
| "Viewers" (level) | ``builtin.viewer`` and "Viewer access" at ``${my workspaces}``; the viewer model sets, unscoped |
| "Members" (level) | ``builtin.member`` and "Member access" at ``${my workspaces}``; the member model sets, unscoped |
| "Workspace admins" | the admin model sets (every model), unscoped: whoever is in a "<W> admins" or "<O> admins" |
| "Platform admins" | ``builtin.platform_admin``, unscoped (``users.is_superadmin``) |

A level is a pair. The built-in role is the level's actions: IAM generates it from the
catalogs by level (``list``/``read``, ``write``, ``admin``), keeps it in step with every
catalog change, and derives the platform companion of a role reached through
``${my workspaces}``. The generic level policy holds what no role does: the level's
features and the module scopes it may use (``${scope}/module:<type>/*``), never an
instance by name. At W, core IAM bounds it by what "<W> workspace" holds there, "<W>
access" (core "Bounds"): a Member uses W's offered agents and apps and the Member
features W offers, a Viewer W's offered apps. "Workspace admin access" (every feature,
agents, apps, workflows and pipelines) is held by "<W> admins" at ``${my workspaces}``
with ``builtin.admin`` (``container_defaults``), bounded the same way. Neither is
copied per workspace.

Everything here is the platform's and written as ``api`` for no user: made on first
need (``LEVELS.get``) and at start (``bootstrap``), found again by owner, name and
description, and the level policies' documents kept as this module writes them (a
feature added to the deployment's catalog reaches the admins at the next start).
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.names import MY_CONTAINERS_SCOPE, PLATFORM
from naas_abi_core.services.iam.policy import POLICY_VERSION, PolicyDocument

VIEWER = "viewer"
MEMBER = "member"
LEVELS_ORDER = (MEMBER, VIEWER)  # the higher first

VIEWER_FEATURES: tuple[str, ...] = ("apps", "datasets")
MEMBER_FEATURES: tuple[str, ...] = (
    "apps",
    "chat",
    "files",
    "datasets",
    "graph",
    "maps",
    "ontology",
    "search",
)
ADMIN_FEATURES: tuple[str, ...] = KNOWN_FEATURE_KEYS

VIEWER_ACCESS = "Viewer access"
MEMBER_ACCESS = "Member access"
WORKSPACE_ADMIN_ACCESS = "Workspace admin access"

VIEWERS = "Viewers"
MEMBERS = "Members"
PLATFORM_ADMINS = "Platform admins"

# The built-in role each level holds beside its policy.
WORKSPACE_ADMINS = "Workspace admins"
LEVEL_ROLE: dict[str, str] = {VIEWER: roles.VIEWER, MEMBER: roles.MEMBER}
ROLE_LEVEL: dict[str, str] = {role: level for level, role in LEVEL_ROLE.items()}

_KEPT = (
    " Nexus keeps it (#1585): it is written once for every workspace, and an edit is "
    "replaced at the next start."
)
# What each level policy's description says, around its features: the part before
# them finds the policy again whatever the deployment sets (``_policy``).
_DESCRIBED: dict[str, tuple[str, str]] = {
    VIEWER_ACCESS: (
        "What a Viewer uses where they are a member (with builtin.viewer), within what the "
        "workspace offers: ",
        " and its apps.",
    ),
    MEMBER_ACCESS: (
        "What a Member uses where they are a member (with builtin.member), within what the "
        "workspace offers: ",
        ", its agents and apps.",
    ),
    WORKSPACE_ADMIN_ACCESS: (
        "What a workspace admin uses in their workspace (with builtin.admin), within what it "
        "offers: ",
        ", its agents, apps, workflows and pipelines.",
    ),
}
# The level each configurable level policy is (``feature_flags.level_features``).
_CONFIGURED: dict[str, str] = {VIEWER_ACCESS: VIEWER, MEMBER_ACCESS: MEMBER}
_DEFAULT_FEATURES: dict[str, tuple[str, ...]] = {
    VIEWER_ACCESS: VIEWER_FEATURES,
    MEMBER_ACCESS: MEMBER_FEATURES,
    WORKSPACE_ADMIN_ACCESS: ADMIN_FEATURES,
}


def level_features(name: str) -> tuple[str, ...]:
    """The features the level policy ``name`` gives: the deployment's
    (``feature_flags.level_features``), else the default; every feature for a
    workspace admin."""
    level = _CONFIGURED.get(name)
    if level is not None:
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

        flags = getattr(live_settings(), "feature_flags", None)
        configured = getattr(flags, "level_features", None) or {}
        if level in configured:
            return tuple(configured[level])
    return _DEFAULT_FEATURES[name]


def description(name: str) -> str:
    """The description of the level policy ``name``, its features named."""
    before, after = _DESCRIBED[name]
    features = level_features(name)
    named = (
        "every feature"
        if name == WORKSPACE_ADMIN_ACCESS
        else ("the " + ", ".join(features) + " features" if features else "no feature")
    )
    return before + named + after + _KEPT


GROUP_DESCRIPTIONS: dict[str, str] = {
    VIEWERS: "The Viewer level: builtin.viewer and Viewer access in each of one's workspaces.",
    MEMBERS: "The Member level: builtin.member and Member access in each of one's workspaces.",
    PLATFORM_ADMINS: "The platform admins (users.is_superadmin): builtin.platform_admin.",
    WORKSPACE_ADMINS: (
        "Everyone in a workspace's or an organization's admins group: every model. Nexus "
        "keeps its members in step with those groups."
    ),
}


def features_statement(features: Sequence[str]) -> dict[str, Any]:
    return {
        "sid": "Features",
        "effect": "Allow",
        "actions": ["nexus:UseFeature"],
        "resources": [f"${{scope}}/nexus:feature/{key}" for key in features],
    }


# The module scopes each level uses (``${scope}/module:<type>/*``), within its
# workspace's offer.
LEVEL_INSTANCES: dict[str, tuple[str, ...]] = {
    VIEWER_ACCESS: (module_scopes.APP,),
    MEMBER_ACCESS: (module_scopes.AGENT, module_scopes.APP),
    WORKSPACE_ADMIN_ACCESS: (
        module_scopes.AGENT,
        module_scopes.APP,
        module_scopes.WORKFLOW,
        module_scopes.PIPELINE,
    ),
}


def instances_statement(types: Sequence[str]) -> dict[str, Any]:
    service = module_scopes.SERVICE
    actions = [f"{service}:{module_scopes.USE_ACTION[t]}" for t in types]
    actions += [
        f"{service}:{module_scopes.RUNS_ACTION[t]}" for t in types if t in module_scopes.RUNS_ACTION
    ]
    return {
        "sid": "Instances",
        "effect": "Allow",
        "actions": actions,
        "resources": [f"${{scope}}/{service}:{t}/*" for t in types],
    }


def search_sources_statement() -> dict[str, Any]:
    """Every search source, by type, for a level that searches: the workspace's
    offer names which (``OfferSearchSources``)."""
    return {
        "sid": "SearchSources",
        "effect": "Allow",
        "actions": ["nexus:UseSearchSource"],
        "resources": ["${scope}/nexus:search_source/*"],
    }


def models_statement() -> dict[str, Any]:
    """Every chat model, by type, for a level that chats: the workspace's offer names
    which (``OfferModels``; ``*`` every one), the person's model set which of those
    they may use (``model_sets``)."""
    return {
        "sid": "Models",
        "effect": "Allow",
        "actions": ["nexus:UseModel"],
        "resources": ["${scope}/nexus:model/*"],
    }


def ontologies_statement() -> dict[str, Any]:
    """Every ontology file, by type, for a level that reads ontologies: the workspace's
    offer names which (``OfferOntologies``)."""
    return {
        "sid": "Ontologies",
        "effect": "Allow",
        "actions": ["nexus:UseOntology"],
        "resources": ["${scope}/nexus:ontology_file/*"],
    }


def viewer_my_files() -> bool:
    """Whether a Viewer reads their My Files: the deployment's
    ``feature_flags.viewer_my_files`` (on by default)."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    flags = getattr(live_settings(), "feature_flags", None)
    return bool(getattr(flags, "viewer_my_files", True))


# What a Viewer reads of their own files through the platform companion of their role
# (``catalog.files.PLATFORM_ACCESS``): My Files and their platform storage.
MY_FILES_READ = (
    "nexus:ListMyFiles",
    "nexus:GetMyFile",
    "nexus:ListUserStorage",
    "nexus:GetUserStorage",
)


def no_my_files_statement() -> dict[str, Any]:
    """A Deny of My Files, for "Viewer access" on a deployment that keeps it from
    Viewers (``viewer_my_files`` off). A Deny may name what lies outside its scope."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

    return {
        "sid": "NoMyFiles",
        "effect": "Deny",
        "actions": list(MY_FILES_READ),
        "resources": [
            nexus_resource(type_name, id=("-",)).rsplit("/", 1)[0] + "/*"
            for type_name in ("my_file", "user_storage")
        ],
    }


def level_document(name: str) -> PolicyDocument:
    """The document of a generic level policy (``VIEWER_ACCESS``, ``MEMBER_ACCESS``,
    ``WORKSPACE_ADMIN_ACCESS``): its features, the module scopes it uses and the
    search sources, every one of a type (the workspace's bound names which). The
    actions of the level are the built-in role's, held beside it. "Viewer access"
    denies My Files when the deployment keeps it from Viewers."""
    statements = [
        features_statement(level_features(name)),
        instances_statement(LEVEL_INSTANCES[name]),
    ]
    if "search" in level_features(name):
        statements.append(search_sources_statement())
    if "ontology" in level_features(name):
        statements.append(ontologies_statement())
    if "chat" in level_features(name):
        statements.append(models_statement())
    if name == VIEWER_ACCESS and not viewer_my_files():
        statements.append(no_my_files_statement())
    return PolicyDocument.from_dict({"version": POLICY_VERSION, "statements": statements})


@dataclass(frozen=True)
class Levels:
    """The platform's level groups and generic level policies, by id."""

    viewers: str
    members: str
    platform_admins: str
    workspace_admins: str
    viewer_access: str
    member_access: str
    workspace_admin_access: str

    def group_of(self, level: str) -> str:
        return {VIEWER: self.viewers, MEMBER: self.members}[level]

    def level_of_group(self, group_id: str) -> str | None:
        return {self.viewers: VIEWER, self.members: MEMBER}.get(group_id)

    @property
    def level_groups(self) -> tuple[str, str]:
        return (self.members, self.viewers)


def _pages(listing: Any, **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _policy(iam: Any, name: str, *, make: bool = True) -> str | None:
    """The platform's level policy ``name``: found by owner, name and the start of
    its description, else made (``make``); its document and description rewritten
    when they are not this deployment's (``level_features``)."""
    wanted = level_document(name)
    described = description(name)
    for policy in _pages(iam.list_policies):
        if (policy.owner_scope, policy.name) == (PLATFORM, name) and str(
            policy.description or ""
        ).startswith(_DESCRIBED[name][0]):
            if make and (
                policy.document.to_dict() != wanted.to_dict() or policy.description != described
            ):
                iam.update_policy(
                    policy.id,
                    expected_revision=policy.revision,
                    document=wanted,
                    description=described,
                )
            return str(policy.id)
    return str(iam.create_policy(name, wanted, description=described).id) if make else None


def _group(iam: Any, name: str, *, level: bool, make: bool = True) -> str | None:
    """The platform's group ``name`` (a level group when ``level``): found, else made
    (``make``)."""
    for group in _pages(iam.list_groups):
        if (
            group.owner_scope == PLATFORM
            and group.name == name
            and group.status != "deleted"
            and bool(getattr(group, "level_group", False)) == level
        ):
            return str(group.id)
    if not make:
        return None
    from naas_abi.apps.nexus.apps.api.app.services.iam.group_descriptions import described

    return str(
        iam.create_group(
            name, level=level, description=described(name, owner=PLATFORM, level=level)
        ).id
    )


def find_levels(iam: Any) -> Levels | None:
    """The levels as they are, made by no one: None until a start (or a change of
    memberships) made them. What a read uses, which writes nothing. As ``api``."""
    with as_service_account("api"):
        found = (
            _group(iam, VIEWERS, level=True, make=False),
            _group(iam, MEMBERS, level=True, make=False),
            _group(iam, PLATFORM_ADMINS, level=False, make=False),
            _group(iam, WORKSPACE_ADMINS, level=False, make=False),
            _policy(iam, VIEWER_ACCESS, make=False),
            _policy(iam, MEMBER_ACCESS, make=False),
            _policy(iam, WORKSPACE_ADMIN_ACCESS, make=False),
        )
    if any(item is None for item in found):
        return None
    return Levels(*(str(item) for item in found))


def _hold(iam: Any, policy_id: str, group_id: str, scope: str | None) -> None:
    if not any(
        (a.policy_id, a.scope) == (policy_id, scope)
        for a in iam.list_attachments(principal_id=group_id)
    ):
        iam.attach_policy(policy_id, group_id, scope)


def ensure_levels(iam: Any) -> Levels:
    """Find or make the level groups, "Workspace admins", "Platform admins" and the
    level policies, and what they hold (the model sets of ``model_sets``, unscoped:
    their names are the platform's). Idempotent. As ``api`` for no user (IAM's
    thread)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.model_sets import (
        level_model_policy_ids,
    )

    with as_service_account("api"):
        levels = Levels(
            viewers=str(_group(iam, VIEWERS, level=True)),
            members=str(_group(iam, MEMBERS, level=True)),
            platform_admins=str(_group(iam, PLATFORM_ADMINS, level=False)),
            workspace_admins=str(_group(iam, WORKSPACE_ADMINS, level=False)),
            viewer_access=str(_policy(iam, VIEWER_ACCESS)),
            member_access=str(_policy(iam, MEMBER_ACCESS)),
            workspace_admin_access=str(_policy(iam, WORKSPACE_ADMIN_ACCESS)),
        )
        for group, role, policy in (
            (levels.viewers, roles.VIEWER, levels.viewer_access),
            (levels.members, roles.MEMBER, levels.member_access),
        ):
            _hold(iam, role, group, MY_CONTAINERS_SCOPE)
            _hold(iam, policy, group, MY_CONTAINERS_SCOPE)
        for group, level in (
            (levels.viewers, "viewer"),
            (levels.members, "member"),
            (levels.workspace_admins, "admin"),
        ):
            for model_policy in level_model_policy_ids(iam, level):  # type: ignore[arg-type]
                _hold(iam, model_policy, group, None)
        _hold(iam, roles.PLATFORM_ADMIN, levels.platform_admins, None)
    return levels


class LevelRegistry:
    """The levels of this process's IAM, made once (``ensure_levels``) and remembered
    for the IAM service that made them (a test installs another)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._levels: Levels | None = None
        self._of: int | None = None

    def get(self, iam: Any) -> Levels:
        with self._lock:
            if self._levels is None or self._of != id(iam):
                if self._of is not None and self._of != id(iam):
                    from naas_abi.apps.nexus.apps.api.app.services.iam import model_sets

                    model_sets.forget()  # another IAM (a test's): its own policies
                self._levels = ensure_levels(iam)
                self._of = id(iam)
            return self._levels

    def peek(self, iam: Any) -> Levels | None:
        """The levels when made (remembered, else found), never making them: for a
        read, which writes nothing."""
        with self._lock:
            if self._levels is not None and self._of == id(iam):
                return self._levels
        return find_levels(iam)

    def forget(self) -> None:
        with self._lock:
            self._levels = None
            self._of = None


LEVELS = LevelRegistry()

__all__ = [
    "ADMIN_FEATURES",
    "LEVELS",
    "LEVEL_ROLE",
    "MEMBER",
    "MEMBERS",
    "MEMBER_ACCESS",
    "MEMBER_FEATURES",
    "PLATFORM_ADMINS",
    "ROLE_LEVEL",
    "VIEWER",
    "VIEWERS",
    "VIEWER_ACCESS",
    "VIEWER_FEATURES",
    "WORKSPACE_ADMINS",
    "WORKSPACE_ADMIN_ACCESS",
    "LevelRegistry",
    "Levels",
    "ensure_levels",
    "find_levels",
    "level_document",
]
