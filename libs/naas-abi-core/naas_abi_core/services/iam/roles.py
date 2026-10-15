"""Built-in managed policies (RFC §7), generated from the registered catalogs.

Roles are attached at a scope: "viewer on workspace W" is ``builtin.viewer``
attached with scope ``abi:<org>:W``. They are cumulative (viewer ⊆ member ⊆
admin ⊆ owner) and stored with explicit action lists, so ``explain`` shows real
statements. IAM regenerates them whenever a catalog changes.

Also here, and named so: the TRANSITIONAL policies that keep every caller
working before the later subtasks of #44 land: ``builtin.engine`` and
``builtin.api`` are one broad statement each (``TransitionalBroadAccess``).
Subtask 11 (#65) replaces them with enumerated statements.

* ``builtin.engine`` and ``builtin.api`` are one broad statement each
  (``TransitionalBroadAccess``). Subtask 11 (#65) replaces them with enumerated
  statements.
* ``builtin.transitional.nexus_user`` is what a Nexus user holds until
  subtask 11 (#65) attaches the roles of its memberships: Nexus still decides
  what such a user may do, as before IAM. It never reaches another
  principal's agent runs: discovery is granted on its modules, agents,
  models, apps and jobs, and on the holder's own runs only
  (``run/${principal.id}/*``).

``builtin.module_bootstrap`` is what every module's service account holds,
approved or not (RFC §8.3): its own discovery record and its own manifest.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from naas_abi_core.services.iam.catalog import ActionCatalog, CatalogRegistry, Level
from naas_abi_core.services.iam.IAMPorts import Policy
from naas_abi_core.services.iam.policy import PolicyDocument, Statement

VIEWER = "builtin.viewer"
MEMBER = "builtin.member"
ADMIN = "builtin.admin"
OWNER = "builtin.owner"
PLATFORM_ADMIN = "builtin.platform_admin"
SELF = "builtin.self"
PLATFORM_VIEWER = "builtin.platform.viewer"
PLATFORM_MEMBER = "builtin.platform.member"
ENGINE = "builtin.engine"
API = "builtin.api"
IDP = "builtin.idp"
TRANSITIONAL_NEXUS_USER = "builtin.transitional.nexus_user"
MODULE_BOOTSTRAP = "builtin.module_bootstrap"

ROLES = (VIEWER, MEMBER, ADMIN, OWNER)
ROLE_LEVELS: dict[str, frozenset[Level]] = {
    VIEWER: frozenset({"list", "read"}),
    MEMBER: frozenset({"list", "read", "write"}),
    ADMIN: frozenset({"list", "read", "write", "admin"}),
    OWNER: frozenset({"list", "read", "write", "admin"}),
}
# The workspace roles that bring builtin.platform.member; viewer brings .viewer.
PLATFORM_MEMBER_ROLES = frozenset({MEMBER, ADMIN, OWNER})

# The built-in service accounts and the policy each holds.
SERVICE_ACCOUNTS: dict[str, str] = {"engine": ENGINE, "api": API, "idp": IDP}

# No role reaches UseFeature through its scope: features come from feature policies.
_FEATURE_TYPE = ("nexus", "feature")
# Kept from admins: they are the owner's.
_OWNER_ONLY_ACTIONS = frozenset({"nexus:DeleteWorkspace", "nexus:DeleteOrganization"})
_ATTACHMENT_TYPE = ("iam", "attachment")
_MAX_ACTIONS = 100


@dataclass(frozen=True)
class _PlatformRow:
    """A row of RFC §7 "Platform types": who reaches a platform-level type."""

    service: str
    resources: tuple[str, ...]
    viewer: tuple[str, ...] = ()
    member: tuple[str, ...] = ()
    self_: tuple[str, ...] = ()


PLATFORM_TYPES: tuple[_PlatformRow, ...] = (
    _PlatformRow(
        "model_registry",
        ("model/*",),
        viewer=("ListModels", "Resolve"),
        member=("Chat", "ChatStream", "Embed"),
    ),
    _PlatformRow(
        "discovery",
        ("module/*", "agent/*", "app/*"),
        viewer=("ListModules", "GetModule", "ListAgents", "ListApps", "OpenApp"),
        member=("InvokeAgent",),
    ),
    _PlatformRow("discovery", ("model/*",), member=("ChatModel",)),
    _PlatformRow(
        "discovery",
        ("run/${principal.id}/*",),
        viewer=("GetAgentRun",),
        member=("CancelAgentRun",),
    ),
    _PlatformRow("triple_store", ("view/*",), viewer=("QueryView",)),
    _PlatformRow("coding_environment", ("template/*",), viewer=("ListTemplates",)),
    _PlatformRow(
        "coding_environment", ("coder_user/${principal.id}",), self_=("EnsureUser",)
    ),
    _PlatformRow(
        "source_control",
        ("forge_user/${principal.id}",),
        self_=("EnsureUser", "MintGitToken"),
    ),
    _PlatformRow(
        "activity_log",
        ("actor/${principal.id}",),
        self_=("Query", "QueryStream", "Record"),
    ),
    _PlatformRow("iam", ("principal/${principal.id}",), self_=("GetPrincipal",)),
    _PlatformRow(
        "iam",
        ("key/${principal.id}/*",),
        self_=("ListKeys", "CreateKey", "RevokeKey"),
    ),
    _PlatformRow("nexus", ("organization/-",), self_=("CreateOrganization",)),
    _PlatformRow(
        "nexus",
        ("provider_model/*",),
        viewer=("ListProviderModels", "GetProviderModel"),
    ),
)


def _sid(*words: str) -> str:
    joined = "".join(
        part[:1].upper() + part[1:]
        for word in words
        for part in word.replace(".", "_").split("_")
        if part
    )
    return "".join(c for c in joined if c.isalnum())[:64]


def _chunks(actions: Sequence[str]) -> list[tuple[str, ...]]:
    return [
        tuple(actions[i : i + _MAX_ACTIONS])
        for i in range(0, len(actions), _MAX_ACTIONS)
    ]


def _role_statements(role: str, catalog: ActionCatalog) -> list[Statement]:
    """One statement per (catalog, kind of resource) for ``role``'s levels."""
    levels = ROLE_LEVELS[role]
    placed = [
        t
        for t in catalog.resource_types
        if t.placement == "placed" and (catalog.service, t.name) != _FEATURE_TYPE
    ]
    groups: dict[bool, tuple[list[str], list[str]]] = {
        False: ([], []),
        True: ([], []),
    }
    for resource_type in placed:
        actions, resources = groups[resource_type.personal]
        base = f"${{scope}}:{catalog.service}:{resource_type.name}/"
        if resource_type.personal:
            resources += [f"{base}${{principal.id}}", f"{base}${{principal.id}}/*"]
        else:
            resources.append(f"{base}*")
        for action in catalog.actions:
            if (
                action.level not in levels
                or resource_type.name not in action.resource_types
            ):
                continue
            qualified = catalog.qualified(action.name)
            if role != OWNER and action.level == "admin":
                if (catalog.service, resource_type.name) == _ATTACHMENT_TYPE:
                    continue
                if qualified in _OWNER_ONLY_ACTIONS:
                    continue
            if qualified not in actions:
                actions.append(qualified)
    statements: list[Statement] = []
    for personal, (actions, resources) in groups.items():
        if not actions:
            continue
        for index, chunk in enumerate(_chunks(actions)):
            statements.append(
                Statement(
                    effect="Allow",
                    actions=chunk,
                    resources=tuple(resources),
                    sid=_sid(
                        role.removeprefix("builtin."),
                        catalog.service,
                        "personal" if personal else "",
                        str(index + 1) if index else "",
                    ),
                )
            )
    return statements


def _admin_attachment_statements(registry: CatalogRegistry) -> list[Statement]:
    """Admins grant and revoke the roles below owner, never owner (RFC §7)."""
    if registry.get("iam") is None:
        return []
    return [
        Statement(
            effect="Allow",
            actions=("iam:AttachPolicy", "iam:DetachPolicy"),
            resources=tuple(
                f"${{scope}}:iam:attachment/{role}/*"
                for role in (ADMIN, MEMBER, VIEWER)
            ),
            sid="AdminGrantsRolesBelowOwner",
        )
    ]


def role_policy(role: str, registry: CatalogRegistry) -> Policy:
    statements: list[Statement] = []
    for catalog in registry.all():
        statements += _role_statements(role, catalog)
    if role == ADMIN:
        statements += _admin_attachment_statements(registry)
    return _managed(
        role,
        role.removeprefix("builtin.").capitalize(),
        f"The {role.removeprefix('builtin.')} role, attached at a scope.",
        statements,
    )


def _platform_statements(
    registry: CatalogRegistry, column: str, sid_prefix: str
) -> list[Statement]:
    statements: list[Statement] = []
    for index, row in enumerate(PLATFORM_TYPES):
        names = {
            "viewer": row.viewer,
            "member": row.viewer + row.member,
            "self": row.self_,
        }[column]
        actions = [
            f"{row.service}:{name}"
            for name in names
            if registry.is_registered(f"{row.service}:{name}")
        ]
        if not actions:
            continue
        statements.append(
            Statement(
                effect="Allow",
                actions=tuple(actions),
                resources=tuple(f"abi:-:-:{row.service}:{r}" for r in row.resources),
                sid=_sid(sid_prefix, row.service, str(index)),
            )
        )
    return statements


def _managed(
    policy_id: str, name: str, description: str, statements: Iterable[Statement]
) -> Policy:
    return Policy(
        id=policy_id,
        name=name,
        description=description,
        document=PolicyDocument(statements=tuple(statements)),
        managed=True,
    )


def _broad(policy_id: str, who: str) -> Policy:
    return _managed(
        policy_id,
        f"{who} (transitional)",
        f"TRANSITIONAL: broad access for the {who} service account until "
        "subtask 11 of #44 enumerates what it needs.",
        [
            Statement(
                effect="Allow",
                actions=("*",),
                resources=("*",),
                sid="TransitionalBroadAccess",
            )
        ],
    )


def idp_policy() -> Policy:
    """The built-in IdP's own namespace, secrets and sender (RFC §12.3)."""
    return _managed(
        IDP,
        "Built-in IdP",
        "The built-in IdP's document namespace, its secrets and its sender.",
        [
            Statement(
                effect="Allow",
                actions=("document:*",),
                resources=(
                    "abi:-:-:document:namespace/idp",
                    "abi:-:-:document:collection/idp/*",
                    "abi:-:-:document:document/idp/*",
                ),
                sid="OwnDocuments",
            ),
            Statement(
                effect="Allow",
                actions=("secret:*",),
                resources=("abi:-:-:secret:secret/idp%2F*",),
                sid="OwnSecrets",
            ),
            Statement(
                effect="Allow",
                actions=("email:Send",),
                resources=("abi:-:-:email:sender/*",),
                sid="SendMail",
            ),
        ],
    )


def module_bootstrap_policy() -> Policy:
    """Held by every module's service account, approved or not (RFC §8.3).

    ``${module.project}`` and ``${module.id}`` come from the account's name,
    ``module/<project>/<module_id>``: the module reaches its own discovery
    record and its own manifest, nothing else, until a manifest is approved.
    """
    return _managed(
        MODULE_BOOTSTRAP,
        "Module bootstrap",
        "What a module's service account holds before and after approval: its "
        "own discovery record and its own permission manifest.",
        [
            Statement(
                effect="Allow",
                actions=(
                    "discovery:Register",
                    "discovery:Renew",
                    "discovery:Unregister",
                    "discovery:GetModule",
                ),
                resources=("abi:-:-:discovery:module/${module.project}/${module.id}",),
                sid="OwnRegistration",
            ),
            Statement(
                effect="Allow",
                actions=("iam:SubmitManifest", "iam:GetManifest"),
                resources=("abi:-:-:iam:manifest/${principal.id}",),
                sid="OwnManifest",
            ),
            # Evicting another module's registration is the platform's, whatever
            # a manifest says.
            Statement(
                effect="Deny",
                actions=("discovery:Evict",),
                resources=("*",),
                sid="NoEviction",
            ),
        ],
    )


# What a Nexus user's side of a Nexus call may reach (TRANSITIONAL, #65).
# Discovery is granted apart (``_transitional_discovery``): never other runs.
_TRANSITIONAL_USER_SERVICES = (
    "activity_log",
    "cache",
    "coding_environment",
    "dataset",
    "document",
    "email",
    "event",
    "keyvalue",
    "model_registry",
    "object_storage",
    "secret",
    "source_control",
    "triple_store",
    "vector_store",
)


def _transitional_discovery() -> list[Statement]:
    """Discovery for a transitional holder: every module, agent, model, app and
    job, but agent runs only its own or those of the user it acts for, so it
    never reads or cancels another principal's run."""
    return [
        Statement(
            effect="Allow",
            actions=("discovery:*",),
            resources=tuple(
                f"abi:-:-:discovery:{type_}/*"
                for type_ in ("module", "agent", "model", "app", "job", "job_run")
            ),
            sid="TransitionalDiscovery",
        ),
        Statement(
            effect="Allow",
            actions=("discovery:*",),
            # Its own runs, and the runs of the user it acts for: an agent run
            # started for a user is that user's (RFC §6.4), and the holder
            # delegating for them must still follow it. ``${user.id}`` matches
            # nothing on a call for no user.
            resources=(
                "abi:-:-:discovery:run/${principal.id}/*",
                "abi:-:-:discovery:run/${user.id}/*",
            ),
            sid="TransitionalOwnRuns",
        ),
    ]


def transitional_nexus_user_policy() -> Policy:
    """TRANSITIONAL (#65 attaches role policies from Nexus memberships, #61
    gives users IAM ids).

    Held implicitly by a user Nexus names on a call (issuer ``urn:abi:nexus``,
    or a Nexus id IAM has no record of): on a Nexus call, ``api`` on behalf of
    that user. Nexus still decides what such a user may do, with its own
    membership checks, so the user side of the intersection (RFC §5.3) allows
    the kernel services a module can declare, plus document and dataset, and
    discovery on the user's own runs only. Never ``iam:*``; seals and explicit
    Denies hold.
    """
    return _managed(
        TRANSITIONAL_NEXUS_USER,
        "Nexus user (transitional)",
        "TRANSITIONAL: a Nexus user's side of a Nexus call until subtask 11 of "
        "#44 attaches the roles of its memberships.",
        [
            Statement(
                effect="Allow",
                actions=tuple(f"{s}:*" for s in _TRANSITIONAL_USER_SERVICES),
                resources=("*",),
                sid="TransitionalNexusUser",
            ),
            *_transitional_discovery(),
        ],
    )


def builtin_policies(registry: CatalogRegistry) -> list[Policy]:
    """Every managed policy, generated from ``registry``."""
    return [
        *(role_policy(role, registry) for role in ROLES),
        _managed(
            PLATFORM_ADMIN,
            "Platform admin",
            "Everything, except sealed resources. Attached without scope.",
            [
                Statement(
                    effect="Allow",
                    actions=("*",),
                    resources=("*",),
                    sid="PlatformAdmin",
                )
            ],
        ),
        _managed(
            SELF,
            "Self",
            "What every user may do on their own principal, keys and records.",
            _platform_statements(registry, "self", "self"),
        ),
        _managed(
            PLATFORM_VIEWER,
            "Platform viewer",
            "Platform-level types a workspace viewer reaches.",
            _platform_statements(registry, "viewer", "platformViewer"),
        ),
        _managed(
            PLATFORM_MEMBER,
            "Platform member",
            "Platform-level types a workspace member reaches.",
            _platform_statements(registry, "member", "platformMember"),
        ),
        _broad(ENGINE, "engine"),
        _broad(API, "api"),
        idp_policy(),
        transitional_nexus_user_policy(),
        module_bootstrap_policy(),
    ]
