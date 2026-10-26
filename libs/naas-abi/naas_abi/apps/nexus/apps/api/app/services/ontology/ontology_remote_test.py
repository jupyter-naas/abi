"""Remote modules' ontologies in the catalog, read from a fake schema graph."""

import base64
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary import (
    ontology__primary_adapter__FastAPI as http,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary.ontology__primary_adapter__dependencies import (
    get_ontology_service,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyFileNotFoundError,
    OntologyPathNotFoundError,
    OntologyServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_imports import (
    clear_catalog_import_caches,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_source import (
    RemoteOntologyReader,
    install_reader,
    parse_remote_id,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService
from rdflib import RDF, Dataset, Literal, URIRef

SCHEMA_GRAPH = URIRef("http://ontology.naas.ai/graph/schema")
INTERNAL = "http://triple-store.internal#"

PREFIXES = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
"""

REPORTS = PREFIXES + """
<http://example.com/reports> a owl:Ontology ;
    dcterms:title "Reports ontology" ;
    owl:imports <http://example.com/base> .
<http://example.com/reports#Report> a owl:Class ; rdfs:label "Report" .
<http://example.com/reports#Section> a owl:Class ; rdfs:label "Section" ;
    rdfs:subClassOf <http://example.com/reports#Report> .
<http://example.com/reports#hasSection> a owl:ObjectProperty ; rdfs:label "has section" .
"""
HEADERLESS = PREFIXES + "<http://example.com/x#Thing> a owl:Class .\n"
SANDBOX = PREFIXES + '<http://example.com/draft> a owl:Ontology ; rdfs:label "Draft" .\n'
SLICE = PREFIXES + '<http://example.com/slice> a owl:Ontology ; rdfs:label "Slice" .\n'

REPORTS_ID = "module/acme.reports/modules/ReportsOntology.ttl"
LOCAL = PREFIXES + """
<http://example.com/local> a owl:Ontology ; rdfs:label "Local ontology" .
<http://example.com/local#Thing> a owl:Class ; rdfs:label "Thing" .
"""


class FakeTripleStore:
    """A schema graph answering the reader's SPARQL, counting its queries."""

    def __init__(self, files: dict[str, str]) -> None:
        self.dataset = Dataset()
        self.queries = 0
        graph = self.dataset.graph(SCHEMA_GRAPH)
        for index, (path, text) in enumerate(files.items()):
            subject = URIRef(f"http://ontology.naas.ai/schema/{index}")
            graph.add((subject, RDF.type, URIRef(INTERNAL + "Schema")))
            graph.add((subject, URIRef(INTERNAL + "filePath"), Literal(path)))
            graph.add(
                (
                    subject,
                    URIRef(INTERNAL + "content"),
                    Literal(base64.b64encode(text.encode()).decode()),
                )
            )

    def query(self, query: str):
        self.queries += 1
        return self.dataset.query(query)


REMOTE_FILES = {
    REPORTS_ID: REPORTS,
    "module/acme.reports/modules/Headerless.ttl": HEADERLESS,
    "module/acme.reports/sandbox/Draft.ttl": SANDBOX,
    "module/acme.reports/processes/Ledger.ttl": SLICE,
    # In-engine files share the schema graph, under their disk path.
    "/srv/abi/example/ontologies/modules/Local.ttl": LOCAL,
}


def service_with(store: FakeTripleStore | None, disk: list[Path] | None = None) -> OntologyService:
    module = SimpleNamespace(ontologies=[str(path) for path in disk or []])
    module.engine = SimpleNamespace(modules={})
    return OntologyService(
        triple_store_getter=(lambda: store) if store is not None else None,
        abi_module_getter=lambda: module,
    )


class RemoteIdTests(unittest.TestCase):
    def test_well_formed_ids(self) -> None:
        self.assertEqual(
            parse_remote_id("module/acme.reports/modules/A.ttl"),
            ("acme.reports", "modules/A.ttl"),
        )
        self.assertEqual(parse_remote_id("module/a:b/A.ttl"), ("a:b", "A.ttl"))

    def test_traversal_and_malformed_ids_are_rejected(self) -> None:
        for bad in (
            "module/../etc/passwd",
            "module/acme/../../etc/passwd",
            "module/acme/./A.ttl",
            "module/acme//A.ttl",
            "module//A.ttl",
            "module/acme",
            "module/acme/",
            "module/acme\\A.ttl",
            "module/acme/A.ttl\x00.png",
            "module/acme/A\n.ttl",
            "/etc/passwd",
            "modules/acme/A.ttl",
            "",
        ):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_remote_id(bad))


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        clear_catalog_import_caches()
        self.addCleanup(clear_catalog_import_caches)
        self.addCleanup(install_reader, None)
        self.store = FakeTripleStore(REMOTE_FILES)
        self.service = service_with(self.store)

    async def test_remote_ontology_is_listed_with_title_module_and_imports(self) -> None:
        files = await self.service.list_ontology_files()
        self.assertEqual(len(files), 1)
        item = files[0]
        self.assertEqual(item.path, REPORTS_ID)
        self.assertEqual(item.name, "Reports ontology")
        self.assertEqual(item.module_name, "acme.reports")
        self.assertEqual(item.imports, ["http://example.com/base"])

    async def test_remote_files_without_ontology_header_sandbox_and_processes_are_skipped(
        self,
    ) -> None:
        paths = {item.path for item in await self.service.list_ontology_files()}
        self.assertEqual(paths, {REPORTS_ID})

    async def test_in_engine_listing_is_unchanged_next_to_remote_ones(self) -> None:
        with TemporaryDirectory() as directory:
            local = Path(directory) / "example" / "ontologies" / "modules" / "Local.ttl"
            local.parent.mkdir(parents=True)
            local.write_text(LOCAL)
            files = await service_with(self.store, [local]).list_ontology_files()
            self.assertEqual(
                [(item.path, item.module_name) for item in files],
                [(REPORTS_ID, "acme.reports"), (str(local), "example")],
            )
            # Without a reachable schema graph the in-engine files still list.
            files = await service_with(None, [local]).list_ontology_files()
            self.assertEqual([item.path for item in files], [str(local)])

    async def test_catalog_refs_match_remote_module_names(self) -> None:
        for ref in (
            "acme.reports:ReportsOntology.ttl",
            "ACME.reports:reportsontology.ttl",
            REPORTS_ID,
        ):
            with self.subTest(ref=ref):
                files = await self.service.list_ontology_files(catalog_refs=[ref])
                self.assertEqual([item.path for item in files], [REPORTS_ID])
        # Not by the bare file name, nor by a path suffix: another module could
        # push a file of the same name, and would be admitted.
        for ref in (
            "ReportsOntology.ttl",
            "modules/ReportsOntology.ttl",
            "other:ReportsOntology.ttl",
            "acme.reports:Other.ttl",
        ):
            with self.subTest(ref=ref):
                self.assertEqual(await self.service.list_ontology_files(catalog_refs=[ref]), [])
        self.assertEqual(await self.service.list_ontology_files(catalog_refs=[]), [])

    async def test_a_workspace_enabling_a_file_does_not_list_another_modules_remote_one(
        self,
    ) -> None:
        evil_id = "module/evil/modules/ReportsOntology.ttl"
        service = service_with(FakeTripleStore({**REMOTE_FILES, evil_id: REPORTS}))

        everything = {item.path for item in await service.list_ontology_files()}
        self.assertEqual(everything, {REPORTS_ID, evil_id})
        for refs in (["ReportsOntology.ttl"], ["modules/ReportsOntology.ttl"]):
            self.assertEqual(await service.list_ontology_files(catalog_refs=refs), [])
        enabled = await service.list_ontology_files(
            catalog_refs=["acme.reports:ReportsOntology.ttl"]
        )
        self.assertEqual([item.path for item in enabled], [REPORTS_ID])
        with self.assertRaises(OntologyPathNotFoundError):
            await http._require_catalog_path(
                evil_id, ["acme.reports:ReportsOntology.ttl"], service
            )

    async def test_listing_reads_the_schema_graph_once_and_parses_a_file_once(
        self,
    ) -> None:
        with patch.object(
            OntologyService, "_file_item", autospec=True, side_effect=OntologyService._file_item
        ) as file_item:
            await self.service.list_ontology_files()
            await self.service.list_ontology_files(catalog_refs=[REPORTS_ID])
            await self.service.list_ontology_files()
        # One query for every file's text, then the cache.
        self.assertEqual(self.store.queries, 1)
        # The titled file and the one without an ontology header: once each.
        self.assertEqual(file_item.call_count, 2)

    async def test_overview_stats_listings_and_counts_read_the_stored_text(self) -> None:
        stats = await self.service.get_overview_stats(REPORTS_ID)
        self.assertEqual(stats.name, "ReportsOntology.ttl")
        self.assertEqual(stats.path, REPORTS_ID)
        self.assertEqual((stats.classes, stats.object_properties), (2, 1))
        classes = await self.service.list_classes(REPORTS_ID)
        self.assertEqual([item.name for item in classes], ["Report", "Section"])
        relations = await self.service.list_relations(REPORTS_ID)
        self.assertEqual([item.name for item in relations], ["has section"])
        counts = await self.service.get_type_counts(REPORTS_ID)
        self.assertEqual(counts.path, REPORTS_ID)
        everything = await self.service.get_all_overview_stats()
        self.assertEqual((everything.ontologies_count, everything.classes), (1, 2))
        graph = await self.service.get_overview_graph(REPORTS_ID)
        self.assertTrue(any(node.label == "Section" for node in graph.nodes))
        overview = await self.service.get_overview_graph(None)
        self.assertTrue(any(node.type == "Ontology" for node in overview.nodes))

    async def test_workspace_dictionary_includes_remote_entries(self) -> None:
        data = await self.service.workspace_dictionary(["acme.reports:ReportsOntology.ttl"])
        self.assertEqual((data["file_count"], data["loaded_file_count"]), (1, 1))
        self.assertEqual(data["errors"], [])
        self.assertEqual(
            {item["id"] for item in data["items"]},
            {
                "http://example.com/reports#Report",
                "http://example.com/reports#Section",
                "http://example.com/reports#hasSection",
            },
        )
        self.assertEqual(await self.service.process_slices(REPORTS_ID, None), [])

    async def test_export_returns_the_stored_text(self) -> None:
        export = await self.service.export_ontology(REPORTS_ID)
        self.assertEqual(export.filename, "ReportsOntology.ttl")
        self.assertIsNone(export.path)
        self.assertEqual(export.content, REPORTS.encode())
        with self.assertRaises(OntologyPathNotFoundError):
            await self.service.export_ontology("module/acme.reports/modules/Missing.ttl")


class DiskIsNeverReadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        clear_catalog_import_caches()
        self.addCleanup(clear_catalog_import_caches)
        self.addCleanup(install_reader, None)
        self.service = service_with(FakeTripleStore(REMOTE_FILES))

    async def test_a_remote_id_cannot_read_a_file_on_disk(self) -> None:
        # A file sits at the very path the id spells, relative to the cwd, and
        # another one is reachable by traversal: neither may be read.
        with TemporaryDirectory() as directory:
            secret = PREFIXES + '<http://example.com/secret> a owl:Ontology ; rdfs:label "Secret" .\n'
            (Path(directory) / "module" / "acme.reports" / "modules").mkdir(parents=True)
            (Path(directory) / "module" / "acme.reports" / "modules" / "OnDisk.ttl").write_text(secret)
            (Path(directory) / "outside.ttl").write_text(secret)
            before = Path.cwd()
            os.chdir(directory)
            try:
                for bad in (
                    "module/acme.reports/modules/OnDisk.ttl",
                    "module/acme.reports/../../outside.ttl",
                    f"module/../{directory}/outside.ttl",
                ):
                    with self.subTest(bad=bad):
                        with self.assertRaises(OntologyPathNotFoundError):
                            await self.service.export_ontology(bad)
                        with self.assertRaises(OntologyServiceUnavailableError):
                            await self.service.get_overview_stats(bad)
                        with self.assertRaises(OntologyPathNotFoundError):
                            await self.service.list_classes(bad)
                        with self.assertRaises(OntologyFileNotFoundError):
                            await self.service.export_ontology_file(bad)
                self.assertNotIn(
                    "http://example.com/secret",
                    [i.id for i in await self.service.list_classes(None)],
                )
            finally:
                os.chdir(before)

    async def test_an_in_engine_path_shaped_like_a_remote_id_is_not_opened(self) -> None:
        with TemporaryDirectory() as directory:
            disguised = Path(directory) / "module" / "evil" / "ontologies" / "A.ttl"
            disguised.parent.mkdir(parents=True)
            disguised.write_text(LOCAL)
            before = Path.cwd()
            os.chdir(directory)
            try:
                module = SimpleNamespace(ontologies=["module/evil/ontologies/A.ttl"])
                module.engine = SimpleNamespace(modules={})
                service = OntologyService(
                    triple_store_getter=lambda: FakeTripleStore({}),
                    abi_module_getter=lambda: module,
                )
                self.assertEqual(await service.list_ontology_files(), [])
            finally:
                os.chdir(before)


class ReaderCacheTests(unittest.TestCase):
    def test_reads_are_cached_briefly_and_the_cache_is_bounded(self) -> None:
        store = FakeTripleStore(
            {f"module/m/File{index}.ttl": REPORTS for index in range(5)}
        )
        now = [0.0]
        reader = RemoteOntologyReader(
            lambda: store, ttl_seconds=10.0, max_entries=2, clock=lambda: now[0]
        )
        self.assertEqual(len(reader.sources()), 5)
        reader.sources()
        self.assertEqual(store.queries, 1)
        reader.read("module/m/File0.ttl")
        reader.read("module/m/File0.ttl")
        self.assertEqual(store.queries, 2)
        reader.read("module/m/File1.ttl")
        reader.read("module/m/File2.ttl")  # evicts File0
        self.assertEqual(store.queries, 4)
        reader.read("module/m/File0.ttl")
        self.assertEqual(store.queries, 5)
        # A change a module pushes shows once the entry expires.
        now[0] = 11.0
        reader.sources()
        reader.read("module/m/File0.ttl")
        self.assertEqual(store.queries, 7)

    def test_ids_the_store_holds_but_are_malformed_are_not_listed(self) -> None:
        store = FakeTripleStore(
            {"module/m/A.ttl": REPORTS, "module/m/../B.ttl": REPORTS, "/abs/C.ttl": REPORTS}
        )
        self.assertEqual(RemoteOntologyReader(lambda: store).sources(), ["module/m/A.ttl"])

    def test_a_quote_in_an_id_cannot_widen_the_query(self) -> None:
        store = FakeTripleStore({"module/m/A.ttl": REPORTS})
        reader = RemoteOntologyReader(lambda: store)
        with self.assertRaises(OntologyPathNotFoundError):
            reader.read('module/m/A.ttl" . ?s ?p ?o . FILTER("')


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        clear_catalog_import_caches()
        self.addCleanup(clear_catalog_import_caches)
        self.addCleanup(install_reader, None)
        self.service = service_with(FakeTripleStore(REMOTE_FILES))
        self.app = FastAPI()
        self.app.include_router(http.router, prefix="/api/ontology")
        self.app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
            id="viewer"
        )
        self.app.dependency_overrides[get_ontology_service] = lambda: self.service
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url="http://test")
        for patcher in (
            patch.object(http, "require_workspace_access", new=AsyncMock()),
            patch.object(
                http,
                "_catalog_refs_for_workspace",
                new=AsyncMock(return_value=["acme.reports:ReportsOntology.ttl"]),
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_listing_shows_the_remote_ontology(self) -> None:
        response = await self.client.get("/api/ontology/ontologies?workspace_id=w")
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["path"], REPORTS_ID)
        self.assertEqual(items[0]["name"], "Reports ontology")
        self.assertEqual(items[0]["module_name"], "acme.reports")
        self.assertEqual(items[0]["imports"], ["http://example.com/base"])

    async def test_stats_and_export_work_for_the_remote_ontology(self) -> None:
        response = await self.client.get(
            "/api/ontology/overview/stats",
            params={"workspace_id": "w", "ontology_path": REPORTS_ID},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["classes"], 2)
        response = await self.client.get(
            "/api/ontology/export", params={"workspace_id": "w", "ontology_path": REPORTS_ID}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, REPORTS.encode())
        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="ReportsOntology.ttl"',
        )

    async def test_export_refuses_what_the_workspace_catalog_does_not_list(self) -> None:
        for path in (
            "module/acme.reports/modules/Headerless.ttl",
            "module/../../etc/passwd",
            "module/acme.reports/../../../etc/passwd",
        ):
            with self.subTest(path=path):
                response = await self.client.get(
                    "/api/ontology/export", params={"workspace_id": "w", "ontology_path": path}
                )
                self.assertEqual(response.status_code, 404, response.text)


if __name__ == "__main__":
    unittest.main()
