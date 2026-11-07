"""IAM test helpers: catalogs, names, and a harness around a bootstrapped service."""

from __future__ import annotations

from contextlib import AbstractContextManager

from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import PrincipalRecord
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.names import PLATFORM, container_name

TRIPLE_STORE = ActionCatalog(
    service="triple_store",
    version=1,
    resource_types=(
        ResourceType("graph", id="opaque"),
        ResourceType("view", id="opaque", placement="platform"),
    ),
    actions=(
        ActionSpec("ListGraphs", "list", ("graph",)),
        ActionSpec("Query", "read", ("graph",)),
        ActionSpec("QueryStream", "read", ("graph",)),
        ActionSpec("Insert", "write", ("graph",)),
        ActionSpec("CreateGraph", "write", ("graph",), creates=True),
        ActionSpec("DropGraph", "admin", ("graph",)),
        ActionSpec("QueryView", "read", ("view",)),
    ),
)

ACTIVITY_LOG = ActionCatalog(
    service="activity_log",
    version=1,
    resource_types=(
        ResourceType("actor", placement="platform", personal=True),
        ResourceType("note", id="path", personal=True),
    ),
    actions=(
        ActionSpec("Query", "read", ("actor",)),
        ActionSpec("ReadNote", "read", ("note",)),
    ),
)


# The containers of the tests: an organisation and its workspaces, declared as
# Nexus declares them. A role at a workspace brings the platform companions.
NEXUS = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(
        ResourceType("organization", container=True),
        ResourceType("workspace", container=True, platform_companions=True),
    ),
    actions=(
        ActionSpec("CreateOrganization", "write", ("organization",), creates=True),
        ActionSpec("GetOrganization", "read", ("organization",)),
        ActionSpec("UpdateOrganization", "admin", ("organization",)),
        ActionSpec(
            "DeleteOrganization",
            "admin",
            ("organization",),
            owner_only=True,
            deletes=True,
        ),
        ActionSpec("CreateWorkspace", "write", ("workspace",), creates=True),
        ActionSpec("GetWorkspace", "read", ("workspace",)),
        ActionSpec("UpdateWorkspace", "admin", ("workspace",)),
        ActionSpec(
            "DeleteWorkspace", "admin", ("workspace",), owner_only=True, deletes=True
        ),
    ),
)


def org(org_id: str = "org-1") -> str:
    """An organisation's container name; ``-`` is the platform."""
    if org_id == "-":
        return PLATFORM
    return container_name("nexus", "organization", org_id)


def workspace(ws: str = "ws-1", org_id: str = "org-1") -> str:
    """A workspace's container name, in ``org_id`` (``-``: at the platform);
    ``ws`` ``-`` is the organisation itself."""
    if ws == "-":
        return org(org_id)
    return container_name("nexus", "workspace", ws, parent=org(org_id))


def below(org_id: str = "org-1") -> str:
    """The scope below an organisation: it and every workspace of it."""
    return org(org_id) + "/*"


def name_in(container: str, rest: str) -> str:
    """``rest`` (``<service>:<type>/<id>``) in ``container``."""
    return f"{PLATFORM}{rest}" if container == PLATFORM else f"{container}/{rest}"


def graph(name: str, org: str = "org-1", workspace: str = "ws-1") -> str:
    """A graph in a workspace (``workspace`` ``-``: in the organisation; ``org``
    ``-``: at the platform). ``name`` is written as is."""
    return name_in(_where(org, workspace), f"triple_store:graph/{name}")


def _where(org_id: str, ws: str) -> str:
    if org_id == "-" and ws == "-":
        return PLATFORM
    return workspace(ws, org_id)


def statement(effect: str, actions: list[str], resources: list[str], sid=None) -> dict:
    data = {"effect": effect, "actions": actions, "resources": resources}
    if sid:
        data["sid"] = sid
    return data


def document(*statements: dict) -> dict:
    return {"version": "2026-10-13", "statements": list(statements)}


class IAMHarness:
    def __init__(self, service: IAMService) -> None:
        self.iam = service

    def user(self, subject: str = "bob", **profile) -> PrincipalRecord:
        with as_service_account("engine"):
            return self.iam.ensure_user("https://idp.example", subject, **profile)

    def service_account(self, name: str) -> PrincipalRecord:
        with as_service_account("engine"):
            return self.iam.create_service_account(name)

    def register(self, ws: str = "ws-1", org_id: str = "org-1") -> str:
        """Register an organisation and a workspace of it (``ws`` ``-``: the
        organisation only; ``org_id`` ``-``: a workspace at the platform), as
        Nexus does with ``api``. Returns the innermost container's name."""
        with as_service_account("api"):
            if org_id != "-":
                self.iam.register_container("nexus", "organization", org_id)
            if ws != "-":
                self.iam.register_container(
                    "nexus", "workspace", ws, parent=org(org_id)
                )
        return workspace(ws, org_id)

    def group(self, name: str = "sales") -> PrincipalRecord:
        with as_service_account("engine"):
            return self.iam.create_group(name)

    def grant(self, principal_id: str, *statements: dict, scope: str | None = None):
        with as_service_account("engine"):
            policy = self.iam.create_policy("test", document(*statements))
            self.iam.attach_policy(policy.id, principal_id, scope)
        return policy

    def attach(self, policy_id: str, principal_id: str, scope: str | None = None):
        with as_service_account("engine"):
            return self.iam.attach_policy(policy_id, principal_id, scope)

    def first_party_may(self, service: str) -> None:
        """Let the engine and api reach a test service the built-in policies do not
        name (they name the kernel services, and api Nexus's catalog)."""
        for name in ("engine", "api"):
            account = self.iam.store.find_service_account(name)
            assert account is not None
            self.grant(account.id, statement("Allow", [f"{service}:*"], ["*"]))

    def admin(self, method: str, *args, **kwargs):
        with as_service_account("engine"):
            return getattr(self.iam, method)(*args, **kwargs)

    @staticmethod
    def context(
        record: PrincipalRecord | None = None,
        *,
        on_behalf_of: PrincipalRecord | None = None,
        actor: str | None = None,
        groups: frozenset[str] = frozenset(),
        scope=None,
    ) -> CallContext:
        if actor is not None:
            principal = Principal(id=actor, kind="service_account", name=actor)
        else:
            assert record is not None
            principal = Principal(
                id=record.id,
                kind=record.kind,  # type: ignore[arg-type]  # users and accounts only
                name=record.name,
                groups=groups,
            )
        obo = (
            Principal(id=on_behalf_of.id, kind="user", groups=groups)
            if on_behalf_of is not None
            else None
        )
        return CallContext(principal=principal, on_behalf_of=obo, scope=scope)

    def as_(self, record=None, **kwargs) -> AbstractContextManager[CallContext]:
        return use_call_context(self.context(record, **kwargs))

    def allowed(self, action: str, resource: str, record=None, **kwargs) -> bool:
        with self.as_(record, **kwargs):
            return self.iam.authorize(action, resource).allowed
