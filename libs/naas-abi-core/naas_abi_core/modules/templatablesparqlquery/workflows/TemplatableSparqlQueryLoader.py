import asyncio
from collections.abc import Iterable

from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import Field, create_model
from rdflib import RDF, Graph, URIRef
from rdflib.util import guess_format

from .GenericWorkflow import GenericWorkflow


async def async_asyncio_thread_jobs(jobs):
    tasks = []
    for job in jobs:
        task = asyncio.create_task(asyncio.to_thread(*job))
        tasks.append(task)
    return await asyncio.gather(*tasks)


def asyncio_thread_job(jobs):
    return asyncio.run(async_asyncio_thread_jobs(jobs))


def first_party_ontologies(modules: Iterable[object]) -> list[str]:
    """The ontology files of the modules this engine runs in process."""
    return [
        path for module in modules for path in getattr(module, "ontologies", None) or []
    ]


class TemplatableSparqlQueryLoader:
    """Turns the templatable queries of first-party ontology files into tools.

    Queries are read from ``ontology_files`` (the files of the modules the
    engine runs, ``first_party_ontologies``), never from the shared schema
    graph, where other principals may load content. The tools run their
    queries on ``triple_store_service``.
    """

    triple_store_service: TripleStoreService

    def __init__(
        self,
        triple_store_service: TripleStoreService,
        ontology_files: Iterable[str] = (),
    ):
        self.triple_store_service = triple_store_service
        self.graph = Graph()
        for path in ontology_files:
            try:
                self.graph.parse(path, format=guess_format(path) or "turtle")
            except Exception as exc:  # noqa: BLE001 - one bad file loses its queries only
                logger.warning(f"Templatable queries: cannot read {path}: {exc}")

    def templatable_queries(self):
        results = self.graph.query(
            """
            PREFIX intentMapping: <http://ontology.naas.ai/intentMapping/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?query ?label ?description ?sparqlTemplate ?hasArgument
            WHERE {
                ?query a intentMapping:TemplatableSparqlQuery ;
                    intentMapping:intentDescription ?description ;
                    intentMapping:sparqlTemplate ?sparqlTemplate ;
                    intentMapping:hasArgument ?hasArgument ;
                    rdfs:label ?label .
            }
        """
        )

        queries = {}

        for result in results:
            query, label, description, sparqlTemplate, hasArgument = result
            queries[query] = {
                "label": label,
                "description": description,
                "sparqlTemplate": sparqlTemplate,
                "hasArgument": [hasArgument]
                if (query not in queries or queries[query].get("hasArgument") is None)
                else queries[query].get("hasArgument") + [hasArgument],
            }

        arguments = {}

        argument_graph = Graph()
        argument_graph.bind(
            "intentMapping", URIRef("http://ontology.naas.ai/intentMapping/")
        )
        results = self.graph.query(
            """
                    PREFIX intentMapping: <http://ontology.naas.ai/intentMapping/>

                    SELECT ?argument ?name ?description ?validationPattern ?validationFormat
                    WHERE {
                        ?argument a intentMapping:QueryArgument ;
                            intentMapping:argumentName ?name ;
                            intentMapping:argumentDescription ?description ;
                            intentMapping:validationPattern ?validationPattern ;
                            intentMapping:validationFormat ?validationFormat .
                    }
                """
        )

        for argument, name, description, validationPattern, validationFormat in results:
            argument_graph.add(
                (
                    argument,
                    RDF.type,
                    URIRef("http://ontology.naas.ai/intentMapping/QueryArgument"),
                )
            )
            argument_graph.add(
                (
                    argument,
                    URIRef("http://ontology.naas.ai/intentMapping/argumentName"),
                    name,
                )
            )
            argument_graph.add(
                (
                    argument,
                    URIRef("http://ontology.naas.ai/intentMapping/argumentDescription"),
                    description,
                )
            )
            argument_graph.add(
                (
                    argument,
                    URIRef("http://ontology.naas.ai/intentMapping/validationPattern"),
                    validationPattern,
                )
            )
            argument_graph.add(
                (
                    argument,
                    URIRef("http://ontology.naas.ai/intentMapping/validationFormat"),
                    validationFormat,
                )
            )

        arguments = {}
        for templatableQuery in queries:
            for argument in queries[templatableQuery].get("hasArgument"):
                q = (
                    """
                    PREFIX intentMapping: <http://ontology.naas.ai/intentMapping/>

                    SELECT ?argument ?name ?description ?validationPattern ?validationFormat
                    WHERE {
                        BIND(<"""
                    + str(argument)
                    + """> AS ?argument)
                        ?argument a intentMapping:QueryArgument ;
                            intentMapping:argumentName ?name ;
                            intentMapping:argumentDescription ?description ;
                            intentMapping:validationPattern ?validationPattern ;
                            intentMapping:validationFormat ?validationFormat .
                    }
                """
                )
                # logger.debug(f"Query: {q}")
                results = argument_graph.query(q)

                for result in results:
                    argument, name, description, validationPattern, validationFormat = (
                        result
                    )

                    arguments[argument] = {
                        "name": name,
                        "description": description,
                        "validationPattern": validationPattern,
                        "validationFormat": validationFormat,
                    }

        return queries, arguments

    def load_workflows(self):
        workflows = []

        queries, arguments = self.templatable_queries()

        # workflows = asyncio.run(__load_queries(queries, arguments))

        # Now for each query, we need to create a Pydantic BaseModel based on the arguments
        for _query in queries:
            try:
                query = queries[_query]

                # Arguments Model with validation patterns
                arguments_model = create_model(
                    f"{str(query['label']).capitalize()}Arguments",
                    **{
                        str(arguments[argument]["name"]): (
                            str,
                            Field(
                                ...,
                                description=str(arguments[argument]["description"]),
                                pattern=str(arguments[argument]["validationPattern"]),
                                # You could also add additional metadata from validationFormat if needed
                                json_schema_extra={
                                    "example": str(
                                        arguments[argument]["validationFormat"]
                                    )
                                },
                            ),
                        )
                        for argument in query.get("hasArgument")
                    },
                )

                p = GenericWorkflow[arguments_model](
                    str(query["label"]),
                    str(query["description"]),
                    str(query["sparqlTemplate"]),
                    arguments_model,
                    self.triple_store_service,
                )
                workflows.append(p)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Error loading workflow for query {query['label']}\nMessage: {e}"
                )

        return workflows
