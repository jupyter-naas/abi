"""Built-in managed policies, generated from the registered catalogs.

Roles are attached at any container: "viewer on workspace W" is ``builtin.viewer``
attached with scope W, the workspace's container name. They are cumulative (viewer ⊆ member ⊆
admin ⊆ owner) and stored with explicit action lists, so ``explain`` shows real
statements. IAM regenerates them whenever a catalog changes.

Also here: ``builtin.engine`` and ``builtin.api``, the two first-party service
accounts, as enumerated statements with a ``sid`` that says what needs each.
Every caller holds only what its policies allow: no principal has implicit
full access.

``builtin.module_bootstrap`` is what every module's service account holds,
approved or not: its own discovery record and its own manifest.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    CatalogRegistry,
    Level,
    PlatformAccess,
)
from naas_abi_core.services.iam.IAMPorts import Policy
from naas_abi_core.services.iam.module_scopes import SERVICE as MODULE_SCOPES
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
JOB = "builtin.job"
MODULE_BOOTSTRAP = "builtin.module_bootstrap"
# Managed policies an older version stored, since removed: IAM drops them (and what
# was attached) at boot, so no grant outlives its definition.
RETIRED_POLICIES = (
    "builtin.transitional.nexus_user",
    "builtin.transitional.module",
)
# The same, by prefix: the policies an older version generated per key from a
# deployment's settings (``builtin.features.*``) and attached beside a role, at
# the role's scope. The last dot-separated segment of the key names that role
# (``builtin.features.org-1.admin`` rode with ``builtin.admin``).
RETIRED_POLICY_PREFIXES = ("builtin.features.",)


def retired_role(policy_id: str) -> str | None:
    """The role a retired companion rode with (``RETIRED_POLICY_PREFIXES``), or
    None for any other policy."""
    prefix = next((p for p in RETIRED_POLICY_PREFIXES if policy_id.startswith(p)), None)
    if prefix is None:
        return None
    role = f"builtin.{policy_id.removeprefix(prefix).rsplit('.', 1)[-1]}"
    return role if role in ROLES else None


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

_ATTACHMENT_TYPE = ("iam", "attachment")
# IAM administration (policies, groups, attachments at the scope) is the
# admins' and owners': viewers and members get nothing of the iam catalog.
_ADMIN_ONLY_SERVICES = frozenset({"iam"})
# IdP group mappings stay the platform admin's: no role maps a claim.
_PLATFORM_ONLY_ACTIONS = frozenset({"iam:MapIdpGroup", "iam:UnmapIdpGroup"})
_MAX_ACTIONS = 100


@dataclass(frozen=True)
class _PlatformRow:
    """A row of the platform types table (``AGENTS.md``, "Built-in policies"): who
    reaches a platform-level type. The kernel services' rows are here; a
    first-party catalog declares its own (``ActionCatalog.platform_access``)."""

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
    # Starting a module's workflow or pipeline (a job of kind ``workflow``, also
    # named ``workflow/…``), as with invoking its agent: the broker's check for a
    # member. Which one is the module scope's (``module:RunWorkflow`` /
    # ``RunPipeline``), which Nexus checks first. A plain job is never a role's.
    _PlatformRow("discovery", ("workflow/*",), member=("TriggerJob",)),
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
    _PlatformRow(
        "iam",
        ("principal/${principal.id}",),
        self_=("GetPrincipal", "RevokeTokens"),
    ),
    _PlatformRow(
        "iam",
        ("key/${principal.id}/*",),
        self_=("ListKeys", "CreateKey", "RevokeKey"),
    ),
    _PlatformRow(
        "object_storage",
        (
            "object/naas_abi/my-drive/${principal.id}",
            "object/naas_abi/my-drive/${principal.id}/*",
            "object/users/${principal.id}",
            "object/users/${principal.id}/*",
            "object/naas_abi/platform-drive",
            "object/naas_abi/platform-drive/*",
        ),
        viewer=(
            "ListObjects",
            "ListObjectsRecursive",
            "GetObject",
            "GetObjectMetadata",
            "GetObjectStream",
        ),
        member=("PutObject", "PutObjectStream", "DeleteObject"),
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
    if catalog.service in _ADMIN_ONLY_SERVICES and role in (VIEWER, MEMBER):
        return []
    placed = [
        t
        for t in catalog.resource_types
        if t.placement == "placed"
        # Granted by a policy only: no role holds it.
        and not t.policy_only
        # Zero trust: no role holds a module scope, owners included; a policy
        # grants each one.
        and not t.module_scope
    ]
    # One statement per kind of resource: what sits in the scope's container
    # (``${scope}/<service>:<type>/*``), a personal type (its owner's), the
    # container itself (``${scope}``: a container type is decided where it is)
    # and making a container in it (its create action).
    groups: dict[str, tuple[list[str], list[str]]] = {
        kind: ([], []) for kind in ("", "personal", "container", "creates")
    }
    for resource_type in placed:
        base = f"${{scope}}/{catalog.service}:{resource_type.name}/"
        for action in catalog.actions:
            if (
                action.level not in levels
                or resource_type.name not in action.resource_types
            ):
                continue
            qualified = catalog.qualified(action.name)
            if qualified in _PLATFORM_ONLY_ACTIONS:
                continue
            if role != OWNER and action.level == "admin":
                if (catalog.service, resource_type.name) == _ATTACHMENT_TYPE:
                    continue
                if action.owner_only:
                    continue
            if resource_type.container:
                kind = "creates" if action.creates else "container"
                patterns = [f"{base}*"] if action.creates else ["${scope}"]
            elif resource_type.personal:
                kind = "personal"
                patterns = [f"{base}${{principal.id}}", f"{base}${{principal.id}}/*"]
            else:
                kind, patterns = "", [f"{base}*"]
            actions, resources = groups[kind]
            if qualified not in actions:
                actions.append(qualified)
            resources += [p for p in patterns if p not in resources]
    statements: list[Statement] = []
    for kind, (actions, resources) in groups.items():
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
                        kind,
                        str(index + 1) if index else "",
                    ),
                )
            )
    return statements


def _admin_attachment_statements(registry: CatalogRegistry) -> list[Statement]:
    """Admins grant and revoke the roles below owner, never owner, and the
    customer policies (``pol_…``) they may attach there: their scope's own, and
    those of the levels above (IAM refuses a policy owned elsewhere)."""
    if registry.get("iam") is None:
        return []
    return [
        Statement(
            effect="Allow",
            actions=("iam:AttachPolicy", "iam:DetachPolicy"),
            resources=tuple(
                f"${{scope}}/iam:attachment/{role}/*"
                for role in (ADMIN, MEMBER, VIEWER)
            ),
            sid="AdminGrantsRolesBelowOwner",
        ),
        Statement(
            effect="Allow",
            actions=("iam:AttachPolicy", "iam:DetachPolicy"),
            resources=("${scope}/iam:attachment/pol_*/*",),
            sid="AdminAttachesCustomerPolicies",
        ),
    ]


def role_policy(role: str, registry: CatalogRegistry) -> Policy:
    statements: list[Statement] = []
    for catalog in registry.all():
        # A catalog whose flags are unknown (stored before they existed) holds
        # nothing for the roles until it is registered again: read as
        # unflagged, its policy-only types and owner-only actions would widen.
        if catalog.flags_known:
            statements += _role_statements(role, catalog)
    if role == ADMIN:
        statements += _admin_attachment_statements(registry)
    return _managed(
        role,
        role.removeprefix("builtin.").capitalize(),
        f"The {role.removeprefix('builtin.')} role, attached at a scope.",
        statements,
    )


def _catalog_rows(registry: CatalogRegistry) -> list[_PlatformRow]:
    """The platform access first-party catalogs declare, as rows of the table."""
    return [
        _platform_row(catalog.service, access)
        for catalog in registry.all()
        if not catalog.module and catalog.flags_known
        for access in catalog.platform_access
    ]


def _platform_row(service: str, access: PlatformAccess) -> _PlatformRow:
    return _PlatformRow(
        service,
        access.resources,
        viewer=access.viewer,
        member=access.member,
        self_=access.self_,
    )


def _platform_statements(
    registry: CatalogRegistry, column: str, sid_prefix: str
) -> list[Statement]:
    statements: list[Statement] = []
    for index, row in enumerate((*PLATFORM_TYPES, *_catalog_rows(registry))):
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
                resources=tuple(f"abi:{row.service}:{r}" for r in row.resources),
                sid=_sid(sid_prefix, row.service, str(index)),
            )
        )
    return statements


@dataclass(frozen=True)
class PlatformGrant:
    """A platform-level resource of the deployment that workspace roles reach by
    level, beyond ``PLATFORM_TYPES``: a viewer the ``list`` and ``read`` actions
    of the resource's type, a member ``write`` too (``resources`` are canonical
    names, ``abi:<service>:<type>/<id>``)."""

    service: str
    resources: tuple[str, ...]
    # False: members read these like viewers do (a shared catalog nobody writes).
    member_writes: bool = True


# The type of a pattern's last literal step, ``.../<service>:<type>/...``.
_LAST_TYPE = re.compile(r"(?:^abi:|/)[a-z][a-z0-9_]*:([a-z][a-z0-9_]*)/")


def _grant_statements(
    registry: CatalogRegistry,
    grants: Sequence[PlatformGrant],
    levels: frozenset[Level],
    sid_prefix: str,
) -> list[Statement]:
    statements: list[Statement] = []
    for index, grant in enumerate(grants):
        catalog = registry.get(grant.service)
        if catalog is None:
            continue
        granted = levels if grant.member_writes else levels & ROLE_LEVELS[VIEWER]
        for resource in grant.resources:
            named = _LAST_TYPE.findall(resource)
            type_name = named[-1] if named else ""
            actions = [
                catalog.qualified(a.name)
                for a in catalog.actions
                if a.level in granted and type_name in a.resource_types
            ]
            if actions:
                statements.append(
                    Statement(
                        effect="Allow",
                        actions=tuple(actions),
                        resources=(resource,),
                        sid=_sid(sid_prefix, grant.service, type_name, str(index)),
                    )
                )
    return statements


# The built-in identity provider's admin app edits who a ``sub`` is (a user's
# email, for one), which is who becomes the platform admin: only the engine
# opens it. ``discovery:OpenApp`` on ``app/*`` comes with every workspace
# viewer and with a module's own bootstrap, so what carries it for the rest
# must also refuse this app, whatever a workspace admin attaches to whom.
_IDP_ADMIN_APP = "abi:discovery:app/*/idp/admin"


def _no_idp_admin_app() -> Statement:
    return Statement(
        effect="Deny",
        actions=("discovery:OpenApp",),
        resources=(_IDP_ADMIN_APP,),
        sid="NoIdpAdminApp",
    )


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


# What the first-party service accounts hold: enumerated statements, each with a ``sid`` that says what needs it.
# Neither holds ``*``: a service Nexus or the engine does not use is reached by
# neither, and the user a Nexus call acts for still bounds every call.
_API_FOR_USERS = (
    ("ObjectStorage", "object_storage", "files and platform storage"),
    ("Documents", "document", "the document service Nexus keeps records in"),
    ("KeyValue", "keyvalue", "system browsing"),
    ("Cache", "cache", "graph query and search caches"),
    ("VectorStore", "vector_store", "chat file ingestion and search"),
    ("TripleStore", "triple_store", "the graph, ontology, views and maps"),
    ("Dataset", "dataset", "datasets"),
    ("Event", "event", "identity and activity events"),
    ("ActivityLog", "activity_log", "the activity log of each request"),
    ("Email", "email", "sign-in and invitation mail"),
    ("ModelRegistry", "model_registry", "chat models and embeddings"),
    ("Discovery", "discovery", "agents, apps, models and jobs of modules"),
    (
        "SourceControl",
        "source_control",
        "repositories of slides, documents, sheets and code",
    ),
    ("CodingEnvironment", "coding_environment", "coding workspaces"),
)
# What the engine does while it boots, runs modules' jobs and schedulers.
_ENGINE_SERVICES = (
    ("ObjectStorage", "object_storage"),
    ("Document", "document"),
    ("KeyValue", "keyvalue"),
    ("Secret", "secret"),
    ("Cache", "cache"),
    ("VectorStore", "vector_store"),
    ("TripleStore", "triple_store"),
    ("Dataset", "dataset"),
    ("Event", "event"),
    ("ActivityLog", "activity_log"),
    ("Email", "email"),
    ("ModelRegistry", "model_registry"),
    ("Discovery", "discovery"),
    ("SourceControl", "source_control"),
    ("CodingEnvironment", "coding_environment"),
    ("Identity", "identity"),
)


def _everything_of(sid: str, service: str) -> Statement:
    return Statement(
        effect="Allow", actions=(f"{service}:*",), resources=("*",), sid=sid
    )


def _module_scope_statements(
    registry: CatalogRegistry | None, sid: str
) -> list[Statement]:
    """Every module scope and every action a module declares (``module_scopes.py``).

    The first-party accounts check them for the user they serve, who bounds the
    call, and run the engine modules' code that enforces them. Generated from
    the registry, so a module's catalog joins them when it registers."""
    if registry is None:
        return []
    services = [
        c.service for c in registry.all() if c.module or c.service == MODULE_SCOPES
    ]
    return [
        Statement(
            effect="Allow", actions=chunk, resources=("*",), sid=_sid(sid, str(i))
        )
        for i, chunk in enumerate(_chunks([f"{s}:*" for s in services]))
    ]


def api_policy(registry: CatalogRegistry | None = None) -> Policy:
    """What Nexus holds as ``api``: its own catalog, the kernel services it calls
    for its users (each user bounds the call), the identity calls of sign-in, and
    the IAM calls that keep memberships, scopes and placements."""
    statements = [
        _everything_of("NexusOwnActions", "nexus"),
        *(
            _everything_of(f"ForUsers{name}", service)
            for name, service, _need in _API_FOR_USERS
        ),
        *_module_scope_statements(registry, "ForUsersModuleScopes"),
        Statement(
            effect="Allow",
            actions=("secret:Get", "secret:Set"),
            resources=("abi:secret:secret/*",),
            sid="ConfiguredSeedCredentials",
        ),
        Statement(
            effect="Allow",
            actions=(
                "identity:ListProviders",
                "identity:GetProvider",
                "identity:SignIn",
                "identity:Authenticate",
                "identity:VerifyToken",
                # Invitations: the provider makes the person the invitation names.
                "identity:ProvisionUser",
                "identity:FindProvisionedUser",
            ),
            resources=("abi:identity:provider/*",),
            sid="SignInThroughProviders",
        ),
        Statement(
            effect="Allow",
            actions=(
                "iam:CreateUser",
                "iam:GetPrincipal",
                "iam:AttachPolicy",
                "iam:DetachPolicy",
                "iam:ListAttachments",
                "iam:PutScope",
                "iam:DeleteScope",
                # The move of the names to container paths, once at start.
                "iam:RewriteNames",
                "iam:PutPlacement",
                "iam:DeletePlacement",
                "iam:ListPlacements",
                # The keys Nexus makes for users (links, coding agents, API keys)
                # and the sessions it ends: the user's side allows them too.
                "iam:CreateKey",
                "iam:ListKeys",
                "iam:RevokeKey",
                "iam:RevokeTokens",
                # A user of the built-in login signing in through the built-in
                # identity provider for the first time keeps its roles (§13).
                "iam:LinkUser",
            ),
            resources=("*",),
            sid="MembershipsScopesPlacementsAndKeys",
        ),
        # A session for a user an identity provider vouched for, and the
        # delegations Nexus makes for a user (agents, links, coding agents).
        Statement(
            effect="Allow",
            actions=("iam:ExchangeToken",),
            resources=(
                "abi:iam:audience/abi%3Asession",
                "abi:iam:audience/abi%3Adelegated%3A*",
                # A key presented without an audience buys the token of its own
                # (checked again on that audience once the key is read).
                "abi:iam:audience/%2A",
            ),
            sid="ExchangeTokensForUsers",
        ),
        # A workspace shares graphs with others as policies Nexus keeps itself.
        Statement(
            effect="Allow",
            actions=(
                "iam:CreatePolicy",
                "iam:UpdatePolicy",
                "iam:DeletePolicy",
                "iam:GetPolicy",
                "iam:ListPolicies",
            ),
            resources=("*",),
            sid="SharedGraphPolicies",
        ),
        # Unchecked dataset SQL reads files on the engine host: never Nexus's.
        Statement(
            effect="Deny",
            actions=("dataset:QueryUnchecked",),
            resources=("*",),
            sid="NoUncheckedSql",
        ),
    ]
    return _managed(
        API,
        "Nexus API",
        "What Nexus holds as the api service account: the user a call acts for "
        "still bounds each call.",
        statements,
    )


def engine_policy(registry: CatalogRegistry | None = None) -> Policy:
    """What the engine holds: IAM's administration (catalogs, placements, service
    accounts, manifests), and the kernel services it uses to boot, run its
    modules' jobs and schedulers."""
    statements = [
        _everything_of("IamAdministration", "iam"),
        *(
            _everything_of(f"Engine{name}", service)
            for name, service in _ENGINE_SERVICES
        ),
        *_module_scope_statements(registry, "EngineModuleScopes"),
    ]
    return _managed(
        ENGINE,
        "Engine",
        "What the engine process holds: boot, module jobs and schedulers.",
        statements,
    )


# What a module's engine-hosted jobs reach: the kernel services a maintenance or
# batch job works with. Never IAM, the identity providers or the sign-in.
_JOB_SERVICES = tuple(
    service
    for _name, service in _ENGINE_SERVICES
    if service not in ("identity", "secret")
)


def job_account_name(module_id: str) -> str:
    """The service account the jobs of an engine module run as."""
    return f"job/{module_id}"


def job_policy(registry: CatalogRegistry | None = None) -> Policy:
    """Held by the account of each engine module's jobs (``job/<module_id>``): the
    kernel services a job works with, read access to secrets (sealed ones stay
    the engine's), and the module scopes a run for a user checks (the user
    bounds them)."""
    statements = [
        *(
            _everything_of(f"Job{name}", service)
            for name, service in _ENGINE_SERVICES
            if service in _JOB_SERVICES
        ),
        Statement(
            effect="Allow",
            actions=("secret:Get", "secret:List"),
            resources=("*",),
            sid="JobReadsSecrets",
        ),
        *_module_scope_statements(registry, "JobModuleScopes"),
    ]
    return _managed(
        JOB,
        "Engine job",
        "What the account of an engine module's jobs holds.",
        statements,
    )


def idp_policy() -> Policy:
    """The built-in IdP's own namespace, secrets and sender."""
    return _managed(
        IDP,
        "Built-in IdP",
        "The built-in IdP's document namespace, its secrets and its sender.",
        [
            Statement(
                effect="Allow",
                actions=("document:*",),
                resources=(
                    "abi:document:namespace/idp",
                    "abi:document:collection/idp/*",
                    "abi:document:document/idp/*",
                ),
                sid="OwnDocuments",
            ),
            Statement(
                effect="Allow",
                actions=("secret:*",),
                resources=("abi:secret:secret/idp%2F*",),
                sid="OwnSecrets",
            ),
            Statement(
                effect="Allow",
                actions=("email:Send",),
                resources=("abi:email:sender/*",),
                sid="SendMail",
            ),
        ],
    )


# The statements of ``builtin.module_bootstrap`` that exist only so the module's
# own side of a delegation allows what it hosts. They open no broker subject:
# the broker turns an InvokeAgent grant into every agent subject of the
# project, and a module is not to call the agents of others.
DELEGATION_SIDS = ("OwnHosted", "OwnRuns")


def module_bootstrap_policy() -> Policy:
    """Held by every module's service account, approved or not.

    ``${module.project}`` and ``${module.id}`` come from the account's name,
    ``module/<project>/<module_id>``: the module reaches its own discovery
    record and its own manifest, and serves what it hosts for a user (the
    actor side of a delegation), nothing else, until a manifest is approved.
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
                resources=("abi:discovery:module/${module.project}/${module.id}",),
                sid="OwnRegistration",
            ),
            # ``default``, which the SDK uses when a module names none and
            # which modules share, is a module's only dataset namespace until
            # a module's approved manifest names its own. Not ``${principal.id}``: a module named by a
            # plain identifier (dev ``sales``) would own a real namespace other
            # principals use. The catalog's snapshots come with it.
            Statement(
                effect="Allow",
                actions=("iam:SubmitManifest", "iam:GetManifest"),
                resources=("abi:iam:manifest/${principal.id}",),
                sid="OwnManifest",
            ),
            # Nexus calls a module's agent, app or model with a delegation that
            # names the module as the actor and the user it acts for:
            # the call is allowed only if the module's own side allows it too,
            # so a module may serve what it hosts. Never another module's, and
            # nothing a user could not do: the user's policy decides as well.
            Statement(
                effect="Allow",
                actions=(
                    "discovery:InvokeAgent",
                    "discovery:OpenApp",
                    "discovery:ChatModel",
                ),
                resources=(
                    "abi:discovery:agent/${module.project}/${module.id}/*",
                    "abi:discovery:app/${module.project}/${module.id}/*",
                    "abi:discovery:model/${module.project}/${module.id}/*",
                ),
                sid="OwnHosted",
            ),
            # The runs of its project that belong to the user it acts for
            # (``${user.id}`` matches nothing on a call for no user: acting
            # alone it reaches its own runs only, by the default manifest).
            Statement(
                effect="Allow",
                actions=("discovery:GetAgentRun", "discovery:CancelAgentRun"),
                resources=("abi:discovery:run/${user.id}/${module.project}/*",),
                sid="OwnRuns",
            ),
            # Evicting another module's registration is the platform's, whatever
            # a manifest says.
            Statement(
                effect="Deny",
                actions=("discovery:Evict",),
                resources=("*",),
                sid="NoEviction",
            ),
            _no_idp_admin_app(),
        ],
    )


def builtin_policies(
    registry: CatalogRegistry, platform_grants: Sequence[PlatformGrant] = ()
) -> list[Policy]:
    """Every managed policy, generated from ``registry``; ``platform_grants`` add
    the deployment's own platform-level resources to the platform policies."""
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
            [
                *_platform_statements(registry, "viewer", "platformViewer"),
                _no_idp_admin_app(),
                *_grant_statements(
                    registry, platform_grants, ROLE_LEVELS[VIEWER], "grantViewer"
                ),
            ],
        ),
        _managed(
            PLATFORM_MEMBER,
            "Platform member",
            "Platform-level types a workspace member reaches.",
            [
                *_platform_statements(registry, "member", "platformMember"),
                _no_idp_admin_app(),
                *_grant_statements(
                    registry, platform_grants, ROLE_LEVELS[MEMBER], "grantMember"
                ),
            ],
        ),
        engine_policy(registry),
        api_policy(registry),
        job_policy(registry),
        idp_policy(),
        module_bootstrap_policy(),
    ]
