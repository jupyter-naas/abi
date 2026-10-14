import asyncio
import json
from typing import ClassVar
from urllib.parse import quote

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.event_resources import (
    EventResources,
    humanize,
    payload_fields,
    payload_summary,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ReadOnlyResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    ResourceTooLarge,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess


class Signed(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/events/Signed"
    _property_uris: ClassVar[dict] = {**LogProcess._property_uris, "who": "http://example.org/who"}
    who: str | None = None


class Paid(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/events#Paid"


class Shipped(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/events/Shipped"


SIGNED = quote(Signed._class_uri, safe="")


@pytest.fixture
def service(tmp_path):
    events = EventService(EventSQLiteAdapter(str(tmp_path / "events.sqlite")))
    for who in ("ada", "bob", "cyd"):
        events.publish(Signed(who=who))
    events.publish(Paid())
    events.publish(Shipped())
    return events


class TestEventTypes(ReadOnlyResourcesContract):
    @pytest.fixture
    def resources(self, service):
        return EventResources(service)


class TestEventsOfOneType(ReadOnlyResourcesContract):
    base = SIGNED

    @pytest.fixture
    def resources(self, service):
        return EventResources(service)


def test_types_are_containers_with_counts(service):
    page = asyncio.run(EventResources(service).list())

    signed = next(e for e in page.entries if e.attributes["type"] == Signed._class_uri)
    assert (signed.id, signed.name, signed.kind) == (SIGNED, "Signed", "container")
    assert (signed.attributes["count"], signed.attributes["last_seq"]) == ("3", "3")
    assert {e.name for e in page.entries} == {"Signed", "Paid", "Shipped"}


def test_events_list_newest_first_and_read_as_json(service):
    resources = EventResources(service)

    page = asyncio.run(resources.list(SIGNED))
    detail = asyncio.run(resources.read(f"{SIGNED}/2"))
    body = json.loads(detail.content.text)

    assert [e.id for e in page.entries] == [f"{SIGNED}/3", f"{SIGNED}/2", f"{SIGNED}/1"]
    assert (body["type"], body["seq"], body["payload"]["who"]) == (Signed._class_uri, 2, "bob")
    assert detail.entry.actions == ("read", "download")


def test_an_event_is_only_found_under_its_own_type(service):
    resources = EventResources(service)
    paid = quote(Paid._class_uri, safe="")

    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.stat(f"{paid}/1"))
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.stat(f"{SIGNED}/99"))
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.stat(f"{SIGNED}/abc"))


def test_bad_parents_and_cursors(service):
    resources = EventResources(service)

    with pytest.raises(InvalidResource):
        asyncio.run(resources.list(f"{SIGNED}/1"))
    with pytest.raises(InvalidResource):
        asyncio.run(resources.list(SIGNED, cursor="x"))
    with pytest.raises(InvalidResource):
        asyncio.run(resources.read(SIGNED))
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.list(quote("http://example.org/Nothing", safe="")))


def test_download_is_the_json_document_and_bounded(service):
    resources = EventResources(service)

    data = asyncio.run(resources.download(f"{SIGNED}/1", max_bytes=1 << 20))

    assert json.loads(data)["payload"]["who"] == "ada"
    with pytest.raises(ResourceTooLarge):
        asyncio.run(resources.download(f"{SIGNED}/1", max_bytes=10))


def test_types_are_named_in_words_with_their_domain(service):
    page = asyncio.run(EventResources(service).list())
    signed = next(e for e in page.entries if e.attributes["type"] == Signed._class_uri)

    assert signed.attributes["domain"] == "events"
    assert signed.attributes["local_name"] == "Signed"
    assert signed.attributes["summary"] == Signed._class_uri
    assert humanize("AgentAIMessageEmitted") == "Agent AI message emitted"
    assert humanize("KeyValueSet") == "Key value set"


def test_events_carry_a_summary_and_a_clean_json_view(service):
    resources = EventResources(service)

    (newest, *_) = asyncio.run(resources.list(SIGNED)).entries
    detail = asyncio.run(resources.read(newest.id))

    assert (newest.name, newest.attributes["seq"]) == ("#3", "3")
    assert newest.attributes["summary"] == "who=cyd"
    assert detail.view["type"] == "json"
    assert detail.view["value"]["who"] == "cyd"
    assert "_property_uris" not in detail.view["value"]
    assert "_property_uris" in detail.content.text  # the raw document keeps everything


def test_search_matches_type_names_then_payload_text(service):
    resources = EventResources(service)

    types = asyncio.run(resources.list("", query="SHIP"))
    events = asyncio.run(resources.list(SIGNED, query="bob"))

    assert resources.capabilities.search is True
    assert [e.name for e in types.entries] == ["Shipped"]
    assert [e.id for e in events.entries] == [f"{SIGNED}/2"]


def test_payload_summary_keeps_the_telling_fields():
    payload = {
        "_uri": "http://ontology.naas.ai/abi/1",
        "_class_uri": "http://x/ObjectPut",
        "created_at": "2026-10-02T15:20:47+00:00",
        "triggered_via": "api",
        "actor_user_id": "user-1",
        "prefix": "naas_abi/nexus",
        "key": "metadata.json",
        "size_bytes": 1108,
        "graph_name": "http://ontology.naas.ai/graph/nexus-identity",
        "note": "x" * 80,
    }

    summary = payload_summary(payload)

    assert summary.startswith("path=naas_abi/nexus/metadata.json · graph_name=nexus-identity")
    assert "size=1.1 KB" in summary
    assert "_uri" not in summary and "triggered_via" not in summary
    assert payload_summary("not an object") == ""
    assert len(payload_fields({"note": "y" * 200})[0][1]) == 48
