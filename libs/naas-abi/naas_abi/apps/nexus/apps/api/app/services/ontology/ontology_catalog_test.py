"""Exercise discovery before dictionary projection, including relocated process files."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService


def service_for(paths: list[Path]) -> OntologyService:
    module = SimpleNamespace(ontologies=[str(path) for path in paths])
    module.engine = SimpleNamespace(modules={"example": module})
    return OntologyService(abi_module_getter=lambda: module)


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_processes_are_discovered_and_workspace_filter_is_applied(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "example" / "ontologies"
            paths = []
            for folder, name in (("modules", "Reference"), ("processes", "Ledger"),
                                 ("sandbox", "Draft"), ("imports", "Dependency")):
                path = root / folder / (name + ".ttl")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
                    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                    @prefix abi: <http://ontology.naas.ai/abi/> .
                    <urn:ontology> a owl:Ontology; rdfs:label "Test ontology" .
                    <urn:system> a owl:Class; abi:systemViewKind "system" .
                ''')
                paths.append(path)
            service = service_for(paths)
            files = await service.list_ontology_files()
            self.assertEqual({Path(item.path).name for item in files}, {"Reference.ttl", "Ledger.ttl"})
            self.assertEqual(len(files), 2)  # registered more than once above
            data = await service.workspace_dictionary(["example:Ledger.ttl"])
            self.assertEqual(data["file_count"], 1)
            self.assertEqual(data["loaded_file_count"], 1)
            self.assertEqual(data["items"][0]["systemViewKind"], "system")
            self.assertEqual(await service.list_ontology_files(catalog_refs=[]), [])

    async def test_abi_process_catalog_contains_system_and_all_processes(self):
        import naas_abi

        root = Path(naas_abi.__file__).parent / "ontologies" / "processes"
        manifest = json.loads((root / "process_ledger_manifest.json").read_text())
        paths = [root / name for name in manifest["files"]]
        service = service_for(paths)
        data = await service.workspace_dictionary(["naas_abi:" + path.name for path in paths])
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["file_count"], 38)
        self.assertEqual(data["loaded_file_count"], 38)
        systems = [term for term in data["items"] if term["systemViewKind"] == "system"]
        self.assertEqual([term["id"] for term in systems], ["http://ontology.naas.ai/abi/LedgerProcess"])
        self.assertEqual(sum(term["systemViewKind"] == "subsystem" for term in data["items"]), 9)
        self.assertEqual(sum(bool(term["processLedger"]) for term in data["items"]), 37)


if __name__ == "__main__":
    unittest.main()
