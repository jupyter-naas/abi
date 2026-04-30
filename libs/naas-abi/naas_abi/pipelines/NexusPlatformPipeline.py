from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, cast

from langchain_core.tools import BaseTool
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    Agent,
    AgentIntent,
    AgentRole,
    AgentTool,
    GraphFilter,
    GraphView,
    KnowledgeGraph,
    KnowledgeGraphRole,
)
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.SPARQL import SPARQLUtils
from rdflib import RDF, Graph, Namespace, URIRef


def _module_name_from_module_path(module_path: str | None) -> str | None:
    if not module_path:
        return None
    return module_path.split(".", 1)[0] or None


def _normalize_logo_path_for_module(logo_url: str, module_name: str) -> str:
    if logo_url.startswith(f"{module_name}/"):
        return logo_url
    if logo_url.startswith(f"/{module_name}/"):
        return logo_url.lstrip("/")
    idx = logo_url.find(f"{module_name}/")
    if idx >= 0:
        return logo_url[idx:]
    return logo_url.lstrip("/")


def _public_modules_url(public_api_host: str, path: str) -> str:
    return f"{public_api_host}/modules/{path.lstrip('/')}"


@dataclass
class NexusPlatformPipelineConfiguration(PipelineConfiguration):
    """Configuration for NexusPlatformPipeline."""

    triple_store: TripleStoreService
    nexus_namespace: Namespace = Namespace("http://ontology.naas.ai/nexus/")
    nexus_graph_uri: URIRef = URIRef("http://ontology.naas.ai/graph/nexus")
    force_update: bool = True


class NexusPlatformPipelineParameters(PipelineParameters):
    """Parameters for NexusPlatformPipeline execution."""

    pass


class NexusPlatformPipeline(Pipeline):
    """Pipeline for initializing the Nexus platform (graph + agents)."""

    __configuration: NexusPlatformPipelineConfiguration
    __nexus_namespace: Namespace
    __nexus_graph_uri: URIRef
    __force_update: bool
    __triple_store: TripleStoreService
    __sparql_utils: SPARQLUtils

    def __init__(self, configuration: NexusPlatformPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__nexus_namespace = configuration.nexus_namespace
        self.__nexus_graph_uri = configuration.nexus_graph_uri
        self.__force_update = configuration.force_update
        self.__triple_store = configuration.triple_store
        self.__sparql_utils = SPARQLUtils(self.__triple_store)

        # Create the Nexus named graph if it does not exist.
        logger.debug(f"Nexus graph list: {self.__triple_store.list_graphs()}")
        if self.__nexus_graph_uri not in self.__triple_store.list_graphs():
            self.__triple_store.create_graph(self.__nexus_graph_uri)
            logger.debug(f"Nexus graph created at {self.__nexus_graph_uri}")

        if (
            self.__force_update
            and self.__nexus_graph_uri in self.__triple_store.list_graphs()
        ):
            logger.debug(f"Nexus graph cleared at {self.__nexus_graph_uri}")
            self.__triple_store.clear_graph(self.__nexus_graph_uri)

    def _query_nexus_instances(
        self,
        class_uri: URIRef,
        metadata: dict[str, URIRef] = {},
    ) -> List[Dict]:
        """Query Nexus instances of a given class.

        Args:
            class_uri: The URI of the class to query.
            metadata: Optional metadata to filter the results

        Returns:
            A list of dictionaries containing the URI and label of the Nexus instances.
        """
        metadata_labels: list[str] = list(metadata.keys())
        metadata_vars = " ".join(f"?{metadata_key}" for metadata_key in metadata_labels)
        metadata_optionals = " ".join(
            f"OPTIONAL {{ ?uri <{str(metadata_value)}> ?{metadata_key} . }}"
            for metadata_key, metadata_value in metadata.items()
        )

        select_clause = (
            f"SELECT ?uri ?label {metadata_vars}"
            if metadata_vars
            else "SELECT ?uri ?label"
        )

        sparql_query = (
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
            f"{select_clause} "
            "WHERE { "
            f"GRAPH <{str(self.__nexus_graph_uri)}> {{ "
            f"?uri rdf:type <{str(class_uri)}> . "
            "OPTIONAL { ?uri rdfs:label ?label . } "
            f"{metadata_optionals} "
            "} "
            "} "
        )
        logger.debug(f"SPARQL query: {sparql_query}")
        results = self.__triple_store.query(sparql_query)
        nexus_instances = self.__sparql_utils.results_to_list(results)
        return nexus_instances if nexus_instances is not None else []

    def list_nexus_graphs(self) -> List[Dict]:
        return self._query_nexus_instances(URIRef(KnowledgeGraph._class_uri))

    def create_graph_to_nexus_graph(
        self,
        uri: URIRef,
    ) -> tuple[KnowledgeGraph, KnowledgeGraphRole]:
        role_label = (
            "Admin"
            if any(token in str(uri).lower() for token in {"schema", "nexus"})
            else "unknown"
        )
        knowledge_graph_role = KnowledgeGraphRole(
            label=role_label,
            is_knowledge_graph_role_of=[uri],
        )
        knowledge_graph = KnowledgeGraph(
            _uri=uri,
            label=uri.split("/")[-1].split("#")[-1].capitalize(),
            has_knowledge_graph_role=[knowledge_graph_role],
        )
        return knowledge_graph, knowledge_graph_role

    def initialize_nexus_graphs(self) -> Graph:
        """Ensure the Nexus graph is populated with KnowledgeGraph instances."""
        inserted_graph = Graph()

        # Add graphs instances to nexus graph
        nexus_graphs = self.list_nexus_graphs()
        nexus_graph_uris = [str(graph["uri"]) for graph in nexus_graphs]
        logger.debug(f"Nexus graph URIs: {nexus_graph_uris}")
        # Some triple-store adapters do not list empty named graphs after clear_graph().
        # Ensure the Nexus graph itself is always considered for registration.
        graph_uris = {URIRef(uri) for uri in self.__triple_store.list_graphs()}
        graph_uris.add(self.__nexus_graph_uri)
        for graph_uri in graph_uris:
            if str(graph_uri) not in nexus_graph_uris:
                logger.debug(f"🟢 Graph {str(graph_uri)} added to nexus graph")
                knowledge_graph, knowledge_graph_role = (
                    self.create_graph_to_nexus_graph(graph_uri)
                )
                inserted_graph += knowledge_graph_role.rdf()
                inserted_graph += knowledge_graph.rdf()

        self.__triple_store.insert(inserted_graph, graph_name=self.__nexus_graph_uri)
        return inserted_graph

    def list_nexus_agents(self, metadata: dict[str, URIRef] = {}) -> List[Dict]:
        return self._query_nexus_instances(URIRef(Agent._class_uri), metadata)

    def create_agent_to_nexus_graph(
        self,
        label: str,
        description: str | None = None,
        logo_url: str | None = None,
        system_prompt: str | None = None,
        class_name: str | None = None,
        module_path: str | None = None,
        class_path: str | None = None,
        has_intent: list[AgentIntent | URIRef | str] | None = None,
        has_tool: list[AgentTool | URIRef | str] | None = None,
        has_agent_role: list[AgentRole | URIRef | str] | None = None,
    ) -> Agent:
        agent = Agent(label=label)
        if description is not None:
            agent.description = description
        if logo_url is not None:
            agent.logo_url = logo_url
        if system_prompt is not None:
            agent.system_prompt = system_prompt
        if class_name is not None:
            agent.class_name = class_name
        if module_path is not None:
            agent.module_path = module_path
        if class_path is not None:
            agent.class_path = class_path
        if has_intent is not None:
            agent.has_intent = has_intent
        if has_tool is not None:
            agent.has_tool = has_tool
        if has_agent_role is not None:
            agent.has_agent_role = has_agent_role
        return agent

    def initialize_nexus_agents(self) -> Graph:
        """Ensure the Nexus graph is populated with Agent instances."""
        inserted_graph = Graph()

        # Create agent roles in nexus graph
        supervisor_role = AgentRole(
            label="Supervisor Agent",
            description="Agent capable of orchestrating other agents.",
        )
        inserted_graph += supervisor_role.rdf()
        core_role = AgentRole(
            label="Core Agent",
            description="Agent capable of performing core tasks.",
        )
        inserted_graph += core_role.rdf()
        ai_role = AgentRole(
            label="AI Agent",
            description="Agent to demonstrate AI provider capabilities.",
        )
        inserted_graph += ai_role.rdf()
        domain_role = AgentRole(
            label="Domain Agent",
            description="Agent capable of performing tasks related to the domain.",
        )
        inserted_graph += domain_role.rdf()
        application_role = AgentRole(
            label="Application Agent",
            description="Agent to chat with AI model.",
        )
        inserted_graph += application_role.rdf()

        # Add agents from engine modules to the API
        from naas_abi import ABIModule
        from naas_abi_core.services.agent.Agent import Agent as RuntimeAgent

        # Get all agents from engine modules
        abi_module = ABIModule.get_instance()
        module_agents = [
            cast(type[RuntimeAgent], agent_cls)
            for agent_cls in abi_module.agents
            if isinstance(agent_cls, type) and issubclass(agent_cls, RuntimeAgent)
        ]
        agents: list[type[RuntimeAgent]] = []
        agents.extend(module_agents)

        for module in abi_module.engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                if isinstance(agent_cls, type) and issubclass(agent_cls, RuntimeAgent):
                    agents.append(cast(type[RuntimeAgent], agent_cls))

        # create agents in nexus graph
        nexus_agents = self.list_nexus_agents(
            metadata={"class_path": URIRef(self.__nexus_namespace["class_path"])}
        )
        logger.debug(f"Nexus agents: {nexus_agents}")
        nexus_agent_class_paths = {agent["class_path"] for agent in nexus_agents}
        for agent_cls in agents:
            module_name = str(agent_cls.__module__)
            class_name = str(agent_cls.__name__)
            class_path = f"{module_name}/{class_name}"
            if class_path in nexus_agent_class_paths:
                continue

            name = getattr(agent_cls, "name", None)
            if not isinstance(name, str) or name is None:
                continue
            logger.info(f"Adding agent '{name}' ({class_path}) to nexus graph")

            description = getattr(agent_cls, "description", None)
            logo_url = getattr(agent_cls, "logo_url", None)
            system_prompt = getattr(agent_cls, "system_prompt", None)

            if (
                isinstance(logo_url, str)
                and logo_url
                and not (
                    logo_url.startswith("http://") or logo_url.startswith("https://")
                )
            ):
                top_level_module = _module_name_from_module_path(module_name)
                if top_level_module and top_level_module in logo_url:
                    normalized_path = _normalize_logo_path_for_module(
                        logo_url, top_level_module
                    )
                    logo_url = _public_modules_url(
                        public_api_host=str(
                            abi_module.configuration.global_config.public_api_host
                        ),
                        path=normalized_path,
                    )

            if system_prompt is None and hasattr(agent_cls, "get_system_prompt"):
                system_prompt = agent_cls.get_system_prompt(cls=agent_cls)
            tools = getattr(agent_cls, "tools", None)
            if tools is None and hasattr(agent_cls, "get_tools"):
                tools = agent_cls.get_tools(cls=agent_cls)
            intents = getattr(agent_cls, "intents", None)
            if intents is None and hasattr(agent_cls, "get_intents"):
                intents = agent_cls.get_intents(cls=agent_cls)

            agent_tools: list = []
            if isinstance(tools, list):
                for tool in tools:
                    if not isinstance(tool, dict):
                        continue
                    agent_tool = AgentTool(
                        label=str(tool.get("name") or tool.get("type") or ""),
                        description=str(tool.get("description", "")),
                    )
                    inserted_graph += agent_tool.rdf()
                    agent_tools.append(agent_tool)

            agent_intents: list = []
            if isinstance(intents, list):
                for intent in intents:
                    agent_intent = AgentIntent(
                        label=intent.intent_value,
                        intent_value=intent.intent_value,
                        intent_type=intent.intent_type,
                        intent_target=intent.intent_target,
                        intent_scope=intent.intent_scope,
                    )
                    inserted_graph += agent_intent.rdf()
                    agent_intents.append(agent_intent)

            agent_roles: list = []
            if "naas_abi." in module_name:
                agent_roles.append(supervisor_role)
            elif "naas_abi_core." in module_name:
                agent_roles.append(core_role)
            elif "naas_abi_marketplace.ai." in module_name:
                agent_roles.append(ai_role)
            elif "naas_abi_marketplace.applications." in module_name:
                agent_roles.append(application_role)
            elif "naas_abi_marketplace.domains." in module_name:
                agent_roles.append(domain_role)

            agent = self.create_agent_to_nexus_graph(
                label=name,
                description=description,
                logo_url=logo_url,
                system_prompt=system_prompt,
                class_name=agent_cls.__name__,
                module_path=agent_cls.__module__,
                class_path=class_path,
                has_intent=agent_intents,
                has_tool=agent_tools,
                has_agent_role=agent_roles,
            )
            inserted_graph += agent.rdf()

        print(inserted_graph.serialize(format="turtle"))
        self.__triple_store.insert(inserted_graph, graph_name=self.__nexus_graph_uri)
        return inserted_graph

    def list_nexus_graph_views(self, metadata: dict[str, URIRef] = {}) -> List[Dict]:
        return self._query_nexus_instances(URIRef(GraphView._class_uri), metadata)

    def create_graph_view_to_nexus_graph(
        self,
        label: str,
        has_graph_filter: list[GraphFilter | URIRef | str],
        includes_knowledge_graph: list[KnowledgeGraph | URIRef | str],
    ) -> GraphView:
        graph_view = GraphView(
            label=label,
            has_graph_filter=has_graph_filter,
            includes_knowledge_graph=includes_knowledge_graph,
        )
        return graph_view

    def initialize_nexus_graph_views(self) -> Graph:
        """Ensure the Nexus graph is populated with GraphView instances."""
        inserted_graph = Graph()

        # Agent view
        graph_filter = GraphFilter(
            label="Filter Nexus Agent",
            predicate_uri=RDF.type,
            object_uri=URIRef(Agent._class_uri),
        )
        inserted_graph += graph_filter.rdf()

        agent_view = self.create_graph_view_to_nexus_graph(
            label="Agent",
            has_graph_filter=[graph_filter],
            includes_knowledge_graph=[self.__nexus_graph_uri],
        )
        inserted_graph += agent_view.rdf()

        # # Graph view
        # graph_filter = GraphFilter(
        #     label="Filter Nexus Graph Views",
        #     predicate_uri=RDF.type,
        #     object_uri=URIRef(GraphView._class_uri),
        # )
        # inserted_graph += graph_filter.rdf()

        # graph_view = self.create_graph_view_to_nexus_graph(
        #     label="Graph View",
        #     has_graph_filter=[graph_filter],
        #     includes_knowledge_graph=[
        #         self.__nexus_graph_uri,
        #         "http://ontology.naas.ai/graph/schema",
        #     ],
        # )
        # inserted_graph += graph_view.rdf()

        self.__triple_store.insert(inserted_graph, graph_name=self.__nexus_graph_uri)
        return inserted_graph

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, NexusPlatformPipelineParameters):
            raise ValueError(
                "Parameters must be of type NexusPlatformPipelineParameters"
            )

        # Initialize Nexus Platform
        from rdflib.namespace import OWL, RDF, RDFS, XSD

        graph = Graph()
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        graph.bind("nexus", self.__nexus_namespace)

        graph += self.initialize_nexus_graphs()
        graph += self.initialize_nexus_agents()
        graph += self.initialize_nexus_graph_views()
        return graph

    def as_tools(self) -> list[BaseTool]:
        return []

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        # Nexus initialization is handled during engine startup.
        return None


if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])
    triple_store = engine.services.triple_store

    store = triple_store

    pipeline = NexusPlatformPipeline(
        NexusPlatformPipelineConfiguration(triple_store=store)
    )
    pipeline.run(NexusPlatformPipelineParameters())
