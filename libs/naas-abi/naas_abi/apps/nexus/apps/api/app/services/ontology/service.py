from __future__ import annotations

import os
import re
import traceback
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyFileItemData,
    OntologyItemData,
    OntologyOverviewAggregateStatsData,
    OntologyOverviewGraphData,
    OntologyOverviewGraphEdgeData,
    OntologyOverviewGraphNodeData,
    OntologyOverviewStatsData,
    OntologyParseError,
    OntologyPathNotFoundError,
    OntologyServiceUnavailableError,
    OntologyTypeCountsData,
    ReferenceClassData,
    ReferenceOntologyData,
    ReferencePropertyData,
)
from naas_abi_core import logger
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.query import ResultRow
from rdflib.term import URIRef

_cache = CacheFactory.CacheFS_find_storage(subpath="nexus/ontology")


# ── Pure utility functions ────────────────────────────────────────────────────


def _load_ontology_graph(ontology_path: str, add_imports: bool = False) -> Graph:
    extension = Path(ontology_path).suffix.lower()
    parse_format = {
        ".ttl": "turtle",
        ".owl": "xml",
        ".rdf": "xml",
        ".nt": "nt",
    }.get(extension)

    graph = Graph()
    try:
        graph.parse(ontology_path, format=parse_format)
    except Exception:
        graph.parse(ontology_path)

    if add_imports:
        for import_uri in graph.objects(None, OWL.imports):
            graph_imports = Graph()
            try:
                import_path = str(import_uri)
                import_extension = Path(import_path).suffix.lower()
                import_parse_format = {
                    ".ttl": "turtle",
                    ".owl": "xml",
                    ".rdf": "xml",
                    ".nt": "nt",
                }.get(import_extension)
                graph_imports.parse(import_path, format=import_parse_format)
            except Exception as e:
                logger.error(f"Error parsing import {import_uri}: {e}")
                continue
            graph += graph_imports
    return graph


def _compute_ontology_stats_for_graph(graph: Graph) -> tuple[int, int, int, int, int]:
    """Return (classes, object_properties, data_properties, named_individuals, imports)."""

    def _count_iri_subjects(rdf_type: URIRef) -> int:
        return len(
            {s for s in graph.subjects(RDF.type, rdf_type) if isinstance(s, URIRef)}
        )

    return (
        _count_iri_subjects(OWL.Class),
        _count_iri_subjects(OWL.ObjectProperty),
        _count_iri_subjects(OWL.DatatypeProperty),
        _count_iri_subjects(OWL.NamedIndividual),
        len(set(graph.objects(None, OWL.imports))),
    )


def _parse_ttl(content: str, file_path: str) -> ReferenceOntologyData:
    """Parse TTL/Turtle format ontology content."""
    classes: list[ReferenceClassData] = []
    properties: list[ReferencePropertyData] = []

    class_pattern = r"<([^>]+)>\s+a\s+owl:Class\s*;([^.]+)\."
    for match in re.finditer(class_pattern, content, re.DOTALL):
        iri = match.group(1)
        body = match.group(2)
        label_match = re.search(r'rdfs:label\s+"([^"]+)"', body)
        label = label_match.group(1) if label_match else iri.split("/")[-1]
        def_match = re.search(r'skos:definition\s+"([^"]+)"', body)
        definition = def_match.group(1) if def_match else None
        example_match = re.search(r'skos:example\s+"([^"]+)"', body)
        examples = example_match.group(1) if example_match else None
        classes.append(ReferenceClassData(iri=iri, label=label, definition=definition, examples=examples))

    prop_pattern = r"<([^>]+)>\s+rdf:type\s+owl:ObjectProperty\s*;?([^.]*)\."
    for match in re.finditer(prop_pattern, content, re.DOTALL):
        iri = match.group(1)
        body = match.group(2)
        label_match = re.search(r'rdfs:label\s+"([^"]+)"', body)
        label = label_match.group(1) if label_match else iri.split("/")[-1]
        def_match = re.search(r'skos:definition\s+"([^"]+)"', body)
        definition = def_match.group(1) if def_match else None
        properties.append(ReferencePropertyData(iri=iri, label=label, definition=definition))

    name_match = re.search(r'dc:title\s+"([^"]+)"', content)
    name = name_match.group(1) if name_match else os.path.basename(file_path).replace(".ttl", "")

    return ReferenceOntologyData(
        id=f"ref-{int(datetime.now().timestamp() * 1000)}",
        name=name,
        file_path=file_path,
        format="ttl",
        classes=classes,
        properties=properties,
        imported_at=datetime.now(),
    )


# ── Cached triple-store helpers (module-level to keep cache decorator) ────────


@_cache(
    lambda triple_store, uri: f"metadata_uri_{uri}",
    DataType.JSON,
    ttl=timedelta(days=1),
)
def _get_uri_metadata(triple_store: TripleStoreService, uri: str) -> dict:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?label ?definition ?example ?subClassOf ?subPropertyOf ?comment
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            OPTIONAL {{ <{uri}> rdfs:label ?label . }}
            OPTIONAL {{ <{uri}> skos:definition ?definition . }}
            OPTIONAL {{ <{uri}> skos:example ?example . }}
            OPTIONAL {{ <{uri}> rdfs:comment ?comment . }}
            OPTIONAL {{
                <{uri}> rdfs:subClassOf ?subClassOf .
                FILTER(isIRI(?subClassOf))
            }}
            OPTIONAL {{
                <{uri}> rdfs:subPropertyOf ?subPropertyOf .
                FILTER(isIRI(?subPropertyOf))
            }}
        }}
    }}
    """
    result: dict = {}
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        result = {
            "label": str(row.label) if row.label else uri,
            "definition": str(row.definition) if row.definition else None,
            "example": str(row.example) if row.example else None,
            "subClassOf": str(row.subClassOf) if row.subClassOf else None,
            "subPropertyOf": str(row.subPropertyOf) if row.subPropertyOf else None,
            "comment": str(row.comment) if row.comment else None,
        }
    return result


def _get_ontology_metadata(triple_store: TripleStoreService, ontology_iri: str) -> dict:
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dc: <http://purl.org/dc/terms/>
    PREFIX dc11: <http://purl.org/dc/elements/1.1/>
    SELECT ?label ?comment ?versionInfo ?title ?description ?license ?date
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            <{ontology_iri}> rdf:type owl:Ontology .
            OPTIONAL {{ <{ontology_iri}> rdfs:label ?label . }}
            OPTIONAL {{ <{ontology_iri}> rdfs:comment ?comment . }}
            OPTIONAL {{ <{ontology_iri}> owl:versionInfo ?versionInfo . }}
            OPTIONAL {{ <{ontology_iri}> dc:title ?title . }}
            OPTIONAL {{ <{ontology_iri}> dc:description ?description . }}
            OPTIONAL {{ <{ontology_iri}> dc:license ?license . }}
            OPTIONAL {{ <{ontology_iri}> dc11:date ?date . }}
        }}
    }}
    """
    result: dict = {}
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        result.update({
            "label": str(row.label) if getattr(row, "label", None) else None,
            "comment": str(row.comment) if getattr(row, "comment", None) else None,
            "versionInfo": str(row.versionInfo) if getattr(row, "versionInfo", None) else None,
            "title": str(row.title) if getattr(row, "title", None) else None,
            "description": str(row.description) if getattr(row, "description", None) else None,
            "license": str(row.license) if getattr(row, "license", None) else None,
            "date": str(row.date) if getattr(row, "date", None) else None,
        })
    return result


# ── Service ───────────────────────────────────────────────────────────────────


class OntologyService:
    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
        abi_module_getter: Callable[[], Any] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter
        self._abi_module_getter = abi_module_getter
        # In-memory storage (replace with persistence later)
        self._ontology_items: list[OntologyItemData] = []

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_triple_store(self) -> TripleStoreService:
        if self._triple_store_getter is not None:
            return self._triple_store_getter()
        try:
            from naas_abi import ABIModule
            return ABIModule.get_instance().engine.services.triple_store
        except Exception as exc:
            raise OntologyServiceUnavailableError(
                "Triple store is not initialized. Load API through naas_abi.ABIModule."
            ) from exc

    def _get_abi_module(self) -> Any:
        if self._abi_module_getter is not None:
            return self._abi_module_getter()
        try:
            from naas_abi import ABIModule
            return ABIModule.get_instance()
        except Exception as exc:
            raise OntologyServiceUnavailableError(
                "ABIModule is not initialized."
            ) from exc

    def _resolve_ontology_paths(
        self, ontology_path: str | None, ontologies: list[OntologyFileItemData]
    ) -> list[str]:
        all_paths = [item.path for item in ontologies]
        if ontology_path:
            if ontology_path not in all_paths:
                raise OntologyPathNotFoundError(f"Ontology path not found: {ontology_path}")
            return [ontology_path]
        return all_paths

    # ── Public API ────────────────────────────────────────────────────────────

    async def list_items(self) -> list[OntologyItemData]:
        """List all ontology items (OWL Classes and Object Properties)."""
        classes = await self.list_classes(ontology_path=None)
        relations = await self.list_relations(ontology_path=None)
        return [*classes, *relations]

    async def list_classes(self, ontology_path: str | None) -> list[OntologyItemData]:
        """List ontology classes (owl:Class) across registered ontology files."""
        store = self._get_triple_store()
        ontologies = await self.list_ontology_files()
        target_paths = self._resolve_ontology_paths(ontology_path, ontologies)
        by_iri: dict[str, OntologyItemData] = {}

        query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?s WHERE {
                ?s rdf:type owl:Class .
                FILTER(isIRI(?s))
            }
        """
        for path in target_paths:
            graph = _load_ontology_graph(path)
            for row in graph.query(query):
                assert isinstance(row, ResultRow)
                iri = str(row.get("s"))
                if iri in by_iri:
                    continue
                data = _get_uri_metadata(store, iri)
                label = data.get("label", "Unknown")
                definition = data.get("definition")
                comment = data.get("comment", "Unknown")
                example = data.get("example", "Unknown")
                parent_id = data.get("subClassOf", "Unknown")
                parent_data = _get_uri_metadata(store, parent_id) if parent_id else None
                parent_label = parent_data.get("label", "Unknown") if parent_data else None
                by_iri[iri] = OntologyItemData(
                    id=iri,
                    name=label,
                    type="Class",
                    description=str(definition) if definition else str(comment),
                    example=str(example),
                    parent_id=str(parent_id),
                    parent_name=str(parent_label),
                )
        return sorted(by_iri.values(), key=lambda item: item.name.lower())

    async def list_relations(self, ontology_path: str | None) -> list[OntologyItemData]:
        """List ontology object properties (owl:ObjectProperty) across registered ontology files."""
        store = self._get_triple_store()
        ontologies = await self.list_ontology_files()
        target_paths = self._resolve_ontology_paths(ontology_path, ontologies)
        by_iri: dict[str, OntologyItemData] = {}

        query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?s WHERE {
                ?s rdf:type owl:ObjectProperty .
                FILTER(isIRI(?s))
            }
        """
        for path in target_paths:
            graph = _load_ontology_graph(path)
            for row in graph.query(query):
                assert isinstance(row, ResultRow)
                iri = str(row.get("s"))
                if iri in by_iri:
                    continue
                data = _get_uri_metadata(store, iri)
                label = data.get("label", "Unknown")
                definition = data.get("definition", "Unknown")
                comment = data.get("comment", "Unknown")
                parent_id = data.get("subPropertyOf", "Unknown")
                parent_data = _get_uri_metadata(store, parent_id) if parent_id else None
                parent_label = parent_data.get("label", "Unknown") if parent_data else None
                by_iri[iri] = OntologyItemData(
                    id=iri,
                    name=label,
                    type="Object Property",
                    description=str(definition) if definition else str(comment),
                    parent_id=str(parent_id),
                    parent_name=str(parent_label),
                )
        return sorted(by_iri.values(), key=lambda item: item.name.lower())

    async def list_ontology_files(self) -> list[OntologyFileItemData]:
        """List ontology files from all registered modules."""
        from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

        try:
            abi_module = self._get_abi_module()
            abi_ontologies: list[str] = list(abi_module.ontologies)
            for module in abi_module.engine.modules.values():
                abi_ontologies.extend(module.ontologies)

            ontology_files: list[OntologyFileItemData] = []
            seen: set[str] = set()

            for ontology in abi_ontologies:
                if ontology in seen:
                    continue
                seen.add(ontology)

                if "sandbox" in ontology.lower() or "modules" not in ontology.lower():
                    continue

                ontology_graph = Graph()
                ontology_graph.parse(ontology, format="turtle")

                ontology_uri = next(ontology_graph.subjects(RDF.type, OWL.Ontology), None)
                if ontology_uri is None:
                    continue

                title = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.title)
                label = ontology_graph.value(URIRef(str(ontology_uri)), RDFS.label)
                description = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.description)
                license_val = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.license)
                contributors = list(ontology_graph.objects(URIRef(str(ontology_uri)), DCTERMS.contributor))
                date = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.date)
                imports = list(ontology_graph.objects(URIRef(str(ontology_uri)), OWL.imports))

                parts = ontology.split("/")
                try:
                    idx = parts.index("ontologies")
                    module_name = parts[idx - 1] if idx > 0 else ""
                except ValueError:
                    module_name = parts[0] if parts else ""

                ontology_files.append(
                    OntologyFileItemData(
                        name=str(title) if title else str(label),
                        description=str(description) if description else None,
                        license=str(license_val) if license_val else None,
                        contributors=[str(c) for c in contributors],
                        date=str(date) if date else None,
                        path=ontology,
                        module_name=module_name.replace("_", " "),
                        submodule_name=None,
                        imports=[str(i) for i in imports],
                    )
                )

            ontology_files.sort(key=lambda item: (item.module_name.lower(), item.name.lower()))
            return ontology_files
        except OntologyServiceUnavailableError:
            raise
        except Exception as exc:
            raise OntologyServiceUnavailableError("Failed to list ontology files") from exc

    async def get_overview_stats(self, ontology_path: str) -> OntologyOverviewStatsData:
        """Return element counts for a specific ontology file."""
        try:
            graph = _load_ontology_graph(ontology_path)
            classes, obj_props, data_props, named_ind, imports = _compute_ontology_stats_for_graph(graph)
            return OntologyOverviewStatsData(
                name=Path(ontology_path).name,
                path=ontology_path,
                total_items=classes + obj_props + data_props + named_ind,
                classes=classes,
                object_properties=obj_props,
                data_properties=data_props,
                named_individuals=named_ind,
                imports=imports,
            )
        except Exception as exc:
            raise OntologyServiceUnavailableError("Failed to compute ontology overview stats") from exc

    async def get_all_overview_stats(self) -> OntologyOverviewAggregateStatsData:
        """Return consolidated stats across all registered ontology files."""
        try:
            ontologies = await self.list_ontology_files()
            totals = [0, 0, 0, 0, 0]  # classes, obj_props, data_props, named_ind, imports
            for item in ontologies:
                try:
                    graph = _load_ontology_graph(item.path)
                    counts = _compute_ontology_stats_for_graph(graph)
                    for i, v in enumerate(counts):
                        totals[i] += v
                except Exception:
                    continue
            return OntologyOverviewAggregateStatsData(
                name="All ontologies",
                path="*",
                ontologies_count=len(ontologies),
                total_items=totals[0] + totals[1] + totals[2] + totals[3],
                classes=totals[0],
                object_properties=totals[1],
                data_properties=totals[2],
                named_individuals=totals[3],
                imports=totals[4],
            )
        except OntologyServiceUnavailableError:
            raise
        except Exception as exc:
            raise OntologyServiceUnavailableError("Failed to compute aggregate ontology stats") from exc

    async def get_type_counts(self, ontology_path: str | None) -> OntologyTypeCountsData:
        """Return NamedIndividual and DatatypeProperty counts."""
        try:
            ontologies = await self.list_ontology_files()
            target_paths = self._resolve_ontology_paths(ontology_path, ontologies)
            named_individuals = 0
            data_properties = 0
            for path in target_paths:
                graph = _load_ontology_graph(path)
                named_individuals += len(set(graph.subjects(RDF.type, OWL.NamedIndividual)))
                data_properties += len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))
            return OntologyTypeCountsData(
                name=Path(ontology_path).name if ontology_path else "All ontologies",
                path=ontology_path or "*",
                data_properties=data_properties,
                named_individuals=named_individuals,
            )
        except (OntologyPathNotFoundError, OntologyServiceUnavailableError):
            raise
        except Exception as exc:
            raise OntologyServiceUnavailableError("Failed to compute ontology type counts") from exc

    async def get_overview_graph(self, ontology_path: str | None) -> OntologyOverviewGraphData:
        """Return ontology dependency/class graph."""
        store = self._get_triple_store()
        try:
            ontologies = await self.list_ontology_files()
            target_paths = self._resolve_ontology_paths(ontology_path, ontologies)

            if ontology_path:
                # Single ontology: show classes + object properties
                classes_by_iri: dict[str, OntologyOverviewGraphNodeData] = {}
                edges_by_id: dict[str, OntologyOverviewGraphEdgeData] = {}

                class_query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX owl: <http://www.w3.org/2002/07/owl#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    SELECT ?classIri WHERE {
                        ?classIri rdf:type owl:Class .
                        FILTER(isIRI(?classIri))
                    }
                """
                relation_query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX owl: <http://www.w3.org/2002/07/owl#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    SELECT ?propertyIri ?propertyLabel ?propertyDefinition ?domain ?range ?parentPropertyIri WHERE {
                        ?propertyIri rdf:type owl:ObjectProperty .
                        FILTER(isIRI(?propertyIri))
                        OPTIONAL { ?propertyIri rdfs:label ?propertyLabel . }
                        OPTIONAL { ?propertyIri skos:definition ?propertyDefinition . }
                        OPTIONAL {
                            ?propertyIri rdfs:domain ?domain .
                            FILTER(isIRI(?domain))
                        }
                        OPTIONAL {
                            ?propertyIri rdfs:range ?range .
                            FILTER(isIRI(?range))
                        }
                        OPTIONAL {
                            ?propertyIri rdfs:subPropertyOf ?parentPropertyIri .
                            FILTER(isIRI(?parentPropertyIri))
                        }
                    }
                """

                for path in target_paths:
                    graph = _load_ontology_graph(path)

                    for row in graph.query(class_query):
                        assert isinstance(row, ResultRow)
                        class_iri = str(row.get("classIri"))
                        if not class_iri or class_iri in classes_by_iri:
                            continue
                        data = _get_uri_metadata(store, class_iri)
                        class_label = data.get("label", "Unknown")
                        definition = data.get("definition")
                        comment = data.get("comment", "Unknown")
                        parent_iri = data.get("subClassOf", "Unknown")
                        parent_data = _get_uri_metadata(store, parent_iri) if parent_iri else None
                        parent_label = parent_data.get("label", "Unknown") if parent_data else None
                        classes_by_iri[class_iri] = OntologyOverviewGraphNodeData(
                            id=class_iri,
                            label=class_label,
                            type=parent_label,
                            properties={
                                "iri": class_iri,
                                "definition": str(definition) if definition else str(comment),
                                "comment": str(comment),
                                "parent_iri": str(parent_iri),
                                "parent_label": str(parent_label),
                            },
                        )

                    for row in graph.query(relation_query):
                        assert isinstance(row, ResultRow)
                        property_iri = str(row.get("propertyIri"))
                        if not property_iri:
                            continue
                        source_iri = str(row.get("domain")) if row.get("domain") else None
                        target_iri = str(row.get("range")) if row.get("range") else None
                        if not source_iri or not target_iri:
                            continue

                        def _make_node(iri: str) -> OntologyOverviewGraphNodeData:
                            d = _get_uri_metadata(store, iri)
                            lbl = d.get("label", "Unknown")
                            typ = d.get("subClassOf")
                            typ_lbl = _get_uri_metadata(store, typ).get("label", "Unknown") if typ else None
                            defn = d.get("definition")
                            cmnt = d.get("comment")
                            return OntologyOverviewGraphNodeData(
                                id=iri,
                                label=str(lbl),
                                type=typ_lbl,
                                properties={
                                    "iri": iri,
                                    "definition": str(defn) if defn else str(cmnt),
                                    "parent_iri": str(typ),
                                    "parent_label": str(typ_lbl),
                                },
                            )

                        if source_iri not in classes_by_iri:
                            classes_by_iri[source_iri] = _make_node(source_iri)
                        if target_iri not in classes_by_iri:
                            classes_by_iri[target_iri] = _make_node(target_iri)

                        property_label = (
                            str(row.get("propertyLabel"))
                            if row.get("propertyLabel")
                            else property_iri.split("/")[-1]
                        )
                        edge_id = f"{source_iri}|{property_iri}|{target_iri}"
                        if edge_id in edges_by_id:
                            continue
                        property_definition = (
                            str(row.get("propertyDefinition")) if row.get("propertyDefinition") else ""
                        )
                        parent_property_iri = (
                            str(row.get("parentPropertyIri")) if row.get("parentPropertyIri") else ""
                        )
                        edges_by_id[edge_id] = OntologyOverviewGraphEdgeData(
                            id=edge_id,
                            source=source_iri,
                            target=target_iri,
                            type=property_label,
                            label=property_label,
                            properties={
                                "relation_kind": "object_property",
                                "iri": property_iri,
                                "definition": property_definition,
                                "parent_property_iri": parent_property_iri,
                            },
                        )

                return OntologyOverviewGraphData(
                    nodes=sorted(classes_by_iri.values(), key=lambda n: n.label.lower()),
                    edges=sorted(edges_by_id.values(), key=lambda e: e.label.lower()),
                )

            # All ontologies: show import dependency graph
            all_graphs = Graph()
            ontologies_by_iri: dict[str, OntologyOverviewGraphNodeData] = {}
            edges_by_id = {}

            def _label_from_iri(iri: str) -> str:
                if "#" in iri:
                    return iri.rsplit("#", 1)[-1]
                return iri.rstrip("/").rsplit("/", 1)[-1]

            for path in target_paths:
                graph = _load_ontology_graph(path)
                all_graphs += graph

                for subject in graph.subjects(RDF.type, OWL.Ontology):
                    ontology_iri = str(subject)
                    if not ontology_iri or ontology_iri in ontologies_by_iri:
                        continue
                    meta = _get_ontology_metadata(store, ontology_iri)
                    title = meta.get("title", "")
                    label = meta.get("label", "")
                    properties: dict[str, str] = {"iri": ontology_iri, "source_path": path}
                    if label:
                        properties["label"] = str(label)
                    elif title:
                        properties["title"] = str(title)
                    for key in ("description", "comment", "versionInfo", "license", "date"):
                        val = meta.get(key)
                        if val:
                            properties[key] = str(val)
                    ontologies_by_iri[ontology_iri] = OntologyOverviewGraphNodeData(
                        id=ontology_iri,
                        label=str(title) if title else str(label),
                        type="Ontology",
                        properties=properties,
                    )

            imports_query = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT ?sourceOntology ?targetOntology WHERE {
                    ?sourceOntology rdf:type owl:Ontology .
                    ?sourceOntology owl:imports ?targetOntology .
                    FILTER(isIRI(?sourceOntology) && isIRI(?targetOntology))
                }
            """
            for row in all_graphs.query(imports_query):
                assert isinstance(row, ResultRow)
                source_iri = str(row.get("sourceOntology")) if row.get("sourceOntology") else ""
                target_iri = str(row.get("targetOntology")) if row.get("targetOntology") else ""
                if not source_iri or not target_iri:
                    continue
                for iri in (source_iri, target_iri):
                    if iri not in ontologies_by_iri:
                        ontologies_by_iri[iri] = OntologyOverviewGraphNodeData(
                            id=iri,
                            label=_label_from_iri(iri),
                            type="Imports",
                            properties={"iri": iri},
                        )
                edge_id = f"{source_iri}|imports|{target_iri}"
                if edge_id not in edges_by_id:
                    edges_by_id[edge_id] = OntologyOverviewGraphEdgeData(
                        id=edge_id,
                        source=source_iri,
                        target=target_iri,
                        type="imports",
                        label="imports",
                        properties={
                            "relation_kind": "imports",
                            "iri": str(OWL.imports),
                            "definition": "Ontology import dependency.",
                            "parent_property_iri": "",
                        },
                    )

            return OntologyOverviewGraphData(
                nodes=sorted(ontologies_by_iri.values(), key=lambda n: n.label.lower()),
                edges=sorted(edges_by_id.values(), key=lambda e: e.label.lower()),
            )

        except (OntologyPathNotFoundError, OntologyServiceUnavailableError):
            raise
        except Exception as exc:
            mode = "single_ontology" if ontology_path else "imports_overview"
            raise OntologyServiceUnavailableError(
                f"Failed to compute ontology overview graph ({mode}): "
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            ) from exc

    async def create_entity(
        self,
        name: str,
        description: str | None,
        base_class: str | None,
    ) -> OntologyItemData:
        item = OntologyItemData(
            id=f"entity-{int(datetime.now().timestamp() * 1000)}",
            name=name,
            type="entity",
            description=description,
            parent_id=base_class,
        )
        self._ontology_items.append(item)
        return item

    async def create_relationship(
        self,
        name: str,
        description: str | None,
        base_property: str | None,
    ) -> OntologyItemData:
        item = OntologyItemData(
            id=f"rel-{int(datetime.now().timestamp() * 1000)}",
            name=name,
            type="relationship",
            description=description,
            parent_id=base_property,
        )
        self._ontology_items.append(item)
        return item

    async def delete_item(self, item_id: str) -> None:
        self._ontology_items = [i for i in self._ontology_items if i.id != item_id]

    async def import_ontology(self, content: str, filename: str) -> ReferenceOntologyData:
        try:
            return _parse_ttl(content, filename)
        except Exception as exc:
            raise OntologyParseError("Failed to parse ontology file") from exc

    async def export_ontology_file(self, ontology_path: str) -> Path:
        path = Path(ontology_path)
        if not path.exists() or not path.is_file():
            from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
                OntologyFileNotFoundError,
            )
            raise OntologyFileNotFoundError("Ontology file does not exist")
        return path
