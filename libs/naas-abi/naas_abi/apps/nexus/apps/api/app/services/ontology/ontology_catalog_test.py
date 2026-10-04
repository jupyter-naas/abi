"""Exercise discovery before dictionary projection: ontologies are listed, process slices are not."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from naas_abi.apps.nexus.apps.api.app.services.ontology import service as ontology_service_module
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService


class MemoryCache:
    """Stand-in for the filesystem bucket cache, so tests never touch storage/."""

    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    def get(self, key: str) -> dict:
        return self.data[key]

    def set_json(self, key: str, value: dict) -> None:
        self.data[key] = value

    def exists(self, key: str) -> bool:
        return key in self.data

    def delete(self, key: str) -> None:
        del self.data[key]


def service_for(paths: list[Path]) -> OntologyService:
    module = SimpleNamespace(ontologies=[str(path) for path in paths])
    module.engine = SimpleNamespace(modules={"example": module})
    return OntologyService(abi_module_getter=lambda: module)


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.cache = MemoryCache()
        patcher = patch.object(ontology_service_module, "_bfo_bucket_cache", self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_ontologies_are_discovered_and_process_slices_are_not(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "example" / "ontologies"
            paths = []
            for folder, name in (("modules", "Reference"), ("processes", "Ledger"),
                                 ("sandbox", "Draft"), ("imports", "Dependency"),
                                 ("queries", "Queries")):
                path = root / folder / (name + ".ttl")
                path.parent.mkdir(parents=True, exist_ok=True)
                header = "" if name == "Queries" else '<urn:ontology> a owl:Ontology; rdfs:label "Test ontology" .'
                path.write_text(f'''@prefix owl: <http://www.w3.org/2002/07/owl#> .
                    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                    @prefix abi: <http://ontology.naas.ai/abi/> .
                    {header}
                    <urn:system> a owl:Class; abi:systemViewKind "system" .
                ''')
                paths.append(path)
            service = service_for(paths)
            files = await service.list_ontology_files()
            # Any ontologies/**/*.ttl declaring owl:Ontology, except process
            # slices (consolidated into modules/) and sandbox drafts.
            self.assertEqual({Path(item.path).name for item in files}, {"Reference.ttl", "Dependency.ttl"})
            self.assertEqual(len(files), 2)  # registered more than once above
            data = await service.workspace_dictionary(["example:Reference.ttl"])
            self.assertEqual(data["file_count"], 1)
            self.assertEqual(data["loaded_file_count"], 1)
            self.assertEqual(data["items"][0]["systemViewKind"], "system")
            self.assertEqual([item["id"] for item in data["ontologies"]], ["urn:ontology"])
            self.assertEqual(data["ontologies"][0]["metadata"]["label"], [str(root / "modules" / "Reference.ttl")])
            self.assertEqual((await service.workspace_dictionary([]))["ontologies"], [])
            self.assertEqual(await service.list_ontology_files(catalog_refs=[]), [])

    async def test_dictionary_entities_carry_bfo_bucket_through_imports(self):
        # Neither class names a BFO root in the workspace file: the bucket is
        # only reachable through the bundled CCO import (Planned Act -> process)
        # or an equivalence to a CCO class.
        with TemporaryDirectory() as directory:
            path = Path(directory) / "example" / "ontologies" / "modules" / "Work.ttl"
            path.parent.mkdir(parents=True)
            path.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                @prefix cco: <https://www.commoncoreontologies.org/> .
                <urn:work> a owl:Ontology ;
                    owl:imports <https://www.commoncoreontologies.org/EventOntology> ,
                                <https://www.commoncoreontologies.org/AgentOntology> .
                <urn:ActOfWorking> a owl:Class ; rdfs:subClassOf cco:ont00000228 .
                <urn:Human> a owl:Class ; owl:equivalentClass cco:ont00001262 .
                <urn:Orphan> a owl:Class ; rdfs:subClassOf <urn:Nowhere> .
            ''')
            data = await service_for([path]).workspace_dictionary(["example:Work.ttl"])
            buckets = {item["id"]: item.get("bfoBucket") for item in data["items"] if item["type"] == "entity"}
            self.assertEqual(buckets["urn:ActOfWorking"], "http://purl.obolibrary.org/obo/BFO_0000015")
            self.assertEqual(buckets["urn:Human"], "http://purl.obolibrary.org/obo/BFO_0000040")
            self.assertIsNone(buckets["urn:Orphan"])

    async def test_referenced_classes_get_label_and_bucket_from_imports(self):
        # cco:ont00000468 (Office Building) is only declared in the bundled CCO
        # FacilityOntology: its label and bucket come from the import.
        with TemporaryDirectory() as directory:
            path = Path(directory) / "example" / "ontologies" / "modules" / "Work.ttl"
            path.parent.mkdir(parents=True)
            path.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                @prefix cco: <https://www.commoncoreontologies.org/> .
                <urn:work> a owl:Ontology ;
                    owl:imports <https://www.commoncoreontologies.org/FacilityOntology> .
                <urn:Desk> a owl:Class ; rdfs:label "Desk" ; rdfs:subClassOf cco:ont00000468 .
            ''')
            service = service_for([path])
            data = await service.workspace_dictionary(["example:Work.ttl"])
            desk = next(item for item in data["items"] if item["id"] == "urn:Desk")
            office = desk["parents"][0]
            self.assertEqual(office["id"], "https://www.commoncoreontologies.org/ont00000468")
            self.assertEqual(office["name"], "Office Building")
            self.assertEqual(office["bfoBucket"], "http://purl.obolibrary.org/obo/BFO_0000040")
            self.assertEqual(desk["bfoBucket"], "http://purl.obolibrary.org/obo/BFO_0000040")

            # Known buckets are served from the cache, without walking the graph again.
            with patch.object(ontology_service_module, "_bfo_bucket", side_effect=AssertionError("walked")):
                cached = await service.workspace_dictionary(["example:Work.ttl"])
            self.assertEqual(
                next(item for item in cached["items"] if item["id"] == "urn:Desk")["bfoBucket"],
                "http://purl.obolibrary.org/obo/BFO_0000040",
            )

            # Refresh forgets the cached value and resolves it again.
            key = "bfo_bucket:urn:Desk"
            self.cache.set_json(key, {"bucket": "http://purl.obolibrary.org/obo/BFO_0000015"})
            refreshed = await service.refresh_bfo_bucket("urn:Desk", ["example:Work.ttl"])
            self.assertEqual(refreshed, "http://purl.obolibrary.org/obo/BFO_0000040")
            self.assertEqual(self.cache.data[key]["bucket"], refreshed)

    async def test_unresolved_and_entity_only_buckets_are_not_cached(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "example" / "ontologies" / "modules" / "Loose.ttl"
            path.parent.mkdir(parents=True)
            path.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                <urn:loose> a owl:Ontology .
                <urn:Orphan> a owl:Class ; rdfs:subClassOf <urn:Nowhere> .
                <urn:Vague> a owl:Class ; rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000001> .
            ''')
            data = await service_for([path]).workspace_dictionary(["example:Loose.ttl"])
            buckets = {item["id"]: item["bfoBucket"] for item in data["items"] if item["type"] == "entity"}
            self.assertIsNone(buckets["urn:Orphan"])
            self.assertEqual(buckets["urn:Vague"], "http://purl.obolibrary.org/obo/BFO_0000001")
            self.assertEqual(self.cache.data, {})

    async def test_abi_process_catalog_contains_system_and_all_processes(self):
        import naas_abi

        ontologies = Path(naas_abi.__file__).parent / "ontologies"
        manifest = json.loads((ontologies / "processes" / "process_ledger_manifest.json").read_text())
        slices = [ontologies / "processes" / name for name in manifest["files"]]
        consolidated = ontologies / "modules" / "NaasAbiOntology.ttl"
        service = service_for([*slices, consolidated])
        # The slices are not listed; their consolidation carries the whole ledger.
        files = await service.list_ontology_files()
        self.assertEqual([Path(item.path) for item in files], [consolidated])
        data = await service.workspace_dictionary(["naas_abi:" + consolidated.name])
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["file_count"], 1)
        self.assertEqual(data["loaded_file_count"], 1)
        systems = [term for term in data["items"] if term["systemViewKind"] == "system"]
        self.assertEqual([term["id"] for term in systems], ["http://ontology.naas.ai/abi/LedgerProcess"])
        self.assertEqual(sum(term["systemViewKind"] == "subsystem" for term in data["items"]), 9)
        self.assertEqual(sum(bool(term["processLedger"]) for term in data["items"]), 37)


if __name__ == "__main__":
    unittest.main()
