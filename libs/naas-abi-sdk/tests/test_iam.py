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


def run(coro):
    return asyncio.run(coro)


def test_decisions_convert_to_python_values():
    client = AsyncMock()
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=False, visible=True, reason="implicit_deny")
    )
    client.filter.return_value = pb.FilterResponse(
        allowed=["abi:-:-:svc:t/a"], prefix_hints=["abi:-:-:svc:t/"]
    )
    iam = IAMService(client)

    decision = run(iam.authorize("svc:Get", "abi:-:-:svc:t/a"))
    assert (decision.allowed, decision.visible, decision.reason) == (
        False,
        True,
        "implicit_deny",
    )
    request = client.authorize.call_args.args[0]
    assert (request.action, request.resource) == ("svc:Get", "abi:-:-:svc:t/a")
    result = run(iam.filter("svc:List", ["abi:-:-:svc:t/a", "abi:-:-:svc:t/b"]))
    assert result.allowed == ["abi:-:-:svc:t/a"]
    assert result.prefix_hints == ["abi:-:-:svc:t/"]


def test_require_tells_denied_from_not_found():
    client = AsyncMock()
    iam = IAMService(client)
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=False, visible=True, reason="implicit_deny")
    )
    with pytest.raises(PermissionDenied):
        run(iam.require("svc:Put", "abi:-:-:svc:t/a"))
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=False, visible=False, reason="implicit_deny")
    )
    with pytest.raises(NotFound):
        run(iam.require("svc:Put", "abi:-:-:svc:t/a"))
    with pytest.raises(KeyError):
        run(iam.require("svc:Put", "abi:-:-:svc:t/a", not_found=lambda: KeyError("a")))
    client.authorize.return_value = pb.AuthorizeResponse(
        decision=pb.Decision(allowed=True, visible=True, reason="allow")
    )
    run(iam.require("svc:Put", "abi:-:-:svc:t/a"))


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


def test_listing_mappings_and_placements_and_deleting_scopes():
    client = AsyncMock()
    client.list_idp_group_mappings.return_value = pb.ListIdpGroupMappingsResponse(
        mappings=[pb.GroupMapping(provider="acme", claim_value="Sales", group_id="g")]
    )
    client.list_placements.return_value = pb.ListPlacementsResponse(
        placements=[
            pb.Placement(service="document", id_key="n/*", org="o", workspace="w")
        ]
    )
    client.delete_scope.return_value = pb.DeleteScopeResponse(deleted=True)
    iam = IAMService(client)
    assert run(iam.list_idp_group_mappings("g")) == [
        {"provider": "acme", "claim_value": "Sales", "group_id": "g"}
    ]
    assert run(iam.list_placements("document"))[0]["id_key"] == "n/*"
    assert run(iam.delete_scope("o", "w")) is True


def test_what_may_be_granted_and_its_refusal():
    client = AsyncMock()
    client.grantable.return_value = pb.GrantableResponse(
        catalogs=[
            pb.GrantableCatalog(
                service="triple_store",
                actions=[
                    pb.GrantableAction(
                        action="triple_store:Query",
                        resources=["${scope}:triple_store:graph/*"],
                        excluded=["${scope}:triple_store:graph/hr*"],
                    )
                ],
            )
        ]
    )
    found = run(IAMService(client).grantable("abi:org-1:ws-1"))
    assert found == [
        {
            "service": "triple_store",
            "actions": [
                {
                    "action": "triple_store:Query",
                    "resources": ["${scope}:triple_store:graph/*"],
                    "excluded": ["${scope}:triple_store:graph/hr*"],
                }
            ],
        }
    ]
    assert client.grantable.call_args.args[0].scope == "abi:org-1:ws-1"
    client.attach_policy.side_effect = RPCError(
        "GRANT_NOT_HELD", "You cannot grant what you do not hold: ..."
    )
    with pytest.raises(GrantNotHeld) as refused:
        run(IAMService(client).attach_policy("builtin.owner", "usr_x", "abi:o:w"))
    assert isinstance(refused.value, PermissionDenied)
    assert "do not hold" in str(refused.value)
