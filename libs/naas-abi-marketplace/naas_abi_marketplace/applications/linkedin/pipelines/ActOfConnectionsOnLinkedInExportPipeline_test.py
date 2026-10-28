from pathlib import Path

import pytest
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    read_connections_csv,
)
from naas_abi_marketplace.applications.linkedin.pipelines.ActOfConnectionsOnLinkedInExportPipeline import (
    LINKEDIN,
    ActOfConnectionsOnLinkedInExportPipeline,
    ActOfConnectionsOnLinkedInExportPipelineConfiguration,
    ActOfConnectionsOnLinkedInExportPipelineParameters,
    KnownPerson,
    linkedin_key,
    linkedin_person_uri,
    linkedin_profile_slug,
    normalize_linkedin_url,
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ABI = "http://ontology.naas.ai/abi/"
PERSON = URIRef(f"{ABI}Person")
ACT = LINKEDIN.ActOfConnection
WORKING = URIRef(f"{ABI}ActOfWorking")
EMAIL = URIRef(f"{ABI}email_address")

CSV = b"""Notes:
"When exporting your connection data, you may notice that some of the email addresses are missing."

First Name,Last Name,URL,Email Address,Company,Position,Connected On
Jane,Doe,https://www.linkedin.com/in/jane-doe,jane@example.com,AXA,Chief Risk Officer,23 Oct 2025
John,Smith,http://linkedin.com/in/John-Smith/,,EDF,Engineer,01 Jan 2024
Jane,Doe,https://www.linkedin.com/in/jane-doe-2,,,,05 Mar 2023
No,Url,,,ACME,CEO,05 Mar 2023
Jane,Doe,https://www.linkedin.com/in/jane-doe?trk=dup,,AXA,Chief Risk Officer,23 Oct 2025
"""

LINKEDIN_TTL = (
    Path(__file__).parents[1]
    / "ontologies"
    / "modules"
    / "ActOfConnectionsOnLinkedIn.ttl"
)
WORKING_TTL = (
    Path(__file__).parents[3]
    / "domains/intelligence/modules/people/ontologies/processes/ActOfWorkingProcess.ttl"
)


def _build(owner="http://ontology.naas.ai/abi/Person/alice", name="Alice Owner", **kw):
    pipeline = ActOfConnectionsOnLinkedInExportPipeline(
        ActOfConnectionsOnLinkedInExportPipelineConfiguration()
    )
    return pipeline.build(
        ActOfConnectionsOnLinkedInExportPipelineParameters(
            owner_uri=owner,
            owner_name=name,
            rows=read_connections_csv(CSV),
            source_path="uploads/linkedin/x/Connections.csv",
            **kw,
        )
    )


def _people(graph: Graph) -> set[URIRef]:
    return {s for s in graph.subjects(RDF.type, PERSON) if isinstance(s, URIRef)}


def _without_timestamps(graph: Graph) -> set:
    created = URIRef("http://purl.org/dc/terms/created")
    return {t for t in graph if t[1] != created}


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://www.linkedin.com/in/jane-doe",
            "https://www.linkedin.com/in/jane-doe",
        ),
        (
            "http://linkedin.com/in/Jane-Doe/?trk=x",
            "https://www.linkedin.com/in/jane-doe",
        ),
        ("fr.linkedin.com/in/jane-doe", "https://www.linkedin.com/in/jane-doe"),
        ("https://example.com/in/jane", None),
        ("https://www.linkedin.com/company/axa", None),
        ("", None),
        (None, None),
    ],
)
def test_linkedin_urls_are_normalized(url, expected):
    assert normalize_linkedin_url(url) == expected


def test_a_profile_key_is_ascii_unique_and_fits_a_slug():
    plain = "https://www.linkedin.com/in/jane-doe"
    accented = "https://www.linkedin.com/in/jérôme-durand"
    long = "https://www.linkedin.com/in/" + "a" * 120
    assert linkedin_key(plain) == "jane-doe"
    assert linkedin_key(accented) != linkedin_key(
        "https://www.linkedin.com/in/j-r-me-durand"
    )
    for url in (plain, accented, long):
        slug = linkedin_profile_slug(url)
        assert slug.isascii() and len(slug) <= 64 and slug[0].isalnum()


def test_the_csv_preamble_is_skipped():
    rows = read_connections_csv(CSV)
    assert rows[0]["First Name"] == "Jane"
    assert rows[0]["Connected On"] == "23 Oct 2025"
    assert len(rows) == 5


def test_one_act_of_connection_per_profile_between_owner_and_connection():
    graph, stats = _build()
    acts = set(graph.subjects(RDF.type, ACT))
    assert len(acts) == 3
    owner = URIRef("http://ontology.naas.ai/abi/Person/alice")
    for act in acts:
        assert (act, LINKEDIN.hasConnectionOwner, owner) in graph
        assert len(set(graph.objects(act, URIRef(f"{ABI}hasParticipant")))) == 2
        assert set(graph.objects(act, URIRef(f"{ABI}hasSourceDocument")))
    assert stats.as_dict() | {"skipped_reasons": None} == {
        "rows": 5,
        "created": 3,
        "matched": 0,
        "skipped": 2,
        "skipped_reasons": None,
    }
    assert stats.skipped_reasons == {"no_linkedin_url": 1, "duplicate_row": 1}


def test_the_connection_date_bounds_the_temporal_region():
    graph, _ = _build()
    dates = {str(o) for o in graph.objects(None, URIRef(f"{ABI}instant_date"))}
    assert {"2025-10-23", "2024-01-01", "2023-03-05"} <= dates


def test_two_people_with_the_same_name_stay_two_people():
    graph, _ = _build()
    janes = {p for p in _people(graph) if (p, RDFS.label, Literal("Jane Doe")) in graph}
    assert janes == {
        URIRef(linkedin_person_uri("https://www.linkedin.com/in/jane-doe")),
        URIRef(linkedin_person_uri("https://www.linkedin.com/in/jane-doe-2")),
    }


def test_company_and_position_become_an_act_of_working():
    graph, _ = _build()
    workings = set(graph.subjects(RDF.type, WORKING))
    # Jane Doe 2 has neither company nor position.
    assert len(workings) == 2
    orgs = {str(graph.value(w, URIRef(f"{ABI}forOrganization"))) for w in workings}
    assert orgs == {f"{ABI}Organization/axa", f"{ABI}Organization/edf"}


def test_reimporting_the_same_export_gives_the_same_graph():
    first, _ = _build()
    second, _ = _build()
    assert _without_timestamps(first) == _without_timestamps(second)


def test_a_person_in_two_exports_is_the_same_node():
    alice, _ = _build()
    bob, _ = _build(owner="http://ontology.naas.ai/abi/Person/bob", name="Bob Owner")
    shared = _people(alice) & _people(bob)
    assert URIRef(linkedin_person_uri("https://www.linkedin.com/in/jane-doe")) in shared
    # One act of connection in each graph, not a shared one.
    assert not set(alice.subjects(RDF.type, ACT)) & set(bob.subjects(RDF.type, ACT))


def test_a_known_linkedin_url_reuses_the_existing_person():
    existing = "http://ontology.naas.ai/abi/Person/jane-doe"
    graph, stats = _build(
        known_people={
            "https://www.linkedin.com/in/jane-doe": KnownPerson(
                uri=existing, slug="jane_doe"
            )
        }
    )
    assert stats.matched == 1 and stats.created == 2
    assert URIRef(existing) in _people(graph)
    assert (
        URIRef(existing),
        URIRef(f"{ABI}profile_slug"),
        Literal("jane_doe", datatype=URIRef("http://www.w3.org/2001/XMLSchema#string")),
    ) in graph
    assert (
        URIRef(linkedin_person_uri("https://www.linkedin.com/in/jane-doe")),
        None,
        None,
    ) not in graph


def test_an_email_is_stated_only_as_the_person_email():
    graph, _ = _build()
    holders = [(s, p) for s, p, o in graph if str(o) == "jane@example.com"]
    assert holders == [
        (URIRef(linkedin_person_uri("https://www.linkedin.com/in/jane-doe")), EMAIL)
    ]


def test_nothing_is_written_without_a_named_graph():
    class Store:
        def __init__(self):
            self.calls = []

        def insert(self, graph, graph_name=None):
            self.calls.append(graph_name)

    store = Store()
    params = ActOfConnectionsOnLinkedInExportPipelineParameters(
        owner_uri="http://ontology.naas.ai/abi/Person/alice",
        owner_name="Alice Owner",
        rows=read_connections_csv(CSV),
        source_path="x",
    )
    ActOfConnectionsOnLinkedInExportPipeline(
        ActOfConnectionsOnLinkedInExportPipelineConfiguration(triple_store=store)
    ).run(params)
    assert store.calls == []
    target = "http://ontology.naas.ai/graph/u1/linkedin"
    ActOfConnectionsOnLinkedInExportPipeline(
        ActOfConnectionsOnLinkedInExportPipelineConfiguration(
            triple_store=store, graph_name=target
        )
    ).run(params)
    assert store.calls == [URIRef(target)]


def test_the_act_of_connection_uses_the_act_of_working_vocabulary():
    ontology = Graph().parse(LINKEDIN_TTL)
    working = Graph().parse(WORKING_TTL)

    def restricted(graph, cls):
        return {
            graph.value(r, OWL.onProperty)
            for r in graph.objects(cls, RDFS.subClassOf)
            if (r, RDF.type, OWL.Restriction) in graph
        }

    act_props = restricted(ontology, ACT)
    working_props = restricted(working, WORKING)
    shared = {
        URIRef(f"{ABI}{name}")
        for name in (
            "hasParticipant",
            "occupiesTemporalRegion",
            "realizes",
            "hasSourceDocument",
        )
    }
    assert shared <= act_props and shared <= working_props
    # Who is an abi:Person, as in an act of working; the old CCO/linkedin-only
    # qualities are gone.
    assert (
        LINKEDIN.ConnectionsExportFile,
        RDFS.subClassOf,
        URIRef(f"{ABI}ProfileDocument"),
    ) in ontology
    for gone in (
        "CurrentPublicUrl",
        "EmailAddress",
        "CurrentJobPosition",
        "CurrentOrganization",
    ):
        assert (LINKEDIN[gone], RDF.type, OWL.Class) not in ontology


def test_the_pipeline_output_only_uses_declared_linkedin_terms():
    ontology = Graph().parse(LINKEDIN_TTL)
    declared = set(ontology.subjects(RDF.type, OWL.Class)) | set(
        ontology.subjects(RDF.type, OWL.ObjectProperty)
    )
    graph, _ = _build()
    used = {
        term
        for s, p, o in graph
        for term in (p, o if p == RDF.type else None)
        if isinstance(term, URIRef)
        and str(term).startswith(str(LINKEDIN))
        and str(term).count("/") == str(LINKEDIN).count("/")
    }
    assert used and used <= declared
