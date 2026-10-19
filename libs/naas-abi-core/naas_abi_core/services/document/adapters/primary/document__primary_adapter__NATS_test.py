import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_proto.document.v1 import document_pb2 as pb

SECRET = TEST_TOKENS.verifier


@pytest.mark.parametrize(
    "authenticated, payload, code",
    [
        (
            False,
            pb.GetRequest(
                namespace="module", collection="state", id="one"
            ).SerializeToString(),
            "UNAUTHENTICATED",
        ),
        (True, b"\xff", "INVALID_ARGUMENT"),
    ],
)
def test_invalid_requests_never_reach_service(authenticated, payload, code):
    service = Mock()
    primary = DocumentPrimaryAdapterNATS(service, SECRET)
    request = SimpleNamespace(
        data=payload,
        headers={"Nats-Auth-Token": TEST_TOKENS.token("test")} if authenticated else {},
        respond=AsyncMock(),
    )
    asyncio.run(primary._handle(request, operation="get"))
    response = pb.GetResponse.FromString(request.respond.call_args.args[0])
    assert response.error.code == code
    service._for_namespace.assert_not_called()
    primary._dispatch.close()


def _namespaces_request(identity):
    return SimpleNamespace(
        data=pb.NamespacesRequest().SerializeToString(),
        headers={"Nats-Auth-Token": TEST_TOKENS.token(identity)},
        respond=AsyncMock(),
    )


@pytest.mark.parametrize("identity", ["api", "acme.module", "dagster"])
def test_every_caller_gets_the_domain_answer(identity):
    # No identity is an administrator by name: the domain service filters.
    service = Mock()
    service.namespaces.return_value = ["acme.module"]
    primary = DocumentPrimaryAdapterNATS(service, SECRET)
    request = _namespaces_request(identity)
    try:
        asyncio.run(primary._handle(request, operation="namespaces"))
        response = pb.NamespacesResponse.FromString(request.respond.call_args.args[0])
        assert not response.HasField("error")
        assert list(response.namespaces) == ["acme.module"]
        service.namespaces.assert_called_once()
    finally:
        primary._dispatch.close()


@pytest.mark.parametrize(
    "error, code",
    [
        (
            PermissionDeniedError("document:Get", "abi:-:-:document:document/a/b/c"),
            "PERMISSION_DENIED",
        ),
        (ResourceNotFoundError("abi:-:-:document:namespace/a"), "NOT_FOUND"),
    ],
)
def test_authorization_outcomes_keep_their_code(error, code):
    service = Mock()
    service._for_namespace.return_value.get.side_effect = error
    primary = DocumentPrimaryAdapterNATS(service, SECRET)
    request = SimpleNamespace(
        data=pb.GetRequest(namespace="a", collection="b", id="c").SerializeToString(),
        headers={"Nats-Auth-Token": TEST_TOKENS.token("acme.module")},
        respond=AsyncMock(),
    )
    try:
        asyncio.run(primary._handle(request, operation="get"))
        response = pb.GetResponse.FromString(request.respond.call_args.args[0])
        assert response.error.code == code
        assert response.error.message == str(error)
    finally:
        primary._dispatch.close()
