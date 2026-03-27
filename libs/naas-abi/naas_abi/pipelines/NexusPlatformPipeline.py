from datetime import datetime

from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import DCTERMS, OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.query import ResultRow

NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
NEXUS_NAMESPACE = Namespace("http://ontology.naas.ai/nexus/")
ABI_NAMESPACE = Namespace("http://ontology.naas.ai/abi/")
NEXUS_GRAPH_CLASS = NEXUS_NAMESPACE.Graph
NEXUS_AGENT_CLASS = NEXUS_NAMESPACE.Agent


def create_nexus_graph(store: TripleStoreService) -> None:
    if NEXUS_GRAPH_URI not in store.list_graphs():
        store.create_graph(NEXUS_GRAPH_URI)
        logger.info(f"Nexus graph created at {NEXUS_GRAPH_URI}")


def _query_nexus_instances(store: TripleStoreService, class_uri: URIRef) -> list[dict]:
    sparql_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?uri ?label
    WHERE {{
        GRAPH <{str(NEXUS_GRAPH_URI)}> {{
            ?uri a <{str(class_uri)}> .
            OPTIONAL {{ ?uri rdfs:label ?label . }}
        }}
    }}
    """
    results = store.query(sparql_query)
    nexus_instances: list[dict] = []
    for row in results:
        assert isinstance(row, ResultRow)
        uri = str(row.uri)
        label = str(row.label) if row.label is not None else ""
        nexus_instances.append({"uri": uri, "label": label})
    return nexus_instances


def list_nexus_graphs(
    store: TripleStoreService,
) -> list[dict]:
    return _query_nexus_instances(store, NEXUS_GRAPH_CLASS)


def create_graph_to_nexus_graph(store: TripleStoreService, graph_uri: URIRef) -> None:
    graph = Graph()
    graph.add((graph_uri, RDF.type, OWL.NamedIndividual))
    graph.add((graph_uri, RDF.type, NEXUS_GRAPH_CLASS))
    graph.add((graph_uri, RDFS.label, Literal(graph_uri.split("/")[-1].split("#")[-1])))
    graph.add(
        (
            graph_uri,
            DCTERMS.created,
            Literal(
                datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"), datatype=XSD.dateTime
            ),
        )
    )
    store.insert(graph, graph_name=NEXUS_GRAPH_URI)


def list_nexus_agents(store: TripleStoreService) -> list[dict]:
    return _query_nexus_instances(store, NEXUS_AGENT_CLASS)


def create_agent_to_nexus_graph(
    store: TripleStoreService,
    graph_uri: URIRef,
    uri: str,
    label: str,
    description: str | None = None,
    logo_url: str | None = None,
    system_prompt: str | None = None,
) -> None:
    graph = Graph()
    graph.add((URIRef(uri), RDF.type, OWL.NamedIndividual))
    graph.add((URIRef(uri), RDF.type, NEXUS_AGENT_CLASS))
    graph.add((URIRef(uri), RDFS.label, Literal(label)))
    graph.add(
        (
            URIRef(uri),
            DCTERMS.created,
            Literal(
                datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"), datatype=XSD.dateTime
            ),
        )
    )
    if description is not None:
        graph.add((URIRef(uri), RDFS.comment, Literal(description)))
    if logo_url is not None:
        graph.add((URIRef(uri), ABI_NAMESPACE.logo, Literal(logo_url)))
    if system_prompt is not None:
        graph.add((URIRef(uri), ABI_NAMESPACE.system_prompt, Literal(system_prompt)))

    graph.add((URIRef(uri), NEXUS_NAMESPACE.inGraph, graph_uri))
    graph.add((graph_uri, NEXUS_NAMESPACE.hasAgent, URIRef(uri)))
    store.insert(graph, graph_name=NEXUS_GRAPH_URI)


def initialize_nexus_graphs(store: TripleStoreService) -> None:
    # Create nexus graph to triple store
    create_nexus_graph(store)

    # Add graphs instances to nexus graph
    nexus_graphs = list_nexus_graphs(store)
    nexus_graph_uris = {graph["uri"] for graph in nexus_graphs}
    for graph_uri in store.list_graphs():
        if str(graph_uri) not in nexus_graph_uris:
            create_graph_to_nexus_graph(store, graph_uri)
            logger.info(f"🟢 Graph {str(graph_uri)} added to nexus graph")


def initialize_nexus_agents(store: TripleStoreService) -> None:
    # Add agents from engine modules to the API
    import hashlib

    from naas_abi import ABIModule
    from naas_abi_core.services.agent.Agent import Agent

    # Get all agents from engine modules
    abi_module = ABIModule.get_instance()
    module_agents = list(abi_module.agents)
    agents: list[type[Agent]] = []
    agents.extend(module_agents)

    for module in abi_module.engine.modules.values():
        for agent_cls in module.agents:
            if agent_cls is None:
                continue
            agents.append(agent_cls)

    # create agents in nexus graph
    nexus_agent_uris = {agent["uri"] for agent in list_nexus_agents(store)}
    for agent_cls in agents:
        class_name = f"{agent_cls.__module__}/{agent_cls.__name__}"
        agent_hash = hashlib.sha256(class_name.encode()).hexdigest()
        uri = str(NEXUS_NAMESPACE[f"agent/{agent_hash}"])
        if uri in nexus_agent_uris:
            continue
        name = getattr(agent_cls, "name", None)
        if name is None:
            name = agent_cls.__name__
        description = getattr(agent_cls, "description", None)
        logo_url = getattr(agent_cls, "logo_url", None)
        system_prompt = getattr(agent_cls, "system_prompt", None)
        create_agent_to_nexus_graph(
            store, NEXUS_GRAPH_URI, uri, name, description, logo_url, system_prompt
        )


def initialize_nexus(store: TripleStoreService) -> None:
    initialize_nexus_graphs(store)
    initialize_nexus_agents(store)


if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])
    triple_store = engine.services.triple_store

    store = triple_store

    # Initialize nexus graph
    initialize_nexus(store)
