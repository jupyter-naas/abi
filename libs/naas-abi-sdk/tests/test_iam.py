import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.iam.v1 import iam_pb2 as pb

from naas_abi_sdk.module import ModuleDependencies, ServicesProxy
from naas_abi_sdk.services import IAMService
from naas_abi_sdk.services.errors import NotFound, PermissionDenied
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
        "actions": [{"name": "GetPerson", "level": "read", "resource_types": ["person"]}],
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
