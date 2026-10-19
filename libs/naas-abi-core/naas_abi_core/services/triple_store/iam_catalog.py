"""triple_store's action catalog (RFC §6.4, "triple_store").

``graph/<iri>`` is a named graph, by IRI, opaque and placed; ``graph/default``
is the default graph (an encoded IRI always holds ``%3A``, so the two never
collide). ``view/<name>`` is a platform-level view.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
    stream_subjects,
)

SERVICE = "triple_store"
SUBJECT_PREFIX = "abi.svc.triple_store.v1"
STREAM = stream_subjects(f"{SUBJECT_PREFIX}.transfer")
GRAPH = "graph"
VIEW = "view"
DEFAULT_GRAPH = "default"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(
            GRAPH,
            id="opaque",
            description="A named graph, by IRI. `default` is the default graph.",
        ),
        ResourceType(VIEW, id="opaque", placement="platform", description="A view."),
    ),
    actions=(
        service_action("ListGraphs", "list", (GRAPH,), _subject("list_graphs")),
        service_action("Get", "read", (GRAPH,), _subject("get")),
        service_action(
            "GetSubjectGraph", "read", (GRAPH,), _subject("get_subject_graph")
        ),
        service_action("Query", "read", (GRAPH,), _subject("query")),
        service_action("QueryStream", "read", (GRAPH,), *STREAM),
        service_action("QueryView", "read", (VIEW,), _subject("query_view")),
        service_action("Export", "read", (GRAPH,), *STREAM),
        # In process only: it wires a bus callback, there is no NATS subject.
        service_action(
            "Subscribe",
            "read",
            (GRAPH,),
            description="Receive the triples inserted into or removed from a graph.",
        ),
        service_action("Insert", "write", (GRAPH,), _subject("insert")),
        service_action("Remove", "write", (GRAPH,), _subject("remove")),
        service_action(
            "CreateGraph", "write", (GRAPH,), _subject("create_graph"), creates=True
        ),
        service_action("ClearGraph", "admin", (GRAPH,), _subject("clear_graph")),
        service_action("DropGraph", "admin", (GRAPH,), _subject("drop_graph")),
        service_action(
            "HandleViewEvent", "admin", (VIEW,), _subject("handle_view_event")
        ),
    ),
)
