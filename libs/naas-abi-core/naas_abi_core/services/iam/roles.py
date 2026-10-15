"""Built-in managed policies (RFC §7), generated from the registered catalogs.

Roles are attached at a scope: "viewer on workspace W" is ``builtin.viewer``
attached with scope ``abi:<org>:W``. They are cumulative (viewer ⊆ member ⊆
admin ⊆ owner) and stored with explicit action lists, so ``explain`` shows real
statements. IAM regenerates them whenever a catalog changes.

Also here, and named so: the TRANSITIONAL policies that keep every caller
working before the later subtasks of #44 land.

* ``builtin.engine`` and ``builtin.api`` are one broad statement each
  (``TransitionalBroadAccess``). Subtask 11 (#65) replaces them with enumerated
  statements.
* ``builtin.transitional.module`` is what a remote module's service account
  holds until subtask 6 (#60) gives it an approved manifest: its own document
  and dataset namespaces, and the kernel services a module can declare.
* ``builtin.transitional.nexus_user`` is what a Nexus user holds until
  subtask 11 (#65) attaches the roles of its memberships: Nexus still decides
  what such a user may do, as before IAM.

Neither transitional grant reaches another principal's agent runs: discovery
is granted on its modules, agents, models, apps and jobs, and on the holder's
own runs only (``run/${principal.id}/*``).
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
TRANSITIONAL_MODULE = "builtin.transitional.module"
TRANSITIONAL_NEXUS_USER = "builtin.transitional.nexus_user"

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

# What a remote module may declare before manifests (TRANSITIONAL, #60).
# Discovery is granted apart (``_transitional_discovery``): never other runs.
_TRANSITIONAL_MODULE_SERVICES = (
    "activity_log",
    "cache",
    "coding_environment",
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


def transitional_module_policy() -> Policy:
    """TRANSITIONAL (#60 replaces it with approved manifests).

    Held implicitly by every service account IAM has no record of: today, the
    remote modules, whose token names their module. The engine does not see a
    remote module's declared services before manifests, so it gets the kernel
    services a module can declare, and only its own namespaces in document and
    dataset (``${principal.id}`` is the module's name until #60).
    """
    return _managed(
        TRANSITIONAL_MODULE,
        "Remote module (transitional)",
        "TRANSITIONAL: a remote module's access until subtask 6 of #44 "
        "approves its permission manifest.",
        [
            Statement(
                effect="Allow",
                actions=("document:*",),
                resources=(
                    "abi:-:-:document:namespace/${principal.id}",
                    "abi:-:-:document:collection/${principal.id}/*",
                    "abi:-:-:document:document/${principal.id}/*",
                ),
                sid="TransitionalOwnDocuments",
            ),
            Statement(
                effect="Allow",
                actions=("dataset:*",),
                resources=(
                    "abi:-:-:dataset:namespace/${principal.id}",
                    "abi:-:-:dataset:dataset/${principal.id}/*",
                ),
                sid="TransitionalOwnDatasets",
            ),
            Statement(
                effect="Allow",
                actions=tuple(f"{s}:*" for s in _TRANSITIONAL_MODULE_SERVICES),
                resources=("*",),
                sid="TransitionalKernelServices",
            ),
            *_transitional_discovery(),
            # Evicting another module's registration is the platform's.
            Statement(
                effect="Deny",
                actions=("discovery:Evict",),
                resources=("*",),
                sid="TransitionalNoEviction",
            ),
        ],
    )


def _transitional_discovery() -> list[Statement]:
    """Discovery for a transitional holder: every module, agent, model, app and
    job, but only its own agent runs, so it never reads or cancels another
    principal's run."""
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
            resources=("abi:-:-:discovery:run/${principal.id}/*",),
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
                actions=tuple(
                    f"{s}:*"
                    for s in sorted(
                        {*_TRANSITIONAL_MODULE_SERVICES, "dataset", "document"}
                    )
                ),
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
        transitional_module_policy(),
        transitional_nexus_user_policy(),
    ]
