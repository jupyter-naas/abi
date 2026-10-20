"""Structural checks for the generated ABI draft schemas (not an OWL reasoner)."""
import importlib.util
import json
import os
import unittest
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("build_process_ledger", ROOT / "build_process_ledger.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ABI, BFO = builder.ABI, builder.BFO


class ProcessLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "process_ledger_manifest.json").read_text())
        cls.graphs = {name: Graph().parse(ROOT / name) for name in cls.manifest["files"]}
        cls.graph = Graph()
        for graph in cls.graphs.values():
            cls.graph += graph

    def ancestors(self, subject):
        seen, pending = set(), [subject]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(x for x in self.graph.objects(current, RDFS.subClassOf) if isinstance(x, URIRef))
        return seen

    def targets(self, subject, prop):
        return {target for r in self.graph.objects(subject, RDFS.subClassOf)
                if self.graph.value(r, OWL.onProperty) == prop
                for target in self.graph.objects(r, OWL.someValuesFrom)}

    def test_every_process_has_a_discoverable_file_and_overview_parent(self):
        self.assertEqual(self.manifest["process_count"], 37)
        self.assertEqual(self.manifest["subsystem_count"], 9)
        self.assertEqual(len(self.graphs), 38)
        ontology_ids = []
        for row in self.manifest["processes"]:
            g, iri = self.graphs[row["file"]], URIRef(row["iri"])
            ids = list(g.subjects(RDF.type, OWL.Ontology))
            self.assertEqual(len(ids), 1)
            ontology_ids.extend(ids)
            self.assertIn((iri, RDFS.subClassOf, BFO.BFO_0000015), g)
            self.assertIn((iri, RDFS.subClassOf, ABI.LedgerProcess), g)
            self.assertIn((ids[0], OWL.imports, ABI.ABIProcessLedgerOntology), g)
        self.assertEqual(len(set(ontology_ids)), 37)
        self.assertEqual(len(set(self.graph.subjects(RDFS.subClassOf, ABI.LedgerProcess))), 37)

    def test_six_supported_buckets_are_connected_and_typed(self):
        for row in self.manifest["processes"]:
            iri = URIRef(row["iri"])
            for prop, ancestor in (
                (BFO.BFO_0000057, BFO.BFO_0000040),
                (BFO.BFO_0000066, BFO.BFO_0000029),
                (BFO.BFO_0000199, BFO.BFO_0000008),
                (BFO.BFO_0000055, BFO.BFO_0000023),
                (ABI.documentedBy, BFO.BFO_0000031),
            ):
                targets = self.targets(iri, prop)
                self.assertTrue(targets, (row["code"], prop))
                for target in targets:
                    self.assertIn(ancestor, self.ancestors(target), (row["code"], target))
            self.assertTrue(self.targets(iri, ABI.pursuesObjective))
            self.assertTrue(self.targets(iri, ABI.hasExecutionCondition))

    def test_scores_goals_software_and_triggers_are_not_mistyped(self):
        for parent in (ABI.IndicatorRecord, ABI.ObjectiveSpecification, ABI.Software, ABI.ExecutionCondition):
            for subject in self.graph.subjects(RDFS.subClassOf, parent):
                ancestors = self.ancestors(subject)
                self.assertIn(BFO.BFO_0000031, ancestors)
                self.assertFalse(ancestors & {BFO.BFO_0000019, BFO.BFO_0000023, BFO.BFO_0000040, BFO.BFO_0000008})
        self.assertIn(BFO.BFO_0000031, self.ancestors(ABI.OSINTSourceInformation))
        self.assertTrue(self.targets(ABI.HRSystemHost, BFO.BFO_0000101))
        self.assertIn(BFO.BFO_0000040, self.ancestors(ABI.HRSystemHost))

    def test_steps_are_scoped_and_no_runs_or_global_bfo_redefinitions_exist(self):
        steps = set(self.graph.subjects(RDFS.subClassOf, ABI.ProcessStep))
        self.assertEqual(len(steps), 111)
        for step in steps:
            parents = self.targets(step, BFO.BFO_0000132)
            self.assertEqual(len(parents), 1)
            self.assertIn(step, self.targets(next(iter(parents)), BFO.BFO_0000117))
        self.assertFalse(list(self.graph.subjects(RDF.type, OWL.NamedIndividual)))
        self.assertFalse([s for s in self.graph.subjects() if isinstance(s, URIRef) and str(s).startswith(str(BFO))])

    def test_generated_terms_have_definitions_labels_and_draft_status(self):
        for kind in (OWL.Class, OWL.ObjectProperty, OWL.AnnotationProperty):
            for subject in self.graph.subjects(RDF.type, kind):
                if not isinstance(subject, URIRef):
                    continue
                self.assertTrue(list(self.graph.objects(subject, RDFS.label)), subject)
                self.assertTrue(list(self.graph.objects(subject, RDFS.comment)), subject)
                self.assertTrue(list(self.graph.objects(subject, SKOS.definition)), subject)
                if kind == OWL.Class:
                    self.assertTrue(list(self.graph.objects(subject, ABI.modelingStatus)), subject)

    def test_quality_gaps_or_proposals_are_explicit_and_bearers_are_material(self):
        for row in self.manifest["processes"]:
            iri = URIRef(row["iri"])
            quality_targets = self.targets(iri, ABI.hasAssessedQuality)
            self.assertEqual(len(quality_targets), row["qualities"])
            for quality in quality_targets:
                self.assertIn(BFO.BFO_0000019, self.ancestors(quality))
                bearers = self.targets(quality, BFO.BFO_0000197)
                self.assertTrue(bearers)
                for bearer in bearers:
                    self.assertIn(BFO.BFO_0000040, self.ancestors(bearer))
                    self.assertNotIn(BFO.BFO_0000015, self.ancestors(bearer))
            status = str(self.graph.value(iri, ABI.qualityMappingStatus))
            self.assertIn("Proposed" if quality_targets else "Unresolved", status)

    def test_all_original_bucket_values_are_preserved(self):
        source = Path(os.environ.get("ABI_LEDGER_SOURCE", str(ROOT / "source_ledger.json")))
        ledger = builder.read_ledger(source)
        self.assertEqual(ledger["source_sha256"], self.manifest["source_sha256"])
        for subsystem in ledger["subsystems"]:
            for process in subsystem["processes"]:
                iri = ABI[process["code"].replace("-", "")]
                for bucket in builder.BUCKETS:
                    values = {str(x) for x in self.graph.objects(iri, ABI["ledger" + bucket])}
                    self.assertEqual(values, set(process[bucket]), (process["code"], bucket))


if __name__ == "__main__":
    unittest.main()
