"""The static ontology check must not depend on the network.

ABIOntology imports BFO by its version IRI
(``http://purl.obolibrary.org/obo/bfo/2020/bfo-core.ttl``) while the vendored
``bfo-core.ttl`` declares ``owl:Ontology <.../bfo.owl>`` with that IRI as its
``owl:versionIRI``. When only ontology IRIs were indexed, BFO was fetched over
HTTP on every run, and a failed fetch cut every CCO class (e.g.
``nexus:Organization`` via ``cco:ont00000300``) off from its bucket root.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest
from rdflib import Graph

from naas_abi_core.utils import validate_bfo_ontology as v

_NEXUS_MODULES = (
    Path(v.__file__).resolve().parents[3]
    / "naas-abi"
    / "naas_abi"
    / "ontologies"
    / "modules"
)


@pytest.fixture
def offline(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("the ontology check tried to use the network")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    v._LOCAL_ONTOLOGY_INDEX.clear()
    yield
    v._LOCAL_ONTOLOGY_INDEX.clear()


def test_import_by_version_iri_resolves_to_the_local_file(tmp_path, offline) -> None:
    ontologies = tmp_path / "pkg" / "ontologies"
    ontologies.mkdir(parents=True)
    (ontologies / "upstream.ttl").write_text(
        """@prefix owl: <http://www.w3.org/2002/07/owl#> .
        <http://example.org/up.owl> a owl:Ontology ;
            owl:versionIRI <http://example.org/up/2020/up.ttl> .
        <http://example.org/Thing> a owl:Class ."""
    )
    main = tmp_path / "pkg" / "ontologies" / "main.ttl"
    main.write_text(
        """@prefix owl: <http://www.w3.org/2002/07/owl#> .
        <http://example.org/main> a owl:Ontology ;
            owl:imports <http://example.org/up/2020/up.ttl> ."""
    )
    graph = Graph()
    graph.parse(main)

    _combined, records = v.load_imports(graph, str(main.parent))

    assert [(r["status"], r["message"].split(":")[0]) for r in records] == [
        ("ok", "Resolved IRI to local file")
    ]


@pytest.mark.skipif(
    not _NEXUS_MODULES.exists(), reason="naas-abi sources not available"
)
def test_nexus_platform_ontology_checks_clean_offline(offline) -> None:
    report = v.validate(str(_NEXUS_MODULES / "NexusPlatformOntology.ttl"))

    assert all(r["status"] == "ok" for r in report["imports"]), report["imports"]
    assert report["errors"] == []


def _bucket_issues(body: str) -> list[dict]:
    g = Graph()
    g.parse(
        data="@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix bfo: <http://purl.obolibrary.org/obo/> .\n"
        "@prefix ex: <http://example.org/> .\n" + body,
        format="turtle",
    )
    return v.check_bucket_mapping(g)


def test_fiat_boundaries_need_no_bucket() -> None:
    # A geospatial position is a fiat point: no volume, so not a site, and
    # outside the 7 buckets by nature.
    assert _bucket_issues(
        "ex:Position a owl:Class ; rdfs:subClassOf bfo:BFO_0000147 .\n"
        "ex:Border a owl:Class ; rdfs:subClassOf bfo:BFO_0000142 .\n"
        "ex:Pin a owl:Class ; rdfs:subClassOf ex:Position .\n"
    ) == []


def test_classes_outside_the_buckets_are_still_reported() -> None:
    issues = _bucket_issues("ex:Loose a owl:Class ; rdfs:subClassOf bfo:BFO_0000141 .\n")
    assert [issue["category"] for issue in issues] == ["BUCKET_MAPPING"]
