"""Personal Knowledge Graph — per-user "My Graph" lifecycle and event indexing.

Maintains one named graph per user (URI ``…/graph/personal/{user_id}``, label
``"My Graph"``, role ``Personal``) and projects every chat lifecycle event
published through ``EventService`` into that graph as RDF triples:

- Conversation/Message individuals carry a ``nexus:hasStatus`` quality that
  starts at ``ActiveStatus`` and flips to ``DeletedStatus`` on a delete event
  — individuals themselves are never removed (history is preserved).
- Each event itself is logged as a ``LogProcess`` named individual linked
  to the artifact it touched via ``nexus:creates`` / ``nexus:updates`` /
  ``nexus:deletes``.

The service is registered as an EventService subscriber at API startup.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable

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
    KnowledgeGraph,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    UpdateConversation as UpdateConversationEvent,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    UpdateMessage as UpdateMessageEvent,
)
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import RDF, RDFS, XSD, Graph, Literal, URIRef
from rdflib.namespace import OWL

_logger = logging.getLogger(__name__)

# ── URIs ──────────────────────────────────────────────────────────────────────

PERSONAL_GRAPH_BASE = "http://ontology.naas.ai/graph/personal/"
PERSONAL_GRAPH_LABEL = "My Graph"

NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
NEXUS_NS = "http://ontology.naas.ai/nexus/"

_ACTIVE_STATUS = URIRef(NEXUS_NS + "ActiveStatus")
_DELETED_STATUS = URIRef(NEXUS_NS + "DeletedStatus")
_PERSONAL_ROLE = URIRef(NEXUS_NS + "PersonalKnowledgeGraphRole")
_HAS_STATUS = URIRef(NEXUS_NS + "hasStatus")
_HAS_MESSAGE = URIRef(NEXUS_NS + "hasMessage")
_IS_MESSAGE_OF = URIRef(NEXUS_NS + "isMessageOf")
_CREATES = URIRef(NEXUS_NS + "creates")
_UPDATES = URIRef(NEXUS_NS + "updates")
_DELETES = URIRef(NEXUS_NS + "deletes")
_CREATED_AT = URIRef(NEXUS_NS + "createdAt")
_USER_ID = URIRef(NEXUS_NS + "user_id")
_WORKSPACE_ID = URIRef(NEXUS_NS + "workspace_id")
_CONVERSATION_ID = URIRef(NEXUS_NS + "conversation_id")
_MESSAGE_ID = URIRef(NEXUS_NS + "message_id")
_ROLE = URIRef(NEXUS_NS + "role")
_CONTENT = URIRef(NEXUS_NS + "content")
_AGENT = URIRef(NEXUS_NS + "agent")
_TITLE = URIRef(NEXUS_NS + "title")

_CONVERSATION_CLASS = URIRef(NEXUS_NS + "Conversation")
_MESSAGE_CLASS = URIRef(NEXUS_NS + "Message")


def personal_graph_uri(user_id: str) -> URIRef:
    """Build the canonical personal-graph URI for *user_id*."""
    return URIRef(f"{PERSONAL_GRAPH_BASE}{user_id}")


def is_personal_graph_uri(graph_uri: str) -> bool:
    return graph_uri.startswith(PERSONAL_GRAPH_BASE)


def personal_graph_owner(graph_uri: str) -> str | None:
    """Return the user_id segment of a personal graph URI, or None."""
    if not is_personal_graph_uri(graph_uri):
        return None
    return graph_uri[len(PERSONAL_GRAPH_BASE):] or None


# ── Service ───────────────────────────────────────────────────────────────────


class PersonalGraphService:
    """Maintains one personal knowledge graph per user, indexed from chat events."""

    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter
        self._registered_users: set[str] = set()
        self._lock = threading.Lock()

    def _store(self) -> TripleStoreService:
        if self._triple_store_getter is not None:
            return self._triple_store_getter()
        from naas_abi import ABIModule

        return ABIModule.get_instance().engine.services.triple_store

    # ── Graph bootstrap ───────────────────────────────────────────────────────

    def ensure_personal_graph(self, user_id: str) -> URIRef:
        """Create the per-user named graph and register it in the nexus graph.

        Idempotent: safe to call from every event callback. Uses an in-memory
        set to avoid hitting the triple store on every event after warm-up.
        """
        if not user_id:
            raise ValueError("user_id is required to ensure a personal graph")
        graph_uri = personal_graph_uri(user_id)
        with self._lock:
            if user_id in self._registered_users:
                return graph_uri

        store = self._store()
        # create_graph is idempotent on the triple store side.
        store.create_graph(graph_uri)

        # Register the graph in the nexus graph so /graph/list surfaces it.
        registration = KnowledgeGraph(
            _uri=graph_uri,
            label=PERSONAL_GRAPH_LABEL,
            creator=user_id,
            has_knowledge_graph_role=[_PERSONAL_ROLE],
        )
        store.insert(registration.rdf(), graph_name=NEXUS_GRAPH_URI)

        with self._lock:
            self._registered_users.add(user_id)
        return graph_uri

    # ── Event indexing ────────────────────────────────────────────────────────

    def index_event(self, event: LogProcess) -> None:
        """Write the event and its target artifact to the user's personal graph."""
        try:
            self._index_event_unsafe(event)
        except Exception as exc:  # pragma: no cover - best-effort
            _logger.warning(
                "PersonalGraphService failed to index %s: %s",
                type(event).__name__,
                exc,
            )

    def _index_event_unsafe(self, event: LogProcess) -> None:
        user_id = getattr(event, "user_id", None)
        if not user_id:
            return  # events without a user_id are not part of a personal graph
        graph_uri = self.ensure_personal_graph(user_id)
        store = self._store()

        if isinstance(event, CreateConversationEvent):
            triples = self._build_create_conversation_triples(event, graph_uri)
            store.insert(triples, graph_name=graph_uri)
            return

        if isinstance(event, UpdateConversationEvent):
            triples = self._build_update_conversation_triples(event, graph_uri)
            store.insert(triples, graph_name=graph_uri)
            return

        if isinstance(event, DeleteConversationEvent):
            self._apply_delete_conversation(event, graph_uri)
            return

        if isinstance(event, CreateMessageEvent):
            triples = self._build_create_message_triples(event, graph_uri)
            store.insert(triples, graph_name=graph_uri)
            return

        if isinstance(event, UpdateMessageEvent):
            triples = self._build_update_message_triples(event, graph_uri)
            store.insert(triples, graph_name=graph_uri)
            return

        _logger.debug("PersonalGraphService: ignoring unknown event %s", type(event).__name__)

    # ── Triple builders ───────────────────────────────────────────────────────

    def _conversation_uri(self, graph_uri: URIRef, conversation_id: str) -> URIRef:
        return URIRef(f"{graph_uri}/conversation/{conversation_id}")

    def _message_uri(self, graph_uri: URIRef, message_id: str) -> URIRef:
        return URIRef(f"{graph_uri}/message/{message_id}")

    def _event_uri(self, graph_uri: URIRef, event: LogProcess) -> URIRef:
        # `_uri` is populated by RDFEntity.__init__ with a UUID4 fallback.
        # Anchor it inside the personal graph for human-friendly browsing.
        local_id = str(getattr(event, "_uri", "")).rsplit("/", 1)[-1] or "event"
        prefix = type(event).__name__
        return URIRef(f"{graph_uri}/event/{prefix}/{local_id}")

    def _add_common_event_triples(
        self,
        g: Graph,
        event: LogProcess,
        event_iri: URIRef,
        class_iri: URIRef,
    ) -> None:
        g.add((event_iri, RDF.type, OWL.NamedIndividual))
        g.add((event_iri, RDF.type, class_iri))
        g.add((event_iri, RDFS.label, Literal(class_iri.split("/")[-1])))
        user_id = getattr(event, "user_id", None)
        if user_id:
            g.add((event_iri, _USER_ID, Literal(user_id)))
        ws_id = getattr(event, "workspace_id", None)
        if ws_id:
            g.add((event_iri, _WORKSPACE_ID, Literal(ws_id)))
        created = getattr(event, "created", None)
        if created is not None:
            g.add((event_iri, _CREATED_AT, Literal(created.isoformat(), datatype=XSD.dateTime)))

    def _ensure_conversation_individual(
        self,
        g: Graph,
        graph_uri: URIRef,
        conversation_id: str,
        title: str | None,
        agent: str | None,
        user_id: str | None,
        workspace_id: str | None,
    ) -> URIRef:
        conv_iri = self._conversation_uri(graph_uri, conversation_id)
        g.add((conv_iri, RDF.type, OWL.NamedIndividual))
        g.add((conv_iri, RDF.type, _CONVERSATION_CLASS))
        g.add((conv_iri, _CONVERSATION_ID, Literal(conversation_id)))
        g.add((conv_iri, _HAS_STATUS, _ACTIVE_STATUS))
        if title:
            g.add((conv_iri, RDFS.label, Literal(title)))
            g.add((conv_iri, _TITLE, Literal(title)))
        else:
            g.add((conv_iri, RDFS.label, Literal(conversation_id)))
        if agent:
            g.add((conv_iri, _AGENT, Literal(agent)))
        if user_id:
            g.add((conv_iri, _USER_ID, Literal(user_id)))
        if workspace_id:
            g.add((conv_iri, _WORKSPACE_ID, Literal(workspace_id)))
        return conv_iri

    def _build_create_conversation_triples(
        self,
        event: CreateConversationEvent,
        graph_uri: URIRef,
    ) -> Graph:
        g = Graph()
        if not event.conversation_id:
            return g
        conv_iri = self._ensure_conversation_individual(
            g=g,
            graph_uri=graph_uri,
            conversation_id=event.conversation_id,
            title=event.title,
            agent=event.agent,
            user_id=event.user_id,
            workspace_id=event.workspace_id,
        )
        event_iri = self._event_uri(graph_uri, event)
        self._add_common_event_triples(
            g, event, event_iri, URIRef(CreateConversationEvent._class_uri)
        )
        g.add((event_iri, _CREATES, conv_iri))
        g.add((event_iri, _CONVERSATION_ID, Literal(event.conversation_id)))
        return g

    def _build_update_conversation_triples(
        self,
        event: UpdateConversationEvent,
        graph_uri: URIRef,
    ) -> Graph:
        g = Graph()
        if not event.conversation_id:
            return g
        conv_iri = self._conversation_uri(graph_uri, event.conversation_id)
        event_iri = self._event_uri(graph_uri, event)
        self._add_common_event_triples(
            g, event, event_iri, URIRef(UpdateConversationEvent._class_uri)
        )
        g.add((event_iri, _UPDATES, conv_iri))
        g.add((event_iri, _CONVERSATION_ID, Literal(event.conversation_id)))
        # Surface the change payload on the event itself; the artifact's
        # canonical state is left alone (immutable history).
        if event.title:
            g.add((event_iri, _TITLE, Literal(event.title)))
        if event.agent:
            g.add((event_iri, _AGENT, Literal(event.agent)))
        return g

    def _apply_delete_conversation(
        self,
        event: DeleteConversationEvent,
        graph_uri: URIRef,
    ) -> None:
        if not event.conversation_id:
            return
        store = self._store()
        conv_iri = self._conversation_uri(graph_uri, event.conversation_id)

        # Flip the status quality from Active to Deleted. The individual and
        # all message individuals it references are preserved.
        to_remove = Graph()
        to_remove.add((conv_iri, _HAS_STATUS, _ACTIVE_STATUS))
        store.remove(to_remove, graph_name=graph_uri)

        g = Graph()
        g.add((conv_iri, RDF.type, OWL.NamedIndividual))
        g.add((conv_iri, RDF.type, _CONVERSATION_CLASS))
        g.add((conv_iri, _HAS_STATUS, _DELETED_STATUS))

        event_iri = self._event_uri(graph_uri, event)
        self._add_common_event_triples(
            g, event, event_iri, URIRef(DeleteConversationEvent._class_uri)
        )
        g.add((event_iri, _DELETES, conv_iri))
        g.add((event_iri, _CONVERSATION_ID, Literal(event.conversation_id)))

        store.insert(g, graph_name=graph_uri)

    def _build_create_message_triples(
        self,
        event: CreateMessageEvent,
        graph_uri: URIRef,
    ) -> Graph:
        g = Graph()
        if not event.conversation_id or not event.message_id:
            return g
        conv_iri = self._ensure_conversation_individual(
            g=g,
            graph_uri=graph_uri,
            conversation_id=event.conversation_id,
            title=None,
            agent=None,
            user_id=event.user_id,
            workspace_id=event.workspace_id,
        )
        msg_iri = self._message_uri(graph_uri, event.message_id)
        g.add((msg_iri, RDF.type, OWL.NamedIndividual))
        g.add((msg_iri, RDF.type, _MESSAGE_CLASS))
        g.add((msg_iri, _MESSAGE_ID, Literal(event.message_id)))
        g.add((msg_iri, _CONVERSATION_ID, Literal(event.conversation_id)))
        g.add((msg_iri, _HAS_STATUS, _ACTIVE_STATUS))
        g.add((msg_iri, _IS_MESSAGE_OF, conv_iri))
        g.add((conv_iri, _HAS_MESSAGE, msg_iri))
        if event.role:
            g.add((msg_iri, _ROLE, Literal(event.role)))
        if event.content:
            g.add((msg_iri, _CONTENT, Literal(event.content)))
        if event.agent:
            g.add((msg_iri, _AGENT, Literal(event.agent)))
        if event.user_id:
            g.add((msg_iri, _USER_ID, Literal(event.user_id)))
        label = (event.content or event.role or event.message_id or "").strip()
        if label:
            g.add((msg_iri, RDFS.label, Literal(label[:120])))

        event_iri = self._event_uri(graph_uri, event)
        self._add_common_event_triples(
            g, event, event_iri, URIRef(CreateMessageEvent._class_uri)
        )
        g.add((event_iri, _CREATES, msg_iri))
        g.add((event_iri, _MESSAGE_ID, Literal(event.message_id)))
        g.add((event_iri, _CONVERSATION_ID, Literal(event.conversation_id)))
        if event.role:
            g.add((event_iri, _ROLE, Literal(event.role)))
        return g

    def _build_update_message_triples(
        self,
        event: UpdateMessageEvent,
        graph_uri: URIRef,
    ) -> Graph:
        g = Graph()
        if not event.conversation_id or not event.message_id:
            return g
        msg_iri = self._message_uri(graph_uri, event.message_id)
        event_iri = self._event_uri(graph_uri, event)
        self._add_common_event_triples(
            g, event, event_iri, URIRef(UpdateMessageEvent._class_uri)
        )
        g.add((event_iri, _UPDATES, msg_iri))
        g.add((event_iri, _MESSAGE_ID, Literal(event.message_id)))
        g.add((event_iri, _CONVERSATION_ID, Literal(event.conversation_id)))
        if event.content:
            g.add((event_iri, _CONTENT, Literal(event.content)))
        return g

    # ── Subscriber wiring ────────────────────────────────────────────────────

    _EVENT_CLASSES: tuple[type[LogProcess], ...] = (
        CreateConversationEvent,
        UpdateConversationEvent,
        DeleteConversationEvent,
        CreateMessageEvent,
        UpdateMessageEvent,
    )

    def register_subscribers(self, event_service: object) -> None:
        """Subscribe ``index_event`` to every chat lifecycle event class."""
        subscribe = getattr(event_service, "subscribe", None)
        if subscribe is None:
            return
        for cls in self._EVENT_CLASSES:
            try:
                subscribe(cls, self.index_event)
            except Exception as exc:  # pragma: no cover
                _logger.warning(
                    "PersonalGraphService: failed to subscribe %s: %s",
                    cls.__name__,
                    exc,
                )


_singleton: PersonalGraphService | None = None
_singleton_lock = threading.Lock()


def get_personal_graph_service() -> PersonalGraphService:
    """Lazy singleton accessor (one indexer per process)."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = PersonalGraphService()
        return _singleton
