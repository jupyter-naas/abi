"""Unit tests for PersonalGraphService.

Uses a fake triple-store double that records every insert/remove/create_graph
call. That keeps the test independent of the engine and the Fuseki/oxigraph
adapters — the only thing under test here is the indexer's projection of
chat events into the personal-graph URI scheme.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.personal_graph_service import (
    PERSONAL_GRAPH_BASE,
    PERSONAL_GRAPH_LABEL,
    PersonalGraphService,
    is_personal_graph_uri,
    personal_graph_owner,
    personal_graph_uri,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    CreateConversation as CreateConversationEvent,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    CreateMessage as CreateMessageEvent,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    DeleteConversation as DeleteConversationEvent,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    UpdateConversation as UpdateConversationEvent,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    UpdateMessage as UpdateMessageEvent,
)
from rdflib import Graph, Literal, URIRef

NEXUS = "http://ontology.naas.ai/nexus/"
HAS_STATUS = URIRef(NEXUS + "hasStatus")
ACTIVE_STATUS = URIRef(NEXUS + "ActiveStatus")
DELETED_STATUS = URIRef(NEXUS + "DeletedStatus")


class _FakeStore:
    """Triple-store double — keeps everything in an in-memory rdflib Graph per named graph."""

    def __init__(self) -> None:
        self.graphs: dict[str, Graph] = {}
        self.created: list[URIRef] = []

    def _graph(self, name: URIRef) -> Graph:
        return self.graphs.setdefault(str(name), Graph())

    def create_graph(self, graph_name: URIRef) -> None:
        self.created.append(graph_name)
        self._graph(graph_name)

    def insert(self, triples, graph_name: URIRef) -> None:
        target = self._graph(graph_name)
        for t in triples:
            target.add(t)

    def remove(self, triples, graph_name: URIRef) -> None:
        target = self._graph(graph_name)
        for t in triples:
            target.remove(t)


@pytest.fixture
def fake_store() -> _FakeStore:
    return _FakeStore()


@pytest.fixture
def svc(fake_store: _FakeStore) -> PersonalGraphService:
    return PersonalGraphService(triple_store_getter=lambda: fake_store)


# ── URI helpers ───────────────────────────────────────────────────────────────


def test_personal_graph_uri_uses_user_id() -> None:
    assert str(personal_graph_uri("alice")) == f"{PERSONAL_GRAPH_BASE}alice"


def test_is_personal_graph_uri_detects_prefix() -> None:
    assert is_personal_graph_uri(f"{PERSONAL_GRAPH_BASE}alice")
    assert not is_personal_graph_uri("http://ontology.naas.ai/graph/foo")


def test_personal_graph_owner_returns_user_id_segment() -> None:
    assert personal_graph_owner(f"{PERSONAL_GRAPH_BASE}alice") == "alice"
    assert personal_graph_owner("http://ontology.naas.ai/graph/foo") is None


# ── ensure_personal_graph ─────────────────────────────────────────────────────


def test_ensure_personal_graph_creates_and_registers_in_nexus(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    uri = svc.ensure_personal_graph("alice")
    assert str(uri) == f"{PERSONAL_GRAPH_BASE}alice"
    # The named graph itself was created.
    assert URIRef(str(uri)) in fake_store.created
    # The KnowledgeGraph individual was registered in the nexus graph with the
    # canonical "My Graph" label.
    nexus_graph = fake_store.graphs["http://ontology.naas.ai/graph/nexus"]
    labels = list(
        nexus_graph.objects(URIRef(str(uri)), URIRef("http://www.w3.org/2000/01/rdf-schema#label"))
    )
    assert Literal(PERSONAL_GRAPH_LABEL) in labels


def test_ensure_personal_graph_is_idempotent(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.ensure_personal_graph("alice")
    svc.ensure_personal_graph("alice")
    # After warm-up the subsequent call must not hit the store again.
    assert fake_store.created.count(URIRef(f"{PERSONAL_GRAPH_BASE}alice")) == 1


def test_ensure_personal_graph_rejects_empty_user(svc: PersonalGraphService) -> None:
    with pytest.raises(ValueError):
        svc.ensure_personal_graph("")


# ── index_event: CreateConversation ───────────────────────────────────────────


def test_create_conversation_event_inserts_conversation_with_active_status(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.index_event(
        CreateConversationEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
            title="Project Alpha",
            agent="aia",
            created=datetime(2026, 6, 1, 9, 14),
        )
    )
    graph = fake_store.graphs[f"{PERSONAL_GRAPH_BASE}alice"]
    conv_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/conversation/conv-1")
    assert (conv_iri, HAS_STATUS, ACTIVE_STATUS) in graph
    # Title surfaces on the artifact.
    assert (
        conv_iri,
        URIRef(NEXUS + "title"),
        Literal("Project Alpha"),
    ) in graph


def test_event_without_user_id_is_dropped(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.index_event(
        CreateConversationEvent(
            user_id=None,
            workspace_id="ws-1",
            conversation_id="conv-1",
        )
    )
    # No personal graph should be created for an anonymous event.
    assert not fake_store.created


# ── index_event: CreateMessage ────────────────────────────────────────────────


def test_create_message_event_links_message_to_conversation(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.index_event(
        CreateMessageEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
            message_id="msg-1",
            role="user",
            content="What is the status of Project Alpha?",
            agent=None,
            created=datetime(2026, 6, 1, 9, 14),
        )
    )
    graph = fake_store.graphs[f"{PERSONAL_GRAPH_BASE}alice"]
    msg_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/message/msg-1")
    conv_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/conversation/conv-1")
    assert (msg_iri, HAS_STATUS, ACTIVE_STATUS) in graph
    assert (msg_iri, URIRef(NEXUS + "isMessageOf"), conv_iri) in graph
    assert (conv_iri, URIRef(NEXUS + "hasMessage"), msg_iri) in graph
    assert (
        msg_iri,
        URIRef(NEXUS + "content"),
        Literal("What is the status of Project Alpha?"),
    ) in graph
    assert (msg_iri, URIRef(NEXUS + "role"), Literal("user")) in graph


# ── index_event: DeleteConversation ───────────────────────────────────────────


def test_delete_conversation_flips_status_without_removing_individual(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.index_event(
        CreateConversationEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
            title="Project Alpha",
        )
    )
    svc.index_event(
        CreateMessageEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
            message_id="msg-1",
            role="user",
            content="hello",
        )
    )
    svc.index_event(
        DeleteConversationEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
        )
    )
    graph = fake_store.graphs[f"{PERSONAL_GRAPH_BASE}alice"]
    conv_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/conversation/conv-1")
    msg_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/message/msg-1")

    # Status flipped, individual preserved.
    assert (conv_iri, HAS_STATUS, ACTIVE_STATUS) not in graph
    assert (conv_iri, HAS_STATUS, DELETED_STATUS) in graph
    assert (
        conv_iri,
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
        URIRef(NEXUS + "Conversation"),
    ) in graph
    # Message individual untouched.
    assert (msg_iri, HAS_STATUS, ACTIVE_STATUS) in graph


# ── index_event: UpdateConversation / UpdateMessage ───────────────────────────


def test_update_conversation_event_logs_change_on_event_individual(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.index_event(
        UpdateConversationEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
            title="New title",
        )
    )
    graph = fake_store.graphs[f"{PERSONAL_GRAPH_BASE}alice"]
    # Some Update* event individual was inserted that updates the conversation.
    conv_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/conversation/conv-1")
    update_subjects = list(
        graph.subjects(URIRef(NEXUS + "updates"), conv_iri)
    )
    assert update_subjects, "Expected at least one nexus:updates triple pointing to the conversation"
    # The new title is surfaced on the event individual (history-preserving).
    has_title = False
    for s in update_subjects:
        if (s, URIRef(NEXUS + "title"), Literal("New title")) in graph:
            has_title = True
    assert has_title


def test_update_message_event_inserts_update_event(
    svc: PersonalGraphService, fake_store: _FakeStore
) -> None:
    svc.index_event(
        UpdateMessageEvent(
            user_id="alice",
            workspace_id="ws-1",
            conversation_id="conv-1",
            message_id="msg-1",
            content="updated content",
        )
    )
    graph = fake_store.graphs[f"{PERSONAL_GRAPH_BASE}alice"]
    msg_iri = URIRef(f"{PERSONAL_GRAPH_BASE}alice/message/msg-1")
    update_subjects = list(graph.subjects(URIRef(NEXUS + "updates"), msg_iri))
    assert update_subjects
    has_content = any(
        (s, URIRef(NEXUS + "content"), Literal("updated content")) in graph
        for s in update_subjects
    )
    assert has_content


# ── register_subscribers ──────────────────────────────────────────────────────


def test_register_subscribers_wires_every_chat_event_class(
    svc: PersonalGraphService,
) -> None:
    calls: list[type] = []

    class _FakeEventService:
        def subscribe(self, event_cls, handler):
            calls.append(event_cls)
            assert handler == svc.index_event

    svc.register_subscribers(_FakeEventService())
    assert {c.__name__ for c in calls} == {
        "CreateConversation",
        "UpdateConversation",
        "DeleteConversation",
        "CreateMessage",
        "UpdateMessage",
    }


def test_register_subscribers_is_a_noop_when_service_lacks_subscribe(
    svc: PersonalGraphService,
) -> None:
    # No exception, no calls. Some test/dev event stubs may lack subscribe().
    svc.register_subscribers(object())
