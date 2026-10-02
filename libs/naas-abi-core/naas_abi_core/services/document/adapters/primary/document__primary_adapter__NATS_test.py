import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_proto.document.v1 import document_pb2 as pb

SECRET = "document-primary-test-secret-32-bytes"


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
        headers={"Nats-Auth-Token": issue_service_token("test", SECRET)}
        if authenticated
        else {},
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
        headers={"Nats-Auth-Token": issue_service_token(identity, SECRET)},
        respond=AsyncMock(),
    )


def test_platform_identities_list_namespaces():
    service = Mock()
    service.namespaces.return_value = ["acme.module", "naas_abi"]
    primary = DocumentPrimaryAdapterNATS(service, SECRET)
    request = _namespaces_request("api")
    try:
        asyncio.run(primary._handle(request, operation="namespaces"))
        response = pb.NamespacesResponse.FromString(request.respond.call_args.args[0])
        assert not response.HasField("error")
        assert list(response.namespaces) == ["acme.module", "naas_abi"]
    finally:
        primary._dispatch.close()


@pytest.mark.parametrize("identity", ["acme.module", "dagster", "test"])
def test_other_identities_cannot_list_namespaces(identity):
    service = Mock()
    primary = DocumentPrimaryAdapterNATS(service, SECRET)
    request = _namespaces_request(identity)
    try:
        asyncio.run(primary._handle(request, operation="namespaces"))
        response = pb.NamespacesResponse.FromString(request.respond.call_args.args[0])
        assert response.error.code == "PERMISSION_DENIED"
        assert not response.error.retryable
        service.namespaces.assert_not_called()
    finally:
        primary._dispatch.close()


def test_admin_identities_are_configurable():
    service = Mock()
    service.namespaces.return_value = []
    primary = DocumentPrimaryAdapterNATS(service, SECRET, admin_identities={"ops"})
    allowed, denied = _namespaces_request("ops"), _namespaces_request("api")
    try:
        asyncio.run(primary._handle(allowed, operation="namespaces"))
        asyncio.run(primary._handle(denied, operation="namespaces"))
        assert not pb.NamespacesResponse.FromString(
            allowed.respond.call_args.args[0]
        ).HasField("error")
        assert (
            pb.NamespacesResponse.FromString(
                denied.respond.call_args.args[0]
            ).error.code
            == "PERMISSION_DENIED"
        )
    finally:
        primary._dispatch.close()


def test_backend_error_is_not_leaked_or_retried():
    service = Mock()
    service._for_namespace.return_value.get.side_effect = RuntimeError(
        "sensitive connection details"
    )
    primary = DocumentPrimaryAdapterNATS(service, SECRET)
    request = SimpleNamespace(
        data=pb.GetRequest(
            namespace="module", collection="state", id="one"
        ).SerializeToString(),
        headers={"Nats-Auth-Token": issue_service_token("test", SECRET)},
        respond=AsyncMock(),
    )
    try:
        asyncio.run(primary._handle(request, operation="get"))
        response = pb.GetResponse.FromString(request.respond.call_args.args[0])
        assert response.error.code == "INTERNAL"
        assert "sensitive" not in response.error.message
        assert not response.error.retryable
        service._for_namespace.return_value.get.assert_called_once()
    finally:
        primary._dispatch.close()
