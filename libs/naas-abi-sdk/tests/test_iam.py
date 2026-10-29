import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.iam.v1 import iam_pb2 as pb

from naas_abi_sdk.module import ModuleDependencies, ServicesProxy
from naas_abi_sdk.services import IAMService
from naas_abi_sdk.services.errors import GrantNotHeld, NotFound, PermissionDenied
from naas_abi_sdk.transport import RPCError

WORKSPACE = "abi:nexus:organization/org-1/nexus:workspace/ws-1"


def run(coro):
    return asyncio.run(coro)


def test_decisions_convert_to_python_values():
    client = AsyncMock()
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=False, visible=True, reason="implicit_deny")
    )
    client.filter.return_value = pb.FilterResponse(
        allowed=["abi:svc:t/a"], prefix_hints=["abi:svc:t/"]
    )
    iam = IAMService(client)

    decision = run(iam.authorize("svc:Get", "abi:svc:t/a"))
    assert (decision.allowed, decision.visible, decision.reason) == (
        False,
        True,
        "implicit_deny",
    )
    request = client.authorize.call_args.args[0]
    assert (request.action, request.resource) == ("svc:Get", "abi:svc:t/a")
    result = run(iam.filter("svc:List", ["abi:svc:t/a", "abi:svc:t/b"]))
    assert result.allowed == ["abi:svc:t/a"]
    assert result.prefix_hints == ["abi:svc:t/"]


def test_require_tells_denied_from_not_found():
    client = AsyncMock()
    iam = IAMService(client)
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=False, visible=True, reason="implicit_deny")
    )
    with pytest.raises(PermissionDenied):
        run(iam.require("svc:Put", "abi:svc:t/a"))
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=False, visible=False, reason="implicit_deny")
    )
    with pytest.raises(NotFound):
        run(iam.require("svc:Put", "abi:svc:t/a"))
    with pytest.raises(KeyError):
        run(iam.require("svc:Put", "abi:svc:t/a", not_found=lambda: KeyError("a")))
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=True, visible=True, reason="allow")
    )
    run(iam.require("svc:Put", "abi:svc:t/a"))


def test_policies_carry_their_document_as_a_mapping():
    document = {
        "version": "2026-10-13",
        "statements": [{"effect": "Allow", "actions": ["*"], "resources": ["*"]}],
    }
    client = AsyncMock()
    client.create_policy.return_value = pb.CreatePolicyResponse(
        policy=pb.Policy(
            id="pol_1", name="all", document_json=json.dumps(document), revision=1
        )
    )
    policy = run(IAMService(client).create_policy("all", document))
    assert policy["document"] == document and policy["revision"] == 1
    sent = client.create_policy.call_args.args[0]
    assert json.loads(sent.document_json) == document


def test_a_sub_policy_names_its_parent_and_is_listed_under_it():
    document = {
        "version": "2026-10-13",
        "statements": [{"effect": "Allow", "actions": ["*"], "resources": ["*"]}],
    }
    record = pb.Policy(
        id="pol_s",
        name="sub",
        document_json=json.dumps(document),
        revision=1,
        parent_id="pol_p",
    )
    client = AsyncMock()
    client.create_policy.return_value = pb.CreatePolicyResponse(policy=record)
    client.update_policy.return_value = pb.UpdatePolicyResponse(
        policy=pb.Policy(id="pol_s", document_json=json.dumps(document), revision=2)
    )
    client.list_sub_policies.return_value = pb.ListSubPoliciesResponse(
        policies=[record]
    )
    iam = IAMService(client)
    created = run(iam.create_policy("sub", document, parent="pol_p"))
    assert created["parent_id"] == "pol_p"
    assert client.create_policy.call_args.args[0].parent == "pol_p"
    # "" removes the parent; None, the default, keeps it (unset on the wire).
    freed = run(iam.update_policy("pol_s", expected_revision=1, parent=""))
    assert freed["parent_id"] is None
    sent = client.update_policy.call_args.args[0]
    assert sent.HasField("parent") and sent.parent == ""
    run(iam.update_policy("pol_s", expected_revision=2, name="kept"))
    assert not client.update_policy.call_args.args[0].HasField("parent")
    listed = run(iam.list_sub_policies("pol_p"))
    assert [p["id"] for p in listed] == ["pol_s"]
    assert client.list_sub_policies.call_args.args[0].policy_id == "pol_p"


def test_wire_errors_become_portable_exceptions():
    client = AsyncMock()
    client.get_principal.side_effect = RPCError("NOT_FOUND", "Principal x not found")
    with pytest.raises(NotFound):
        run(IAMService(client).get_principal("x"))
    client.get_principal.side_effect = RPCError(
        "PERMISSION_DENIED",
        "no",
        response=pb.GetPrincipalResponse(
            error=common_pb2.CallError(code="PERMISSION_DENIED", message="no")
        ),
    )
    with pytest.raises(PermissionError):
        run(IAMService(client).get_principal("x"))


def test_catalogs_register_from_the_rfc_format():
    client = AsyncMock()
    client.register_catalog.return_value = pb.RegisterCatalogResponse(registered=True)
    catalog = {
        "service": "people",
        "version": 1,
        "resource_types": [{"name": "person", "id": "opaque", "placement": "placed"}],
        "actions": [
            {"name": "GetPerson", "level": "read", "resource_types": ["person"]}
        ],
    }
    assert run(IAMService(client).register_catalog(catalog)) is True
    sent = client.register_catalog.call_args.args[0].catalog
    assert sent.service == "people" and sent.actions[0].resource_types == ["person"]


def test_iam_needs_no_dependency_declaration():
    client = AsyncMock()
    services = ServicesProxy(client, ModuleDependencies(services=("kv",)), "demo")
    assert services.iam_available()
    assert isinstance(services.iam, IAMService)
    with pytest.raises(ValueError):
        services.document  # noqa: B018 - undeclared services stay closed


def test_every_iam_operation_has_a_facade_method():
    from naas_abi_sdk.catalog import OPERATIONS

    missing = [op for op in OPERATIONS["iam"] if not hasattr(IAMService, op)]
    assert missing == []


def test_listing_mappings_and_placements():
    client = AsyncMock()
    client.list_idp_group_mappings.return_value = pb.ListIdpGroupMappingsResponse(
        mappings=[pb.GroupMapping(provider="acme", claim_value="Sales", group_id="g")]
    )
    client.list_placements.return_value = pb.ListPlacementsResponse(
        placements=[pb.Placement(service="document", id_key="n/*", container=WORKSPACE)]
    )
    client.put_placement.return_value = pb.PutPlacementResponse(
        placement=pb.Placement(service="document", id_key="n", container=WORKSPACE)
    )
    iam = IAMService(client)
    assert run(iam.list_idp_group_mappings("g")) == [
        {"provider": "acme", "claim_value": "Sales", "group_id": "g"}
    ]
    found = run(iam.list_placements("document"))[0]
    assert (found["id_key"], found["container"]) == ("n/*", WORKSPACE)
    run(iam.put_placement("document", "n", WORKSPACE))
    sent = client.put_placement.call_args.args[0].placement
    assert (sent.service, sent.id_key, sent.container) == ("document", "n", WORKSPACE)


def test_registering_reading_and_deleting_containers():
    client = AsyncMock()
    client.register_container.return_value = pb.RegisterContainerResponse(
        container=pb.Container(
            service="acme_crm",
            type="project",
            id="p-9",
            parent=WORKSPACE,
            name=f"{WORKSPACE}/acme_crm:project/p-9",
        )
    )
    client.get_container.return_value = pb.GetContainerResponse(
        name=f"{WORKSPACE}/acme_crm:project/p-9"
    )
    client.delete_container.return_value = pb.DeleteContainerResponse(deleted=True)
    iam = IAMService(client)

    record = run(iam.register_container("acme_crm", "project", "p-9", parent=WORKSPACE))
    assert record["name"] == f"{WORKSPACE}/acme_crm:project/p-9"
    sent = client.register_container.call_args.args[0]
    assert (sent.service, sent.type, sent.id, sent.parent) == (
        "acme_crm",
        "project",
        "p-9",
        WORKSPACE,
    )
    run(iam.register_container("acme_crm", "project", "p-1"))
    assert client.register_container.call_args.args[0].parent == "abi:"
    assert run(iam.get_container("acme_crm", "project", "p-9")) == (
        f"{WORKSPACE}/acme_crm:project/p-9"
    )
    client.get_container.return_value = pb.GetContainerResponse(name="")
    assert run(iam.get_container("acme_crm", "project", "nope")) is None
    assert run(iam.delete_container("acme_crm", "project", "p-9")) is True
    assert not hasattr(iam, "put_scope") and not hasattr(iam, "delete_scope")


def test_a_declared_action_is_named_by_iam_and_required():
    client = AsyncMock()
    client.authorize_declared.return_value = pb.AuthorizeDeclaredResponse(
        decision=pb.Decision(allowed=False, visible=False, reason="implicit_deny"),
        resource=f"{WORKSPACE}/acme_reports:report/q3",
    )
    iam = IAMService(client)
    decision, resource = run(
        iam.authorize_declared("acme_reports:ExportReport", "report", ["q3"])
    )
    assert not decision.allowed
    assert resource == f"{WORKSPACE}/acme_reports:report/q3"
    request = client.authorize_declared.call_args.args[0]
    assert (request.action, request.resource_type, list(request.parts)) == (
        "acme_reports:ExportReport",
        "report",
        ["q3"],
    )
    assert request.container == ""
    with pytest.raises(NotFound):
        run(iam.require_declared("acme_reports:ExportReport", "report", ["q3"]))
    client.authorize_declared.return_value = pb.AuthorizeDeclaredResponse(
        decision=pb.Decision(allowed=True, visible=True, reason="allow")
    )
    run(
        iam.require_declared(
            "acme_reports:ExportReport", "report", ["q3"], container=WORKSPACE
        )
    )
    assert client.authorize_declared.call_args.args[0].container == WORKSPACE


def test_a_module_requires_its_own_actions_by_name():
    from naas_abi_sdk.module import BaseModule

    class Reports(BaseModule):
        module_id = "acme.reports"
        iam_catalog = {
            "resource_types": [{"name": "report"}],
            "actions": [
                {"name": "ExportReport", "level": "read", "resource_types": ["report"]}
            ],
        }

    module = Reports.__new__(Reports)
    iam = AsyncMock()

    class Engine:
        class services:
            pass

    Engine.services.iam = iam
    module._engine = Engine
    run(module.require_action("ExportReport", "report", "q3"))
    iam.require_declared.assert_awaited_once_with(
        "acme_reports:ExportReport", "report", ["q3"], container=None
    )


def test_what_may_be_granted_and_its_refusal():
    client = AsyncMock()
    client.grantable.return_value = pb.GrantableResponse(
        catalogs=[
            pb.GrantableCatalog(
                service="triple_store",
                actions=[
                    pb.GrantableAction(
                        action="triple_store:Query",
                        resources=["${scope}/triple_store:graph/*"],
                        excluded=["${scope}/triple_store:graph/hr*"],
                    )
                ],
            )
        ]
    )
    found = run(IAMService(client).grantable(WORKSPACE))
    assert found == [
        {
            "service": "triple_store",
            "actions": [
                {
                    "action": "triple_store:Query",
                    "resources": ["${scope}/triple_store:graph/*"],
                    "excluded": ["${scope}/triple_store:graph/hr*"],
                }
            ],
        }
    ]
    assert client.grantable.call_args.args[0].scope == WORKSPACE
    assert client.grantable.call_args.args[0].parent == ""
    # Within a parent: what a sub-policy of it may grant.
    run(IAMService(client).grantable(WORKSPACE, parent="pol_parent"))
    assert client.grantable.call_args.args[0].parent == "pol_parent"
    assert client.grantable.call_args.args[0].derive is False
    # For a new one: refused as create_policy would refuse the parent.
    run(IAMService(client).grantable(WORKSPACE, parent="pol_parent", derive=True))
    assert client.grantable.call_args.args[0].derive is True
    client.attach_policy.side_effect = RPCError(
        "GRANT_NOT_HELD", "You cannot grant what you do not hold: ..."
    )
    with pytest.raises(GrantNotHeld) as refused:
        run(IAMService(client).attach_policy("builtin.owner", "usr_x", WORKSPACE))
    assert isinstance(refused.value, PermissionDenied)
    assert "do not hold" in str(refused.value)
    # The code is said once.
    assert str(refused.value) == (
        "GRANT_NOT_HELD: You cannot grant what you do not hold: ..."
    )


def test_a_listing_of_what_the_caller_may_list():
    client = AsyncMock()
    client.list_resources.return_value = pb.ListResourcesResponse(
        items=[
            pb.ListedResource(
                name=f"{WORKSPACE}/triple_store:graph/g1", id="g1", label="Sales"
            )
        ],
        next_cursor="",
        listed=True,
    )
    found = run(
        IAMService(client).list_resources(
            "triple_store", "graph", scope=WORKSPACE, text="sa", limit=10
        )
    )
    assert found == {
        "items": [
            {
                "name": f"{WORKSPACE}/triple_store:graph/g1",
                "id": "g1",
                "label": "Sales",
                "description": "",
            }
        ],
        "next_cursor": None,
        "listed": True,
    }
    request = client.list_resources.call_args.args[0]
    assert (request.service, request.type, request.scope, request.text, request.limit) == (
        "triple_store",
        "graph",
        WORKSPACE,
        "sa",
        10,
    )
