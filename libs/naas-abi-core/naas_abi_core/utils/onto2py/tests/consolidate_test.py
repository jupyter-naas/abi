import json
from pathlib import Path

import pytest
import rdflib
from naas_abi_core.utils.onto2py.consolidate import (
    REGION_END,
    REGION_START,
    consolidate_processes,
    module_ontology_name,
    split_statements,
)
from naas_abi_core.utils.onto2py.module_codegen import LOCK_FILE, onto2py_module
from rdflib.namespace import OWL, RDF, RDFS

PREFIXES = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix abi:  <http://ontology.naas.ai/abi/> .
@prefix demo: <http://ontology.naas.ai/demo/> .
"""

WORKING = (
    PREFIXES
    + """@prefix cco: <https://www.commoncoreontologies.org/> .

demo:ActOfWorkingProcess a owl:Ontology ;
  owl:imports <http://ontology.naas.ai/abi/Ontology> ;
  owl:imports <https://www.commoncoreontologies.org/EventOntology> ;
  rdfs:comment "Slice. Shared classes live in the module ontology."@en .

# The process class.
demo:ActOfWorking a owl:Class ;
  rdfs:subClassOf cco:ont00000228 ,
    [ a owl:Restriction ; owl:onProperty demo:develops ; owl:someValuesFrom demo:Skill ] ;
  rdfs:label "Act of Working"@en .
"""
)

STUDYING = (
    PREFIXES
    + """
demo:ActOfStudyingProcess a owl:Ontology ;
  owl:imports <http://ontology.naas.ai/abi/Ontology> .

demo:ActOfStudying a owl:Class ;
  rdfs:label "Act of Studying"@en ;
  rdfs:comment "Ends with a dot. 1.5 is a decimal, \\"quoted\\" text too."@en .
"""
)

MODULE = (
    PREFIXES
    + """
demo:DemoOntology a owl:Ontology ;
  owl:imports <http://ontology.naas.ai/abi/Ontology> ;
  owl:imports <http://ontology.naas.ai/demo/ActOfWorkingProcess> ;
  owl:imports demo:ActOfStudyingProcess ;
  rdfs:label "Demo"@en .

# Shared class used by both slices.
demo:Skill a owl:Class ;
  rdfs:label "Skill"@en .
"""
)


def _module(tmp_path: Path, with_module: bool = True) -> Path:
    root = tmp_path / "demo"
    (root / "ontologies" / "processes").mkdir(parents=True)
    (root / "ontologies" / "modules").mkdir(parents=True)
    (root / "ontologies" / "processes" / "ActOfWorkingProcess.ttl").write_text(WORKING)
    (root / "ontologies" / "processes" / "ActOfStudyingProcess.ttl").write_text(
        STUDYING
    )
    if with_module:
        (root / "ontologies" / "modules" / "DemoOntology.ttl").write_text(MODULE)
    return root


def _graph(path: Path) -> rdflib.Graph:
    return rdflib.Graph().parse(path, format="turtle")


def test_module_ontology_name():
    assert module_ontology_name(Path("people")) == "PeopleOntology"
    assert module_ontology_name(Path("hr_core")) == "HrCoreOntology"


def test_split_statements_keeps_every_character():
    chunks = split_statements(WORKING + STUDYING)
    assert "".join(c.text for c in chunks) == WORKING + STUDYING
    # 5 prefixes + 2 statements, then 4 prefixes + 2 statements.
    assert [c.kind for c in chunks].count("statement") == 4


def test_consolidates_slices_into_existing_module_ontology(tmp_path):
    root = _module(tmp_path)
    target = consolidate_processes(root)

    assert target == root / "ontologies" / "modules" / "DemoOntology.ttl"
    text = target.read_text()
    g = _graph(target)
    demo = rdflib.Namespace("http://ontology.naas.ai/demo/")

    # One ontology, the module's; slice headers are gone.
    assert set(g.subjects(RDF.type, OWL.Ontology)) == {demo.DemoOntology}
    # Slice classes and the shared class are all in the one file.
    for cls in (demo.ActOfWorking, demo.ActOfStudying, demo.Skill):
        assert (cls, RDF.type, OWL.Class) in g
    # Imports of the slices themselves are dropped (IRI and prefixed form);
    # what the slices imported is carried over, once.
    imports = set(map(str, g.objects(demo.DemoOntology, OWL.imports)))
    assert imports == {
        "http://ontology.naas.ai/abi/Ontology",
        "https://www.commoncoreontologies.org/EventOntology",
    }
    # The `cco:` prefix the module lacked is declared in the region.
    assert "@prefix cco: <https://www.commoncoreontologies.org/> ." in text
    # Hand-authored content and slice comments survive.
    assert "# Shared class used by both slices." in text
    assert "# The process class." in text
    assert (demo.ActOfStudying, RDFS.comment, None) in g


def test_consolidation_is_idempotent(tmp_path):
    root = _module(tmp_path)
    target = consolidate_processes(root)
    first = target.read_text()
    consolidate_processes(root)
    assert target.read_text() == first
    assert first.count(REGION_START) == 1 and first.count(REGION_END) == 1


def test_consolidation_picks_up_slice_changes(tmp_path):
    root = _module(tmp_path)
    consolidate_processes(root)
    slice_path = root / "ontologies" / "processes" / "ActOfStudyingProcess.ttl"
    slice_path.write_text(STUDYING.replace("Act of Studying", "Act of Learning"))
    text = consolidate_processes(root).read_text()
    assert "Act of Learning" in text and "Act of Studying" not in text


def test_creates_module_ontology_when_missing(tmp_path):
    root = _module(tmp_path, with_module=False)
    target = consolidate_processes(root)

    assert target.name == "DemoOntology.ttl"
    g = _graph(target)
    onto = rdflib.URIRef("http://ontology.naas.ai/demo/DemoOntology")
    assert set(g.subjects(RDF.type, OWL.Ontology)) == {onto}
    assert (
        rdflib.URIRef("http://ontology.naas.ai/demo/ActOfWorking"),
        RDF.type,
        OWL.Class,
    ) in g


def test_conflicting_prefix_is_rejected(tmp_path):
    root = _module(tmp_path)
    slice_path = root / "ontologies" / "processes" / "ActOfStudyingProcess.ttl"
    slice_path.write_text(
        STUDYING.replace("<http://ontology.naas.ai/abi/>", "<http://other.example/>")
    )
    with pytest.raises(ValueError, match="prefix 'abi:'"):
        consolidate_processes(root)


def test_no_processes_is_a_no_op(tmp_path):
    root = tmp_path / "empty"
    (root / "ontologies" / "modules").mkdir(parents=True)
    assert consolidate_processes(root) is None


def _fake_generate(calls: list[str]):
    def generate(ttl: str) -> str:
        calls.append(Path(ttl).name)
        Path(ttl).with_suffix(".py").write_text("# generated\n")
        return ""

    return generate


def test_module_codegen_runs_processes_then_module(tmp_path):
    root = _module(tmp_path)
    calls: list[str] = []
    report = onto2py_module(root, generate=_fake_generate(calls))

    assert report.ok
    assert calls == [
        "ActOfStudyingProcess.ttl",
        "ActOfWorkingProcess.ttl",
        "DemoOntology.ttl",
    ]
    lock = json.loads((root / "ontologies" / LOCK_FILE).read_text())["files"]
    assert set(lock) == {
        "processes/ActOfStudyingProcess.ttl",
        "processes/ActOfWorkingProcess.ttl",
        "modules/DemoOntology.ttl",
    }


def test_module_codegen_skips_unchanged_files(tmp_path):
    root = _module(tmp_path)
    onto2py_module(root, generate=_fake_generate([]))

    calls: list[str] = []
    report = onto2py_module(root, generate=_fake_generate(calls))
    assert calls == []
    assert len(report.skipped) == 3

    # A slice change regenerates that slice and, through consolidation, the module.
    slice_path = root / "ontologies" / "processes" / "ActOfWorkingProcess.ttl"
    slice_path.write_text(WORKING.replace("Act of Working", "Act of Labour"))
    onto2py_module(root, generate=_fake_generate(calls))
    assert calls == ["ActOfWorkingProcess.ttl", "DemoOntology.ttl"]

    calls.clear()
    onto2py_module(root, force=True, generate=_fake_generate(calls))
    assert len(calls) == 3


def test_module_codegen_ignores_module_ttl_without_ontology(tmp_path):
    root = _module(tmp_path)
    (root / "ontologies" / "modules" / "Data.ttl").write_text(
        PREFIXES + 'demo:x rdfs:label "x" .\n'
    )
    calls: list[str] = []
    onto2py_module(root, generate=_fake_generate(calls))
    assert "Data.ttl" not in calls


def test_module_codegen_retries_failed_file(tmp_path):
    root = _module(tmp_path)

    def failing(ttl: str) -> str:
        raise ValueError("boom")

    report = onto2py_module(root, generate=failing)
    assert not report.ok
    # Nothing recorded, so the next run retries every file.
    calls: list[str] = []
    onto2py_module(root, generate=_fake_generate(calls))
    assert len(calls) == 3


def test_consolidates_into_the_only_module_ontology_when_names_differ(tmp_path):
    # Folder "demos", ontology "DemoOntology.ttl" (organizations / OrganizationOntology).
    root = _module(tmp_path)
    root = root.rename(tmp_path / "demos")
    (root / "ontologies" / "modules" / "NotAnOntology.ttl").write_text(
        PREFIXES + 'demo:Loose rdfs:label "loose" .\n'
    )
    target = consolidate_processes(root)

    assert target.name == "DemoOntology.ttl"
    assert not (root / "ontologies" / "modules" / "DemosOntology.ttl").exists()
    assert REGION_START in target.read_text()


def test_several_module_ontologies_fall_back_to_the_derived_name(tmp_path):
    root = _module(tmp_path)
    (root / "ontologies" / "modules" / "Other.ttl").write_text(
        PREFIXES + "demo:Other a owl:Ontology .\n"
    )
    root = root.rename(tmp_path / "demos")
    assert consolidate_processes(root).name == "DemosOntology.ttl"
