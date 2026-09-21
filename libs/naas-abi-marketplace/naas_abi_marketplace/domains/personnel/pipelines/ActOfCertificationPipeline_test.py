"""Tests for ActOfCertificationPipeline."""

from __future__ import annotations

from datetime import date

from naas_abi.ontologies.modules.ABIOntology import Site
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    Certification,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfCertificationProcess import (
    ActOfCertification,
    CertificationCandidateRole,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfWorkingProcess import (
    ProfileDocument,
    Skill,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfCertificationPipeline import (
    ActOfCertificationPipeline,
    ActOfCertificationPipelineConfiguration,
    ActOfCertificationPipelineParameters,
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

PERSONNEL = "http://ontology.naas.ai/personnel/"
ABI_ORGANIZATION = URIRef("http://ontology.naas.ai/abi/Organization")
ABI_PERSON = URIRef("http://ontology.naas.ai/abi/Person")
ABI_TEMPORAL_REGION = URIRef("http://ontology.naas.ai/abi/TemporalRegion")
ABI_OCCURS_IN = URIRef("http://ontology.naas.ai/abi/occursIn")
ABI_OCCUPIES = URIRef("http://ontology.naas.ai/abi/occupiesTemporalRegion")
ABI_REALIZES = URIRef("http://ontology.naas.ai/abi/realizes")
ABI_CONCRETIZES = URIRef("http://ontology.naas.ai/abi/concretizes")
ABI_HAS_PARTICIPANT = URIRef("http://ontology.naas.ai/abi/hasParticipant")
SITE = URIRef(Site._class_uri)


def p(name: str) -> URIRef:
    return URIRef(f"{PERSONNEL}{name}")


def params(**overrides: object) -> ActOfCertificationPipelineParameters:
    base = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "name": "Certified Information Systems Auditor",
        "issuer": "ISACA",
        "issue_date": date(2019, 3, 1),
        "expiry_date": date(2022, 3, 1),
        "status": "expired",
        "credential_id": "CISA-123",
        "site": "Chicago",
        "skills": ["IT Audit"],
        "source_url": "https://demo.example/profiles/alice-dupont",
    }
    base.update(overrides)
    return ActOfCertificationPipelineParameters(**base)


def run(**overrides: object) -> Graph:
    pipeline = ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(triple_store=None, persist=False)
    )
    return pipeline.run(params(**overrides))


def types(graph: Graph) -> set[URIRef]:
    return {o for o in graph.objects(None, RDF.type) if isinstance(o, URIRef)}


def one(graph: Graph, cls: str) -> URIRef:
    [subject] = list(graph.subjects(RDF.type, URIRef(cls)))
    return subject


class TestSevenBuckets:
    def test_a_full_certification_fills_every_bucket(self) -> None:
        found = types(run())
        assert ABI_PERSON in found  # WHO: the candidate
        assert ABI_ORGANIZATION in found  # WHO: the certifying body
        assert URIRef(ActOfCertification._class_uri) in found  # WHAT
        assert ABI_TEMPORAL_REGION in found  # WHEN
        assert SITE in found  # WHERE
        assert URIRef(CertificationCandidateRole._class_uri) in found  # WHY
        assert URIRef(Skill._class_uri) in found  # HOW IT IS
        assert URIRef(Certification._class_uri) in found  # HOW WE KNOW
        assert URIRef(ProfileDocument._class_uri) in found  # HOW WE KNOW

    def test_the_act_is_wired_to_each_bucket(self) -> None:
        graph = run()
        act = one(graph, ActOfCertification._class_uri)
        person = one(graph, ABI_PERSON)
        certification = one(graph, Certification._class_uri)
        role = one(graph, CertificationCandidateRole._class_uri)
        issuer = one(graph, ABI_ORGANIZATION)

        assert (person, p("hasActOfCertification"), act) in graph
        assert (act, ABI_HAS_PARTICIPANT, person) in graph
        assert (act, p("forCertifyingOrganization"), issuer) in graph
        assert (act, p("hasAwardedCertification"), certification) in graph
        assert (act, ABI_REALIZES, role) in graph
        assert (person, p("hasCertificationCandidateRole"), role) in graph
        assert (act, ABI_OCCURS_IN, one(graph, Site._class_uri)) in graph
        assert (act, ABI_OCCUPIES, one(graph, ABI_TEMPORAL_REGION)) in graph
        assert (act, p("demonstratesSkill"), one(graph, Skill._class_uri)) in graph

    def test_the_certification_is_still_the_credential_the_person_carries(
        self,
    ) -> None:
        graph = run()
        person = one(graph, ABI_PERSON)
        certification = one(graph, Certification._class_uri)
        assert (person, p("hasCertification"), certification) in graph
        assert (
            certification,
            p("certification_name"),
            Literal("Certified Information Systems Auditor"),
        ) in graph
        assert (
            certification,
            p("issuedByOrganization"),
            one(graph, ABI_ORGANIZATION),
        ) in graph
        assert (
            certification,
            p("isSourcedFrom"),
            one(graph, ProfileDocument._class_uri),
        ) in graph

    def test_the_award_date_is_where_the_temporal_region_ends(self) -> None:
        graph = run()
        region = one(graph, ABI_TEMPORAL_REGION)
        [last] = list(
            graph.objects(region, URIRef("http://ontology.naas.ai/abi/hasLastInstant"))
        )
        [awarded] = list(graph.objects(last, p("instant_date")))
        assert awarded.toPython() == date(2019, 3, 1)
        assert not list(
            graph.objects(region, URIRef("http://ontology.naas.ai/abi/hasFirstInstant"))
        )


class TestWhatTheSourceDoesNotSay:
    """A source often lists a bare certification name. Nothing else is invented."""

    def test_a_bare_name_is_still_an_act_of_certification(self) -> None:
        graph = run(
            issuer=None,
            issue_date=None,
            expiry_date=None,
            status=None,
            credential_id=None,
            site=None,
            skills=[],
            source_url=None,
        )
        found = types(graph)
        assert URIRef(ActOfCertification._class_uri) in found
        assert URIRef(Certification._class_uri) in found
        assert URIRef(CertificationCandidateRole._class_uri) in found

        act = one(graph, ActOfCertification._class_uri)
        for predicate in (
            p("forCertifyingOrganization"),
            ABI_OCCURS_IN,
            ABI_OCCUPIES,
            p("demonstratesSkill"),
        ):
            assert not list(graph.objects(act, predicate)), predicate
        assert ABI_TEMPORAL_REGION not in found
        assert SITE not in found
        assert ABI_ORGANIZATION not in found
        assert URIRef(ProfileDocument._class_uri) not in found

    def test_the_same_certification_twice_is_one_act(self) -> None:
        pipeline = ActOfCertificationPipeline(
            ActOfCertificationPipelineConfiguration(triple_store=None, persist=False)
        )
        first = pipeline.run(params())
        second = pipeline.run(params())
        assert len(first) == len(second)
        assert len(list(first.subjects(RDF.type, URIRef(ActOfCertification._class_uri)))) == 1


def test_two_certifications_are_two_acts_sharing_the_candidate() -> None:
    from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
        PersonnelGraphContext,
    )

    context = PersonnelGraphContext()
    pipeline = ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(
            triple_store=None, persist=False, context=context
        )
    )
    pipeline.run(params())
    pipeline.run(params(name="Certified Public Accountant", issuer="AICPA"))
    graph = context.graph
    assert len(list(graph.subjects(RDF.type, URIRef(ActOfCertification._class_uri)))) == 2
    assert len(list(graph.subjects(RDF.type, ABI_PERSON))) == 1


def test_persists_only_when_a_triple_store_is_given() -> None:
    from unittest.mock import MagicMock

    store = MagicMock()
    ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(triple_store=store, persist=False)
    ).run(params())
    store.insert.assert_not_called()

    ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(triple_store=store)
    ).run(params())
    store.insert.assert_called_once()


def test_exposed_as_a_tool() -> None:
    [tool] = ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(triple_store=None, persist=False)
    ).as_tools()
    assert tool.name == "register_act_of_certification"
