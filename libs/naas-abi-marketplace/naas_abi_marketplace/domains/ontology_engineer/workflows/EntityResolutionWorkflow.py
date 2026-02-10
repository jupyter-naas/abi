"""
Entity Resolution Workflow for identifying and resolving duplicate entities in RDF graphs.

This workflow identifies duplicate entities (owl:NamedIndividual) based on:
1. Business rules (e.g., entities with "unknown" key values)
2. Fuzzy matching using key values (owl:hasKey)

Usage:
    uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/workflows/EntityResolutionWorkflow.py
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, List, Optional, Set, Tuple, cast

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field
from rdflib import RDFS, Graph, Literal, Node, URIRef
from rdflib.collection import Collection
from rdflib.query import ResultRow
from thefuzz import fuzz  # type: ignore


@dataclass
class EntityResolutionWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Entity Resolution Workflow.

    Attributes:
        triple_store (ITripleStoreService): TripleStoreService instance for querying the triplestore.
    """

    triple_store: ITripleStoreService


class EntityResolutionWorkflowParameters(WorkflowParameters):
    """Parameters for Entity Resolution Workflow.

    Attributes:
        tbox_paths (Optional[List[str]]): Optional list of paths to TBox (schema/classes) Turtle files.
                                         If not provided, schema will be loaded from triplestore.
        abox_paths (Optional[List[str]]): Optional list of paths to ABox (individuals) Turtle files.
                                         If not provided, individuals will be loaded from triplestore.
        similarity_threshold (int): Minimum similarity score (0-100) to consider entities as duplicates.
        uri_prefix_filter (Optional[str]): Optional URI prefix filter for individuals (e.g., "http://ontology.naas.ai/abi/").
    """

    tbox_paths: Annotated[
        Optional[List[str]],
        Field(
            description="Optional list of paths to TBox (schema/classes) Turtle files. If not provided, schema will be loaded from triplestore.",
        ),
    ] = None
    abox_paths: Annotated[
        Optional[List[str]],
        Field(
            description="Optional list of paths to ABox (individuals) Turtle files. If not provided, individuals will be loaded from triplestore.",
        ),
    ] = None
    similarity_threshold: Annotated[
        int,
        Field(
            description="Minimum similarity score (0-100) to consider entities as duplicates.",
        ),
    ] = 100
    uri_prefix_filter: Annotated[
        Optional[str],
        Field(
            description="URI prefix filter for individuals when loading from triplestore.",
        ),
    ] = "http://ontology.naas.ai/abi/"
    limit: Annotated[
        Optional[int],
        Field(
            description="Limit the number of individuals to load from triplestore.",
        ),
    ] = None


class EntityResolutionWorkflow(Workflow[EntityResolutionWorkflowParameters]):
    """Workflow for identifying and resolving duplicate entities in RDF graphs."""

    __configuration: EntityResolutionWorkflowConfiguration

    def __init__(self, configuration: EntityResolutionWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__triple_store_service = self.__configuration.triple_store

    def _load_schema_from_files(self, tbox_paths: List[str]) -> Graph:
        """Load schema graph from Turtle files.

        Args:
            tbox_paths: List of paths to Turtle files containing schema/classes.

        Returns:
            Graph: The loaded schema graph.
        """
        schema_graph = Graph()
        for schema_file in tbox_paths:
            schema_path = Path(schema_file)
            if not schema_path.exists():
                logger.warning(f"Schema file not found: {schema_file}, skipping...")
                continue
            schema_graph += Graph().parse(str(schema_path), format="turtle")
            logger.info(f"Loaded schema from: {schema_file}")
        return schema_graph

    def _load_schema_from_triplestore(self) -> Graph:
        """Load schema (owl:Class) from triplestore.

        Returns:
            Graph: The loaded schema graph containing owl:Class definitions.
        """
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        CONSTRUCT {
            ?s ?p ?o
        }
        WHERE {
            ?s ?p ?o .
            {
                ?s a owl:Class .
            } UNION {
                ?s rdfs:subClassOf ?o .
            } UNION {
                ?s owl:hasKey ?o .
            }
        }
        """
        schema_graph = Graph()
        try:
            results = self.__triple_store_service.query(query)
            for triple in results:
                # CONSTRUCT queries return triples directly
                schema_graph.add(triple)  # type: ignore
            logger.info(f"Loaded schema from triplestore: {len(schema_graph)} triples")
        except Exception as e:
            logger.error(f"Error loading schema from triplestore: {e}")
        return schema_graph

    def _load_individuals_from_files(self, abox_paths: List[str]) -> Graph:
        """Load individuals graph from Turtle files.

        Args:
            abox_paths: List of paths to Turtle files containing individuals.

        Returns:
            Graph: The loaded individuals graph.
        """
        individual_graph = Graph()
        for individual_file in abox_paths:
            individual_path = Path(individual_file)
            if not individual_path.exists():
                logger.warning(
                    f"Individual file not found: {individual_file}, skipping..."
                )
                continue
            individual_graph += Graph().parse(str(individual_path), format="turtle")
            logger.info(f"Loaded individuals from: {individual_file}")
        return individual_graph

    def _load_individuals_from_triplestore(
        self, uri_prefix_filter: Optional[str] = None, limit: Optional[int] = None
    ) -> Graph:
        """Load individuals (owl:NamedIndividual) from triplestore.

        Args:
            uri_prefix_filter: Optional URI prefix filter for individuals.

        Returns:
            Graph: The loaded individuals graph.
        """
        filter_clause = ""
        if uri_prefix_filter:
            filter_clause = f'FILTER(STRSTARTS(STR(?s), "{uri_prefix_filter}"))'

        query = f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        CONSTRUCT {{
            ?s ?p ?o
        }}
        WHERE {{
            ?s ?p ?o .
            ?s a owl:NamedIndividual .
            {filter_clause}
        }}
        {f"LIMIT {limit}" if limit else ""}
        """
        individual_graph = Graph()
        try:
            results = self.__triple_store_service.query(query)
            for triple in results:
                # CONSTRUCT queries return triples directly
                individual_graph.add(triple)  # type: ignore
            logger.info(
                f"Loaded individuals from triplestore: {len(individual_graph)} triples"
            )
        except Exception as e:
            logger.error(f"Error loading individuals from triplestore: {e}")
        return individual_graph

    def get_keys_for_class(
        self, graph: Graph, class_uri: URIRef
    ) -> Optional[List[Node]]:
        """
        Get the keys (owl:hasKey) for a specific class.
        :param graph: The RDF graph to query.
        :param class_uri: The URI of the class (as string or URIRef).
        :return: A list of keys (Node objects, typically URIRef) if the class has keys, None otherwise.
        """
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?list
        WHERE {
          ?class_uri owl:hasKey ?list .
        }
        """
        results = graph.query(query, initBindings={"class_uri": class_uri})

        for row in results:
            result_row = cast(ResultRow, row)
            list_node = result_row[0]  # ?list
            # Extract all keys from the RDF list
            try:
                collection = Collection(graph, list_node)
                keys = list(collection)
                return keys
            except Exception as e:
                logger.warning(f"{class_uri} - Error extracting keys: {e}")
                return None

        return None

    def get_keys_for_class_recursive(
        self, graph: Graph, class_uri: URIRef, visited: Optional[Set[URIRef]] = None
    ) -> Optional[List[Node]]:
        """
        Recursively get the keys (owl:hasKey) for a specific class, checking parent classes if not found directly.
        :param graph: The RDF graph to query.
        :param class_uri: The URI of the class (as string or URIRef).
        :param visited: Set of already visited class URIs to avoid cycles.
        :return: A list of keys (Node objects, typically URIRef) if found, None otherwise.
        """
        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        # Avoid infinite loops
        if class_uri in visited:
            return None
        visited.add(class_uri)

        # First, check if the class has keys directly
        keys = self.get_keys_for_class(graph, class_uri)
        if keys is not None:
            return keys

        # If not found, check parent classes (rdfs:subClassOf)
        parent_classes = list(graph.objects(class_uri, RDFS.subClassOf))
        for parent in parent_classes:
            # Only recurse on URIRef parents (skip BNodes which might be restrictions)
            if isinstance(parent, URIRef):
                parent_keys = self.get_keys_for_class_recursive(graph, parent, visited)
                if parent_keys is not None:
                    return parent_keys

        return None

    def get_classes_from_individuals_sparql(self, graph: Graph) -> List[URIRef]:
        """
        Get the classes (rdf:type values) from the individuals (owl:NamedIndividual) in the graph using a SPARQL query,
        excluding all types that are in the owl: namespace.
        :param graph: The RDF graph to query.
        :return: A list of classes (URIRef) from the individuals in the graph.
        """
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?type
        WHERE {
            ?individual rdf:type ?type .
            FILTER(STRSTARTS(STR(?type), STR(owl:)) = false)
        }
        """
        results = graph.query(query)
        classes = set()
        for row in results:
            result_row = cast(ResultRow, row)
            type_node = result_row[0]  # ?type
            if isinstance(type_node, URIRef):
                classes.add(type_node)
        return list(classes)

    def resolve_duplicate_entities(
        self, result_rows: List[ResultRow], similarity_threshold: int = 90
    ) -> List[Tuple[URIRef, URIRef]]:
        """
        Efficient entity resolution using business rules and fuzzy matching.

        Business rules:
        1. If multiple entities have key value "unknown" (lowercase), keep the first one and remove others.

        Fuzzy matching:
        2. Use thefuzz library to find duplicates based on key values.
        3. If similarity score >= threshold, consider them duplicates.
        4. Keep the first occurrence and mark others for removal.

        :param result_rows: List of ResultRow tuples, where first element is URIRef (individual URI)
                           and remaining elements are Literal values (key values).
        :param similarity_threshold: Minimum similarity score (0-100) to consider entities as duplicates.
        :return: List of tuples (uri_to_keep, uri_to_remove) indicating which URIs should be kept and removed.
        """
        if len(result_rows) < 2:
            return []

        duplicates_to_remove: List[Tuple[URIRef, URIRef]] = []
        uris_to_remove: Set[URIRef] = set()

        # Extract URIs and key values from result rows
        entities = []
        for row in result_rows:
            result_row = cast(ResultRow, row)
            individual_uri = cast(URIRef, result_row[0])
            # Get all key values (skip the first element which is the URI)
            key_values = [
                str(cast(Literal, val).value) if isinstance(val, Literal) else str(val)
                for val in result_row[1:]
            ]
            entities.append((individual_uri, key_values))

        # Step 1: Apply business rule for "unknown" values
        unknown_entities = []
        for i, (uri, key_values) in enumerate(entities):
            # Check if any key value is "unknown" (case-insensitive, lowercase comparison)
            has_unknown = any(str(kv).lower().strip() == "unknown" for kv in key_values)
            if has_unknown:
                unknown_entities.append((i, uri))

        # If multiple entities have "unknown", keep the first one and remove others
        if len(unknown_entities) > 1:
            first_unknown_uri = unknown_entities[0][1]
            for _, uri in unknown_entities[1:]:
                if uri not in uris_to_remove:
                    duplicates_to_remove.append((first_unknown_uri, uri))
                    uris_to_remove.add(uri)

        # Step 2: Fuzzy matching for duplicates
        # Compare each entity with all subsequent entities
        for i in range(len(entities)):
            uri_i, key_values_i = entities[i]

            # Skip if this URI is already marked for removal
            if uri_i in uris_to_remove:
                continue

            # Create a normalized string representation of key values for comparison
            # Use the first key value, or concatenate all if multiple
            key_str_i = " ".join(key_values_i).strip().lower()

            for j in range(i + 1, len(entities)):
                uri_j, key_values_j = entities[j]

                # Skip if this URI is already marked for removal
                if uri_j in uris_to_remove:
                    continue

                # Create normalized string for comparison
                key_str_j = " ".join(key_values_j).strip().lower()

                # Skip if both are "unknown" (already handled by business rule)
                if key_str_i == "unknown" and key_str_j == "unknown":
                    continue

                # Calculate similarity using token_sort_ratio (good for order-independent matching)
                similarity = fuzz.token_sort_ratio(key_str_i, key_str_j)

                if similarity >= similarity_threshold:
                    # Keep the first one (uri_i), remove the duplicate (uri_j)
                    duplicates_to_remove.append((uri_i, uri_j))
                    uris_to_remove.add(uri_j)

        return duplicates_to_remove

    def run(self, parameters: EntityResolutionWorkflowParameters) -> dict:
        """
        Execute the entity resolution workflow.

        Args:
            parameters: Parameters containing tbox_paths, abox_paths, and other configuration.

        Returns:
            dict: Dictionary containing:
                - classes: List of classes found
                - duplicates: List of duplicate pairs (uri_to_keep, uri_to_remove)
                - summary: Summary statistics
        """
        # Load schema graph (TBox)
        if parameters.tbox_paths:
            schema_graph = self._load_schema_from_files(parameters.tbox_paths)
        else:
            schema_graph = self._load_schema_from_triplestore()

        # Load individuals graph (ABox)
        if parameters.abox_paths:
            individual_graph = self._load_individuals_from_files(parameters.abox_paths)
        else:
            individual_graph = self._load_individuals_from_triplestore(
                parameters.uri_prefix_filter, parameters.limit
            )

        # Get classes from individuals
        classes = self.get_classes_from_individuals_sparql(individual_graph)
        logger.info(f"Found {len(classes)} classes from individuals")

        all_duplicates: List[Tuple[URIRef, URIRef]] = []

        # Process each class
        for c in classes:
            logger.info(f"Checking class: {c}")
            keys = self.get_keys_for_class_recursive(schema_graph, URIRef(c))
            logger.info(f"Has key for {c}: {keys}")
            if keys is not None and len(keys) > 0:
                filter_clauses = []
                var_names = []
                for i, key_predicate in enumerate(keys):
                    # Always use angle-bracket IRI for predicate for SPARQL safety
                    pred_str = f"<{key_predicate}>"
                    # Build valid SPARQL variable names by using 'val' plus numeric index, to avoid "-" or bad chars
                    var_name = f"val{i}"
                    var_names.append(var_name)
                    filter_clauses.append(f"?individual {pred_str} ?{var_name} .")
                keys_filter_str = "\n    ".join(filter_clauses)
                select_vars_str = " ".join(
                    [f"?{v}" for v in ["individual"] + var_names]
                )
                query = f"""
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                SELECT DISTINCT {select_vars_str}
                WHERE {{
                    ?individual rdf:type owl:NamedIndividual .
                    ?individual rdf:type <{c}> .
                    {keys_filter_str}
                }}
                """
                try:
                    results = individual_graph.query(query)
                    result_rows = [cast(ResultRow, row) for row in results]
                    logger.info(f"Found {len(result_rows)} results for class {c}")

                    # Apply entity resolution
                    if len(result_rows) > 0:
                        duplicates = self.resolve_duplicate_entities(
                            result_rows, parameters.similarity_threshold
                        )
                        logger.info(
                            f"Entity resolution found {len(duplicates)} duplicate(s) for class {c}"
                        )
                        all_duplicates.extend(duplicates)
                except Exception as e:
                    logger.error(f"SPARQL query failed for class {c}: {e}")

        return {
            "classes": [str(c) for c in classes],
            "duplicates": [
                {"keep": str(keep), "remove": str(remove)}
                for keep, remove in all_duplicates
            ],
            "summary": {
                "total_classes": len(classes),
                "total_individuals": len(individual_graph),
                "total_duplicates": len(all_duplicates),
            },
        }

    def as_tools(self) -> list[BaseTool]:
        """
        Return a list of tools that can be used to interact with this workflow.

        Returns:
            list[StructuredTool]: List of tools
        """
        return [
            StructuredTool(
                name="resolve_duplicate_entities",
                description="Identify and resolve duplicate entities in RDF graphs based on business rules and fuzzy matching.",
                func=lambda **kwargs: self.run(
                    EntityResolutionWorkflowParameters(**kwargs)
                ),
                args_schema=EntityResolutionWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None


if __name__ == "__main__":
    """
    Main entry point for the script.

    Execute entity resolution workflow to identify duplicate entities.

    Examples:
        # Run with default settings (load from triplestore)
        uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/workflows/EntityResolutionWorkflow.py

        # Run with file paths
        uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/workflows/EntityResolutionWorkflow.py \
            --tbox_paths path/to/schema.ttl \
            --abox_paths path/to/individuals.ttl
    """
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.domains.ontology_engineer.pipelines.MergeIndividualsPipeline import (
        MergeIndividualsPipeline,
        MergeIndividualsPipelineConfiguration,
        MergeIndividualsPipelineParameters,
    )

    # Create Engine and get triple_store_service (only used in example)
    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.domains.ontology_engineer"])
    triple_store_service = engine.services.triple_store
    object_storage_service = engine.services.object_storage

    # Create workflow configuration and instance
    configuration = EntityResolutionWorkflowConfiguration(
        triple_store=triple_store_service
    )
    workflow = EntityResolutionWorkflow(configuration)

    # Merge duplicates pipeline configuration
    merge_duplicates_pipeline_configuration = MergeIndividualsPipelineConfiguration(
        triple_store=triple_store_service,
        object_storage=object_storage_service,
    )

    # Merge duplicates pipeline instance
    merge_duplicates_pipeline = MergeIndividualsPipeline(
        merge_duplicates_pipeline_configuration
    )

    # Example: Use file paths (commented out) or load from triplestore
    tbox_paths = [
        "libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/ontologies/BFO7BucketsProcessOntology.ttl",
        "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/modules/ActOfConnectionsOnLinkedIn.ttl",
    ]
    abox_paths = [
        "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/sandbox/insert_Florent_Ravenel.ttl"
    ]

    # Create parameters (using triplestore by default)
    parameters = EntityResolutionWorkflowParameters(
        tbox_paths=tbox_paths,  # Uncomment to use files
        # abox_paths=abox_paths,  # Uncomment to use files
        similarity_threshold=100,
        uri_prefix_filter="http://ontology.naas.ai/abi/",
        # limit=1000,
    )

    # Execute workflow
    import concurrent.futures

    result = workflow.run(parameters)

    print("\nEntity Resolution Results:")
    print(f"  Classes found: {result['summary']['total_classes']}")
    print(f"  Individuals found: {result['summary']['total_individuals']}")
    print(f"  Duplicates found: {result['summary']['total_duplicates']}")

    def merge_duplicate_worker(duplicate):
        print(f"Merging {duplicate['keep']} and {duplicate['remove']}")
        merged_graph = merge_duplicates_pipeline.run(
            MergeIndividualsPipelineParameters(
                merge_pairs=[
                    (duplicate["keep"], duplicate["remove"]),
                ]
            )
        )
        return merged_graph

    if result["duplicates"]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(merge_duplicate_worker, duplicate)
                for duplicate in result["duplicates"]
            ]
            # Wait for all futures to complete if you need merged results
            for future in concurrent.futures.as_completed(futures):
                _ = future.result()
