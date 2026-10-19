import asyncio
from dataclasses import dataclass, field

import pytest
from naas_abi_proto.app.v1 import app_pb2

from naas_abi_core.services.identity.adapters.secondary import IdPAppNATS as module
from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError


@dataclass
class App:
    name: str


@dataclass
class Instance:
    module_id: str
    service_account: str
    instance_id: str
    status: str = "READY"
    contract_major: int = 1
    apps: tuple = field(default_factory=lambda: (App("idp"), App("admin")))


class Discovery:
    def __init__(self, instances):
        self.instances = instances
        self.reads = 0

    async def list_modules(self, *, limit=100, after_instance_id=""):
        self.reads += 1
        return tuple(self.instances), ""


def client(instances, account="SA-IDP", monkeypatch=None, answers=None):
    discovery = Discovery(instances)
    calls = []

    async def call_app(transport, project, instance_id, request, *, service_account):
        calls.append((project, instance_id, service_account, request))
        answer = (answers or {}).get(instance_id)
        if isinstance(answer, Exception):
            raise answer
        return answer or app_pb2.HttpResponse(status=200, body=b"{}")

    monkeypatch.setattr("naas_abi_sdk.app_host.call_app", call_app)
    app = module.IdPAppNATS(
        nats_url="nats://x",
        project="proj",
        token=lambda: "t",
        host_token=lambda recipient: f"host-{recipient}",
        service_account=lambda: account,
        run=lambda coro, timeout: asyncio.run(coro),
    )
    app._clients = lambda: (object(), discovery)  # type: ignore[method-assign]
    return app, discovery, calls


def test_only_the_instance_running_as_the_idps_account_is_called(monkeypatch):
    app, _, calls = client(
        [
            Instance("idp", "SA-OTHER", "evil"),  # the module id, another account
            Instance("people", "SA-IDP", "wrong-module"),
            Instance("idp", "SA-IDP", "starting", status="STAGED"),
            Instance("idp", "SA-IDP", "no-app", apps=(App("admin"),)),
            Instance("idp", "SA-IDP", "good"),
        ],
        monkeypatch=monkeypatch,
    )
    answer = app.request("GET", "/jwks.json", query="a=1", root_path="/idp")
    assert answer.status == 200
    project, instance, account, request = calls[0]
    assert (project, instance, account) == ("proj", "good", "SA-IDP")
    assert (
        request.app,
        request.method,
        request.path,
        request.query,
        request.root_path,
    ) == (
        "idp",
        "GET",
        "/jwks.json",
        "a=1",
        "/idp",
    )


def test_without_the_account_or_an_instance_the_idp_is_down(monkeypatch):
    app, _, calls = client(
        [Instance("idp", "SA-IDP", "good")], account=None, monkeypatch=monkeypatch
    )
    with pytest.raises(ProviderUnavailableError, match="No instance"):
        app.request("GET", "/jwks.json")
    assert calls == []
    app, _, calls = client(
        [Instance("idp", "SA-OTHER", "evil")], monkeypatch=monkeypatch
    )
    with pytest.raises(ProviderUnavailableError, match="No instance"):
        app.request("GET", "/jwks.json")
    assert calls == []


def test_a_failing_instance_is_retried_on_another_and_discovery_is_read_again(
    monkeypatch,
):
    from naas_abi_sdk.transport import RPCError

    app, discovery, calls = client(
        [Instance("idp", "SA-IDP", "a"), Instance("idp", "SA-IDP", "b")],
        monkeypatch=monkeypatch,
        answers={
            "a": RPCError("MODULE_UNAVAILABLE", "draining"),
            "b": RPCError("MODULE_UNAVAILABLE", "draining"),
        },
    )
    with pytest.raises(ProviderUnavailableError, match="draining"):
        app.request("GET", "/jwks.json")
    assert {c[1] for c in calls} == {"a", "b"}
    # A failure drops the snapshot: the next call reads discovery again.
    reads = discovery.reads
    with pytest.raises(ProviderUnavailableError):
        app.request("GET", "/jwks.json")
    assert discovery.reads == reads + 1


def test_the_instances_are_remembered_for_a_few_seconds(monkeypatch):
    app, discovery, _ = client(
        [Instance("idp", "SA-IDP", "a")], monkeypatch=monkeypatch
    )
    app.request("GET", "/jwks.json")
    app.request("GET", "/jwks.json")
    assert discovery.reads == 1


def test_a_streamed_answer_is_refused(monkeypatch):
    app, _, _ = client(
        [Instance("idp", "SA-IDP", "a")],
        monkeypatch=monkeypatch,
        answers={
            "a": app_pb2.HttpResponse(
                status=200, body_follows=True, body_inbox="_INBOX.x"
            )
        },
    )
    with pytest.raises(ProviderUnavailableError, match="streamed"):
        app.request("GET", "/jwks.json")
