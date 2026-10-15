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


def graph(name: str, org: str = "org-1", workspace: str = "ws-1") -> str:
    return f"abi:{org}:{workspace}:triple_store:graph/{name}"


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
