import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.iam.v1 import iam_pb2 as pb

from naas_abi_sdk.credentials import ServiceKey, module_account
from naas_abi_sdk.module import BaseModule, ModuleDependencies, _await_approval
from naas_abi_sdk.transport import RPCError, Transport

KEY = "abi_sk_abcdefghijklmnop_c2VjcmV0LXNlY3JldC1zZWNyZXQ"


def run(coro):
    return asyncio.run(coro)


def test_a_key_logs_in_as_sa_with_its_own_inbox_prefix():
    key = ServiceKey(KEY)
    assert key.key_id == "abcdefghijklmnop"
    assert key.connect_options() == {
        "user": "sa",
        "password": KEY,
        "inbox_prefix": "_INBOX.abcdefghijklmnop",
    }
    assert KEY not in repr(key)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "token",
        "abi_pk_abcdefghijklmnop_x",
        "abi_sk_short_x",
        "abi_sk_abcdefghijklmnop",
    ],
)
def test_only_service_keys_are_accepted(value):
    with pytest.raises(ValueError):
        ServiceKey(value)


def test_a_transport_given_a_key_logs_in_with_it():
    transport = Transport("nats://127.0.0.1:4222", KEY)
    assert isinstance(transport.credentials, ServiceKey)
    assert transport.options["user"] == "sa"
    assert transport.options["inbox_prefix"] == "_INBOX.abcdefghijklmnop"
    # A URL naming its own login keeps it.
    explicit = Transport("nats://engine:pw@127.0.0.1:4222", KEY)
    assert "user" not in explicit.options and "password" not in explicit.options
    # ... but the inbox prefix still confines the reply subscription.
    assert explicit.options["inbox_prefix"] == "_INBOX.abcdefghijklmnop"


def _exchanging(*responses):
    replies = [SimpleNamespace(data=r.SerializeToString()) for r in responses]
    nc = SimpleNamespace(request=AsyncMock(side_effect=replies))
    transport = SimpleNamespace(connect=AsyncMock(return_value=nc), timeout=5.0)
    return transport, nc


def test_the_key_is_exchanged_once_then_again_at_half_life(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("naas_abi_sdk.credentials.time.time", lambda: now[0])
    transport, nc = _exchanging(
        pb.TokenResponse(
            access_token="t1",
            expires_in=600,
            principal_id="sa_x",
            name="module/acme/people",
        ),
        pb.TokenResponse(
            access_token="t2",
            expires_in=600,
            principal_id="sa_x",
            name="module/acme/people",
        ),
    )
    key = ServiceKey(KEY)
    assert run(key.access_token(transport)) == "t1"
    now[0] += 299
    assert run(key.access_token(transport)) == "t1"
    now[0] += 1
    assert run(key.access_token(transport)) == "t2"
    subject, payload = nc.request.await_args.args[:2]
    assert subject == "abi.iam.v1.token"
    assert pb.TokenRequest.FromString(payload).key == KEY
    assert (key.principal_id, key.name) == ("sa_x", "module/acme/people")


def test_each_audience_is_exchanged_and_cached_on_its_own():
    transport, nc = _exchanging(
        pb.TokenResponse(access_token="kernel", expires_in=600),
        pb.TokenResponse(access_token="host", expires_in=600),
    )
    key = ServiceKey(KEY)
    assert run(key.access_token(transport)) == "kernel"
    assert run(key.access_token(transport, "abi:host")) == "host"
    assert run(key.access_token(transport)) == "kernel"  # cached
    assert run(key.access_token(transport, "abi:host")) == "host"
    audiences = [
        pb.TokenRequest.FromString(call.args[1]).audience
        for call in nc.request.await_args_list
    ]
    assert audiences == ["abi:nats", "abi:host"]


def test_a_refused_key_raises_unauthenticated():
    transport, _ = _exchanging(
        pb.TokenResponse(
            error=common_pb2.CallError(code="UNAUTHENTICATED", message="invalid key")
        )
    )
    with pytest.raises(RPCError, match="UNAUTHENTICATED"):
        run(ServiceKey(KEY).access_token(transport))


def test_module_accounts_name_their_project_and_module():
    assert module_account("module/acme/acme.people") == ("acme", "acme.people")
    assert module_account("ci/nightly") is None
    assert module_account("engine") is None


# -- waiting for approval ------------------------------------------------------------


class People(BaseModule):
    module_id = "people"
    dependencies = ModuleDependencies(services=("document",))


def _client(*submissions, name="module/acme/people"):
    key = ServiceKey(KEY)
    key.name = name
    transport = SimpleNamespace(
        credentials=key,
        access_token=AsyncMock(return_value="t"),
        reconnect=AsyncMock(),
    )
    iam = SimpleNamespace(submit_manifest=AsyncMock(side_effect=list(submissions)))
    return SimpleNamespace(_transport=transport, iam=iam), transport, iam


def _manifest(status, **extra):
    return pb.SubmitManifestResponse(
        manifest=pb.Manifest(status=status, sha256="f" * 64), **extra
    )


def test_an_approved_manifest_lets_the_module_start_without_reconnecting():
    client, transport, iam = _client(_manifest("approved", in_force=True))
    run(_await_approval(client, People, "people"))
    request = iam.submit_manifest.await_args.args[0]
    assert (request.module_id, request.project) == ("people", "acme")
    assert json.loads(request.document_json)["statements"][0]["actions"] == [
        "document:*"
    ]
    transport.reconnect.assert_not_awaited()


def test_an_approval_at_submission_reconnects_for_the_new_permissions():
    client, transport, _ = _client(
        _manifest("approved", approved_now=True, in_force=True)
    )
    run(_await_approval(client, People, "people"))
    transport.reconnect.assert_awaited_once()


def test_a_pending_manifest_waits_then_reconnects(monkeypatch):
    monkeypatch.setattr("naas_abi_sdk.module.APPROVAL_POLL_SECONDS", 0)
    client, transport, iam = _client(
        _manifest("pending"), _manifest("pending"), _manifest("approved", in_force=True)
    )
    run(_await_approval(client, People, "people"))
    assert iam.submit_manifest.await_count == 3
    transport.reconnect.assert_awaited_once()


def test_a_new_version_waits_while_the_approved_one_runs():
    client, transport, _ = _client(_manifest("pending", in_force=True))
    run(_await_approval(client, People, "people"))
    transport.reconnect.assert_not_awaited()


def test_a_rejected_manifest_stops_the_module():
    client, _, _ = _client(_manifest("rejected"))
    with pytest.raises(RuntimeError, match="rejected"):
        run(_await_approval(client, People, "people"))


def test_a_module_refuses_another_modules_key():
    client, _, iam = _client(name="module/acme/billing")
    with pytest.raises(ValueError, match="belongs to module/acme/billing"):
        run(_await_approval(client, People, "people"))
    iam.submit_manifest.assert_not_awaited()


def test_a_scripts_account_submits_no_manifest():
    client, _, iam = _client(name="ci/nightly")
    run(_await_approval(client, People, "people"))
    iam.submit_manifest.assert_not_awaited()
