"""The triple store passes the authorization contract (RFC §6.4, "triple_store").

A caller cannot read a graph it may not read through ``FROM``, ``FROM NAMED``,
``GRAPH <iri>``, ``GRAPH ?g``, the default graph, a stream or an export, in
process or over NATS; a SPARQL Update touches only graphs it may write.
"""

from __future__ import annotations

import pytest
from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
    RemoteTripleStoreService,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam.tests.data_service_contract import (
    ANY_OK,
    DENY,
    HIDDEN,
    NOT_FOUND,
    SECRET,
    Case,
    DataServiceContract,
    Expect,
    ok,
)
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient import (
    TripleStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.iam_catalog import CATALOG
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, Literal, URIRef

P = URIRef("http://p")
SHARED, PRIVATE, FROZEN = (
    URIRef(f"http://g/{n}") for n in ("shared", "private", "frozen")
)
INVALID = Expect("invalid")


class _Bus:
    """The bus a wired triple store notifies; nobody listens here."""

    def publish_many(self, *_args, **_kwargs) -> None:
        return None


def _triple(value: str) -> Graph:
    graph = Graph()
    graph.add((URIRef(f"http://s/{value.replace(' ', '-')}"), P, Literal(value)))
    return graph


def _objects(result) -> list[str]:
    return sorted(str(row[0]) for row in result)


def _streamed(store, query: str) -> list[str]:
    with store.query_stream(query) as result:
        return sorted(str(next(iter(row.values()))) for row in result.rows)


def _exported(store, graph=None) -> list[str]:
    with store.export(graph) as triples:
        return sorted(str(o) for _, p, o in triples if p == P)


def _name(iri: URIRef) -> str:
    from naas_abi_core.services.iam.names import encode_segment

    return f"abi:-:-:triple_store:graph/{encode_segment(str(iri))}"


class TestTripleStoreAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        return TripleStoreService(OxigraphEmbedded(str(tmp_path / "oxigraph")))

    def other_services(self, iam):
        return {"bus": _Bus()}

    def seed(self, owner):
        from pyoxigraph import DefaultGraph, NamedNode, Quad
        from pyoxigraph import Literal as OxLiteral

        for graph in (SHARED, PRIVATE, FROZEN):
            owner.insert(_triple(f"in {graph.rsplit('/', 1)[-1]}"), graph)
        # The store's own default graph holds data too.
        owner.adapter._store.add(
            Quad(
                NamedNode("http://s/default"),
                NamedNode(str(P)),
                OxLiteral("in default"),
                DefaultGraph(),
            )
        )

    def build_primary(self, owner):
        return TripleStorePrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return RemoteTripleStoreService(
            TripleStoreSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))
        )

    def close_remote(self, remote):
        remote.adapter.close()

    # Prefix patterns (`graph/<encoded iri>*`), as a role scoped to a graph
    # family has: they match any name that starts like the graph.
    def granted_resources(self):
        return [_name(SHARED) + "*"]

    def denied_resources(self):
        return [_name(PRIVATE) + "*"]

    def read_only_resources(self):
        return [_name(FROZEN) + "*"]

    def outcome_of(self, exc):
        if isinstance(exc, Exceptions.GraphNotFoundError):
            return NOT_FOUND
        if isinstance(exc, ValueError):
            return "invalid"
        return None

    def cases(self):
        return [
            *self.hostile_name_cases(),
            *self.escaped_name_cases(),
            *self.graph_cases(),
        ]

    @staticmethod
    def escaped_name_cases():
        """A prefixed name may escape characters of its local part (``g:\\/x``).
        The grammar drops the backslash and some stores do; rdflib keeps it, so
        IAM would check ``http://g\\/private`` while the store runs
        ``http://g/private``, a graph a Deny names. The escaped forms are no
        IRI: refused before any check, for everyone, queries and updates."""
        requests = {
            "drop": "PREFIX g: <http://g> DROP GRAPH g:\\/private",
            "copy into a readable graph": (
                "PREFIX h: <http:> INSERT { GRAPH <http://g/shared> { ?s ?p ?o } } "
                "WHERE { GRAPH h:\\/\\/g\\/private { ?s ?p ?o } }"
            ),
            "dot escape": "PREFIX g: <http://g/> CLEAR GRAPH g:private\\.x",
            "dash escape": "PREFIX g: <http://g/> CREATE GRAPH g:private\\-x",
            "add": (
                "PREFIX g: <http://g/> ADD GRAPH g:private\\~x TO <http://g/shared>"
            ),
            "query": (
                "PREFIX g: <http://g> SELECT ?o WHERE { GRAPH g:\\/private { ?s ?p ?o } }"
            ),
        }
        invalid = {"nobody": INVALID, "granted": INVALID, "denied": INVALID}
        return [
            Case(f"escaped name: {name}", lambda t, r=request: t.query(r), **invalid)
            for name, request in requests.items()
        ]

    @staticmethod
    def hostile_name_cases():
        """A graph name IAM would match under ``shared*`` but that is not an
        IRI: it would be checked as text and run as SPARQL (``>``, ``{``, a
        space, a newline close the IRI or the block). Refused before the check
        for everyone, so the checked name is the executed one and there is no
        denied or not-found oracle."""
        hostile = [
            f"{SHARED}> {{ ?s ?p ?o }} }} ; DROP ALL ; INSERT DATA {{ GRAPH <{SHARED}",
            f"{SHARED}{{x",
            f"{SHARED} x",
            f"{SHARED}\nx",
            f"{SHARED}>",
            f"{PRIVATE}>",
        ]
        invalid = {"nobody": INVALID, "granted": INVALID, "denied": INVALID}
        cases = []
        for number, name in enumerate(hostile):
            graph = URIRef(name)
            operations = {
                "insert": lambda t, g=graph: t.insert(_triple("x"), g),
                "remove": lambda t, g=graph: t.remove(_triple("x"), g),
                "create_graph": lambda t, g=graph: t.create_graph(g),
                "clear_graph": lambda t, g=graph: t.clear_graph(g),
                "drop_graph": lambda t, g=graph: t.drop_graph(g),
                "get_subject_graph in": lambda t, g=graph: t.get_subject_graph(
                    "http://s/in-shared", str(g)
                ),
                "get_subject_graph of": lambda t, n=name: t.get_subject_graph(
                    n, str(SHARED)
                ),
                "get_subject_graph across": lambda t, n=name: t.get_subject_graph(n),
            }
            for operation, call in operations.items():
                cases.append(
                    Case(f"{operation}, hostile name {number}", call, **invalid)
                )
        return cases

    def graph_cases(self):
        any_graph = f"SELECT ?o WHERE {{ GRAPH ?g {{ ?s <{P}> ?o }} }}"
        default = f"SELECT ?o WHERE {{ ?s <{P}> ?o }}"
        visible = ["in frozen", "in shared"]
        return [
            Case(
                "list graphs",
                lambda t: [
                    g for g in t.list_graphs() if str(g).startswith("http://g/")
                ],
                nobody=ok([]),
                granted=ok([str(SHARED)]),
                denied=ok([str(FROZEN), str(SHARED)]),
                view=lambda graphs: sorted(str(g) for g in graphs),
            ),
            Case(
                "GRAPH ?g sees only readable graphs",
                lambda t: t.query(any_graph),
                nobody=ok([]),
                granted=ok(["in shared"]),
                denied=ok(visible),
                view=_objects,
            ),
            Case(
                "the default graph is a graph like any other",
                lambda t: t.query(default),
                nobody=ok([]),
                granted=ok([]),
                denied=ok(["in default"]),
                view=_objects,
            ),
            Case(
                "FROM a forbidden graph",
                lambda t: t.query(
                    f"SELECT ?o FROM <{PRIVATE}> WHERE {{ ?s <{P}> ?o }}"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "FROM NAMED a forbidden graph",
                lambda t: t.query(
                    f"SELECT ?o FROM NAMED <{PRIVATE}> WHERE {{ GRAPH ?g {{ ?s ?p ?o }} }}"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "GRAPH <forbidden>",
                lambda t: t.query(
                    f"SELECT ?o WHERE {{ GRAPH <{PRIVATE}> {{ ?s ?p ?o }} }}"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "GRAPH <forbidden> inside FILTER EXISTS",
                lambda t: t.query(
                    f"ASK {{ FILTER EXISTS {{ GRAPH <{PRIVATE}> {{ ?s ?p ?o }} }} }}"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "FROM a readable graph",
                lambda t: t.query(f"SELECT ?o FROM <{SHARED}> WHERE {{ ?s <{P}> ?o }}"),
                nobody=HIDDEN,
                granted=ok(["in shared"]),
                denied=ok(["in shared"]),
                view=_objects,
            ),
            Case(
                "stream GRAPH ?g",
                lambda t: _streamed(t, any_graph),
                nobody=ok([]),
                granted=ok(["in shared"]),
                denied=ok(visible),
            ),
            Case(
                "stream FROM a forbidden graph",
                lambda t: _streamed(
                    t, f"SELECT ?o FROM <{PRIVATE}> WHERE {{ ?s <{P}> ?o }}"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "export a forbidden graph",
                lambda t: _exported(t, PRIVATE),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "export a readable graph",
                lambda t: _exported(t, SHARED),
                nobody=HIDDEN,
                granted=ok(["in shared"]),
                denied=ok(["in shared"]),
            ),
            Case(
                "export the default graph",
                lambda t: _exported(t),
                nobody=ok([]),
                granted=ok([]),
                denied=ok(["in default"]),
            ),
            Case(
                "SERVICE needs every graph",
                lambda t: t.query(
                    "SELECT * WHERE { SERVICE <http://elsewhere/sparql> { ?s ?p ?o } }"
                ),
                nobody=DENY,
                granted=DENY,
                denied=DENY,
            ),
            Case(
                "an unparsable request",
                lambda t: t.query("SELEKT nothing"),
                nobody=INVALID,
                granted=INVALID,
                denied=INVALID,
            ),
            Case(
                "insert into a read-only graph",
                lambda t: t.insert(_triple("x"), FROZEN),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "INSERT DATA into a read-only graph",
                lambda t: t.query(
                    f'INSERT DATA {{ GRAPH <{FROZEN}> {{ <http://s/x> <{P}> "x" }} }}'
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "DROP a forbidden graph",
                lambda t: t.query(f"DROP GRAPH <{PRIVATE}>"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "an update reaching out through SERVICE, USING its own graph",
                lambda t: t.query(
                    f"INSERT {{ GRAPH <{SHARED}> {{ ?s ?p ?o }} }} USING <{SHARED}> "
                    "WHERE { SERVICE <http://127.0.0.1:1/query> "
                    f"{{ GRAPH <{PRIVATE}> {{ ?s ?p ?o }} }} }}"
                ),
                nobody=HIDDEN,
                granted=DENY,
                denied=DENY,
            ),
            Case(
                "LOAD a forbidden graph of the store into a readable one",
                lambda t: t.query(f"LOAD <{PRIVATE}> INTO GRAPH <{SHARED}>"),
                nobody=HIDDEN,
                granted=DENY,
                denied=DENY,
            ),
            Case(
                "CLEAR ALL",
                lambda t: t.query("CLEAR ALL"),
                nobody=DENY,
                granted=DENY,
                denied=DENY,
            ),
            Case(
                "a subject across graphs",
                lambda t: t.get_subject_graph("http://s/in-private"),
                nobody=ok([]),
                granted=ok([]),
                denied=ok([]),
                view=lambda graph: sorted(str(o) for o in graph.objects()),
            ),
            Case(
                "a readable subject across graphs",
                lambda t: t.get_subject_graph("http://s/in-shared"),
                nobody=ok([]),
                granted=ok(["in shared"]),
                denied=ok(["in shared"]),
                view=lambda graph: sorted(str(o) for o in graph.objects()),
            ),
            Case(
                "insert into a readable graph",
                lambda t: t.insert(_triple("new"), SHARED),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
        ]


def test_on_a_union_store_an_update_reading_the_default_graph_needs_every_graph(
    tmp_path,
):
    """Fuseki's default graph is the union of the named graphs: copying it into
    a readable graph would copy the forbidden ones too."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
    )
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

    contract = TestTripleStoreAuthorization()
    owner, _ = contract._owner(tmp_path)
    owner.adapter.union_default_graph = True  # as Fuseki declares
    copy = f"INSERT {{ GRAPH <{SHARED}> {{ ?s ?p ?o }} }} WHERE {{ ?s ?p ?o }}"
    for principal in ("granted", "denied"):
        with use_call_context(CallContext(principal=service_account(principal))):
            with pytest.raises(PermissionDeniedError):
                owner.query(copy)
            with pytest.raises((PermissionDeniedError, Exceptions.GraphNotFoundError)):
                owner.query("DELETE WHERE { ?s ?p ?o }")


def test_a_view_never_runs_an_update_even_for_a_caller_allowed_every_graph(
    tmp_path,
):
    """``query_view`` is a read: the shortcut for broad callers must not let an
    update through it."""
    from naas_abi_core.services.iam.enforcement import internal_call

    contract = TestTripleStoreAuthorization()
    owner, _ = contract._owner(tmp_path)
    with internal_call():
        with pytest.raises(ValueError, match="not a query"):
            owner.query_view("any", f"DROP GRAPH <{SHARED}>")
        assert SHARED in owner.list_graphs()


class _RecordingBus(_Bus):
    def __init__(self) -> None:
        self.subscriptions: list[str] = []

    def subscribe(self, _topic, routing_key, _callback) -> None:
        self.subscriptions.append(routing_key)


def test_a_subscription_is_a_read_of_the_graph_it_names(tmp_path):
    """Its messages are the graph's triples: a graph the caller cannot read
    cannot be followed, and ``*`` follows every graph, so it needs them all."""
    from naas_abi_core.engine.call_context import use_call_context
    from naas_abi_core.engine.IEngine import IEngine
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
    from naas_abi_core.services.iam.tests.data_service_contract import caller

    contract = TestTripleStoreAuthorization()
    owner, iam = contract._owner(tmp_path)
    bus = _RecordingBus()
    owner.set_services(IEngine.Services(iam=iam, bus=bus))
    anything = (None, None, None)

    def follow(principal: str, graph: URIRef | str) -> None:
        with use_call_context(caller(principal)):
            owner.subscribe(anything, lambda _data: None, graph_name=graph)

    # Allowed nothing: the graphs do not exist for it.
    with pytest.raises(Exceptions.GraphNotFoundError):
        follow("nobody", SHARED)
    # Allowed `shared` only: that graph, not the others, not every graph.
    follow("granted", SHARED)
    assert len(bus.subscriptions) == 1
    with pytest.raises(Exceptions.GraphNotFoundError):
        follow("granted", PRIVATE)
    with pytest.raises(PermissionDeniedError):
        follow("granted", "*")
    # Allowed everything but `private`: Deny beats Allow, for `*` too.
    follow("denied", SHARED)
    with pytest.raises(Exceptions.GraphNotFoundError):
        follow("denied", PRIVATE)
    with pytest.raises(PermissionDeniedError):
        follow("denied", "*")
    assert len(bus.subscriptions) == 2
    # A caller allowed every graph follows every graph.
    with internal_call():
        owner.subscribe(anything, lambda _data: None)
    assert bus.subscriptions[-1].startswith("ts.*.g.*.")
