import asyncio
import json
from types import SimpleNamespace as NS

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.discovery_resources import (
    DiscoveryResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)


class RPCError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _instance(module_id, instance_id, status="READY"):
    from naas_abi_sdk.jobs import Every, JobDescriptor

    return NS(
        module_id=module_id,
        instance_id=instance_id,
        package_version="1.2.3",
        contract_major=1,
        status=status,
        expires_at=1_800_000_000.0,
        agents=(
            NS(
                name="Researcher",
                description="",
                contract_major=1,
                capabilities=("agent.invoke.v1",),
            ),
        ),
        jobs=(JobDescriptor("digest", triggers=(Every("10m"),)),),
        dependencies=(("store", 1),),
    )


class FakeClient:
    def __init__(self, instances, *, evict_error=None, list_error=None):
        self.instances, self.evict_error, self.list_error = instances, evict_error, list_error
        self.evicted = []

    async def list_modules(self, *, limit, after_instance_id=""):
        if self.list_error:
            raise self.list_error
        ordered = sorted(self.instances, key=lambda i: i.instance_id)
        rest = [i for i in ordered if i.instance_id > after_instance_id]
        page = rest[:limit]
        return tuple(page), page[-1].instance_id if len(rest) > limit else ""

    async def evict(self, instance_id):
        if self.evict_error:
            raise self.evict_error
        self.evicted.append(instance_id)


def _discovery(client):
    return DiscoveryResources(lambda: client)


def test_modules_group_their_instances_across_pages():
    instances = [_instance("acme", f"a-{i:03}") for i in range(150)] + [
        _instance("zeta", "z", status="STARTING")
    ]
    page = asyncio.run(_discovery(FakeClient(instances)).list(""))

    assert [(e.id, e.attributes["instances"]) for e in page.entries] == [
        ("acme", "150"),
        ("zeta", "1"),
    ]
    assert page.entries[1].attributes["status"] == "STARTING 1"


def test_reading_shows_the_descriptor_json():
    detail = asyncio.run(_discovery(FakeClient([_instance("acme", "a")])).read("acme/a"))
    body = json.loads(detail.content.text)

    assert body["dependencies"] == [{"module_id": "store", "contract_major": 1}]
    assert body["agents"][0]["capabilities"] == ["agent.invoke.v1"]
    assert body["jobs"][0]["name"] == "digest"
    assert body["lease_expires_at"].startswith("2027-01-15")


def test_delete_evicts_the_instance():
    client = FakeClient([_instance("acme", "a")])

    asyncio.run(_discovery(client).delete("acme/a"))

    assert client.evicted == ["a"]


@pytest.mark.parametrize(
    "error,raised",
    [
        (RPCError("INSTANCE_NOT_FOUND"), ResourceNotFound),
        (RPCError("PERMISSION_DENIED"), SourceUnavailable),
        (RPCError("REGISTRY_BUSY"), SourceUnavailable),
    ],
)
def test_eviction_errors_are_mapped(error, raised):
    client = FakeClient([_instance("acme", "a")], evict_error=error)

    with pytest.raises(raised):
        asyncio.run(_discovery(client).delete("acme/a"))


def test_unreachable_discovery_is_named():
    client = FakeClient([], list_error=RPCError("UNAVAILABLE"))

    with pytest.raises(SourceUnavailable, match="UNAVAILABLE"):
        asyncio.run(_discovery(client).list(""))


def test_modules_are_not_items_and_nothing_is_written():
    discovery = _discovery(FakeClient([_instance("acme", "a")]))

    with pytest.raises(InvalidResource):
        asyncio.run(discovery.read("acme"))
    with pytest.raises(UnsupportedOperation):
        asyncio.run(discovery.delete("acme"))
    with pytest.raises(UnsupportedOperation):
        asyncio.run(discovery.write("acme/b", b"{}"))
    with pytest.raises(ResourceNotFound):
        asyncio.run(discovery.stat("acme/missing"))
    with pytest.raises(ResourceNotFound):
        asyncio.run(discovery.list("nobody"))


def test_modules_summarize_agents_jobs_and_statuses():
    instances = [_instance("acme", "a"), _instance("acme", "b", status="STARTING")]
    (module,) = asyncio.run(_discovery(FakeClient(instances)).list("")).entries

    assert module.attributes["ready"] == "1"
    assert module.attributes["starting"] == "1"
    assert module.attributes["agents"] == "Researcher"
    assert module.attributes["jobs"] == "digest"
    assert module.attributes["versions"] == "1.2.3"
    assert module.attributes["summary"] == "2 instances · 1 agent · 1 job"


def test_instances_summarize_their_descriptor():
    (entry,) = asyncio.run(_discovery(FakeClient([_instance("acme", "a")])).list("acme")).entries

    assert entry.attributes["agents"] == "Researcher"
    assert entry.attributes["jobs"] == "digest"
    assert entry.attributes["dependencies"] == "store"
    assert entry.attributes["summary"] == "v1.2.3 · 1 agent · 1 job"


def test_reading_gives_a_status_view():
    detail = asyncio.run(_discovery(FakeClient([_instance("acme", "a")])).read("acme/a"))

    assert detail.view["type"] == "status"
    assert detail.view["phase"] == "READY"
    assert detail.view["fields"]["Version"] == "1.2.3"
    assert detail.view["agents"] == [
        {"name": "Researcher", "description": "", "capabilities": ["agent.invoke.v1"]}
    ]
    assert detail.view["jobs"][0]["name"] == "digest"
    assert detail.view["dependencies"] == [{"module_id": "store", "contract_major": 1}]
    assert detail.view["lease_expires_at"].startswith("2027-01-15")


def test_search_filters_modules_and_instances_by_name():
    discovery = _discovery(
        FakeClient(
            [_instance("acme.jobs", "a1"), _instance("acme.jobs", "b2"), _instance("zeta", "z")]
        )
    )

    assert discovery.capabilities.search is True
    assert [e.id for e in asyncio.run(discovery.list("", query="ACME")).entries] == ["acme.jobs"]
    assert [e.id for e in asyncio.run(discovery.list("acme.jobs", query="b")).entries] == [
        "acme.jobs/b2"
    ]
