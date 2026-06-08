import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, cast

from langchain_core.tools import BaseTool
from naas_abi.ontologies.modules.NexusPlatformOntology import (
    Agent,
    AgentIntent,
    AgentRole,
    AgentTool,
    AIModel,
    Capabilities,
    GraphFilter,
    GraphView,
    KnowledgeGraph,
    KnowledgeGraphRole,
)
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.utils.StorageUtils import StorageUtils
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDFS
from rdflib.query import ResultRow

# Bump when the schema of what the pipeline writes changes (so old signatures
# from older code versions trigger a rebuild even if inputs look identical).
_SIGNATURE_VERSION = "1"

_CCO = Namespace("https://www.commoncoreontologies.org/")
_CCO_ORGANIZATION = _CCO["ont00001180"]
_NEXUS_HAS_CAPABILITIES = URIRef("http://ontology.naas.ai/nexus/hasCapabilities")
_NEXUS_AI_MODEL_PROVIDER = URIRef("http://ontology.naas.ai/nexus/AIModelProvider")


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
    object_storage: ObjectStorageService
    datastore_path: str = "naas_abi/nexus"
    nexus_namespace: Namespace = Namespace("http://ontology.naas.ai/nexus/")
    nexus_graph_uri: URIRef = URIRef("http://ontology.naas.ai/graph/nexus")
    # When True, always clear + rebuild the nexus graph. When False (default),
    # compute a signature of the inputs (agent class paths + named graphs +
    # version) and skip the rebuild entirely if the stored signature matches.
    # This makes warm boots ~one SPARQL read instead of ~6 reads + writes.
    force_update: bool = False


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
    __object_storage: ObjectStorageService
    __storage_utils: StorageUtils

    def __init__(self, configuration: NexusPlatformPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__nexus_namespace = configuration.nexus_namespace
        self.__nexus_graph_uri = configuration.nexus_graph_uri
        self.__force_update = configuration.force_update
        self.__triple_store = configuration.triple_store
        self.__sparql_utils = SPARQLUtils(self.__triple_store)
        # Note: clearing the nexus graph used to happen here, which made
        # merely *constructing* the pipeline destructive. We've moved that
        # into run() so we can check the signature first and skip the rebuild
        # entirely when nothing has changed.
        self.__object_storage = configuration.object_storage
        self.__storage_utils = StorageUtils(self.__object_storage)

    # ------------------------------------------------------------------
    # Signature-based fast path
    # ------------------------------------------------------------------

    def _bootstrap_uri(self) -> URIRef:
        return URIRef(self.__nexus_namespace["Bootstrap"])

    def _signature_predicate(self) -> URIRef:
        return URIRef(self.__nexus_namespace["signature"])

    def _compute_signature(self) -> str:
        """Hash the inputs we'd write so we can detect a no-op rebuild.

        For each agent we include its class path AND the SHA-256 of the
        source file that defines it. Editing an agent's `system_prompt`,
        `get_tools()`, `get_intents()`, etc. changes the file's content
        hash, which changes the signature, which triggers a rebuild. We
        deliberately do NOT call `get_tools()` / `get_intents()` /
        `get_system_prompt()` here — those are the expensive operations
        the fast path is trying to avoid.

        Agent source files are typically small (a few KB), so reading and
        hashing them is cheap, and each file is hashed at most once even
        when it defines multiple agents.

        We also include sorted named graph URIs (so a newly loaded
        ontology triggers a rebuild) and a version tag.
        """
        import inspect

        from naas_abi import ABIModule
        from naas_abi_core.services.agent.Agent import Agent as RuntimeAgent

        agent_entries: list[str] = []
        try:
            abi = ABIModule.get_instance()
            # Cache file hashes so we don't read/hash the same module twice
            # when it defines multiple agents.
            file_hashes: dict[str, str] = {}
            for module in abi.engine.modules.values():
                for agent_cls in module.agents:
                    if (
                        agent_cls is None
                        or not isinstance(agent_cls, type)
                        or not issubclass(agent_cls, RuntimeAgent)
                    ):
                        continue
                    class_path = f"{agent_cls.__module__}/{agent_cls.__name__}"
                    try:
                        source_file = inspect.getfile(agent_cls)
                    except (TypeError, OSError):
                        source_file = ""
                    if source_file and source_file not in file_hashes:
                        try:
                            with open(source_file, "rb") as f:
                                file_hashes[source_file] = hashlib.sha256(
                                    f.read()
                                ).hexdigest()
                        except OSError:
                            file_hashes[source_file] = ""
                    agent_entries.append(
                        f"{class_path}@{file_hashes.get(source_file, '')}"
                    )
        except Exception:
            # If we can't enumerate agents we should not pretend the cache
            # is valid — fall through to a forced rebuild by returning a
            # signature that will never match.
            return "unavailable"

        graph_uris = sorted(str(g) for g in self.__triple_store.list_graphs())

        parts = [
            f"v:{_SIGNATURE_VERSION}",
            "agents:" + ",".join(sorted(agent_entries)),
            "graphs:" + ",".join(graph_uris),
        ]
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def _read_stored_signature(self) -> str | None:
        results = self.__triple_store.query(
            f"""
            SELECT ?sig WHERE {{
                GRAPH <{str(self.__nexus_graph_uri)}> {{
                    <{str(self._bootstrap_uri())}>
                        <{str(self._signature_predicate())}>
                        ?sig .
                }}
            }}
            """
        )
        for row in results:
            assert isinstance(row, ResultRow)
            return str(row[0])
        return None

    def _write_signature(self, signature: str) -> None:
        # Drop any prior signature triple(s) then write the new one.
        old_results = self.__triple_store.query(
            f"""
            SELECT ?sig WHERE {{
                GRAPH <{str(self.__nexus_graph_uri)}> {{
                    <{str(self._bootstrap_uri())}>
                        <{str(self._signature_predicate())}>
                        ?sig .
                }}
            }}
            """
        )
        old_graph = Graph()
        for row in old_results:
            assert isinstance(row, ResultRow)
            old_graph.add((self._bootstrap_uri(), self._signature_predicate(), row[0]))
        if len(old_graph) > 0:
            self.__triple_store.remove(old_graph, graph_name=self.__nexus_graph_uri)

        new_graph = Graph()
        new_graph.add(
            (
                self._bootstrap_uri(),
                self._signature_predicate(),
                Literal(signature),
            )
        )
        self.__triple_store.insert(new_graph, graph_name=self.__nexus_graph_uri)

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
        admin_role: KnowledgeGraphRole | None = None,
        unknown_role: KnowledgeGraphRole | None = None,
    ) -> tuple[KnowledgeGraph, KnowledgeGraphRole]:
        is_admin = any(token in str(uri).lower() for token in {"schema", "nexus"})
        if is_admin:
            knowledge_graph_role = admin_role or KnowledgeGraphRole(label="Admin")
        else:
            knowledge_graph_role = unknown_role or KnowledgeGraphRole(label="unknown")

        label = " ".join(
            word.capitalize()
            for word in uri.split("/")[-1].split("#")[-1].replace("_", " ").split()
        )

        knowledge_graph = KnowledgeGraph(
            _uri=uri,
            label=label,
            has_knowledge_graph_role=[knowledge_graph_role],
        )
        return knowledge_graph, knowledge_graph_role

    def initialize_nexus_graphs(self, _dry_run: bool = False) -> Graph:
        """Ensure the Nexus graph is populated with KnowledgeGraph instances."""
        inserted_graph = Graph()

        # Shared roles — created once so all graphs reference the same role URI.
        admin_role = KnowledgeGraphRole(label="Admin")
        inserted_graph += admin_role.rdf()
        unknown_role = KnowledgeGraphRole(label="unknown")
        inserted_graph += unknown_role.rdf()

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
                knowledge_graph, _ = self.create_graph_to_nexus_graph(
                    graph_uri, admin_role=admin_role, unknown_role=unknown_role
                )
                inserted_graph += knowledge_graph.rdf()

        if not _dry_run:
            self.__triple_store.insert(
                inserted_graph, graph_name=self.__nexus_graph_uri
            )
        return inserted_graph

    def list_nexus_agents(self, metadata: dict[str, URIRef] = {}) -> List[Dict]:
        return self._query_nexus_instances(URIRef(Agent._class_uri), metadata)

    def list_nexus_ai_providers(self) -> List[Dict]:
        return self._query_nexus_instances(_CCO_ORGANIZATION)

    def list_nexus_ai_models(self) -> List[Dict]:
        return self._query_nexus_instances(URIRef(AIModel._class_uri))

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
        has_subagent: list[Agent | URIRef | str] | None = None,
        uses_model: list[AIModel | URIRef | str] | None = None,
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
            for intent in has_intent:
                if isinstance(intent, AgentIntent):
                    intent.is_intent_of = [agent]
        if has_tool is not None:
            agent.has_tool = has_tool
        if has_agent_role is not None:
            agent.has_agent_role = has_agent_role
        if has_subagent is not None:
            agent.has_subagent = has_subagent
        if uses_model is not None:
            agent.uses_model = uses_model
        return agent

    def initialize_nexus_agents(self, _dry_run: bool = False) -> Graph:
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

        abi_agent_object: Agent | None = None
        sub_nexus_agents: list[Agent] = []

        # Create the unique AIModelProvider capability individual once.
        ai_model_provider_capability = Capabilities(
            _uri=str(_NEXUS_AI_MODEL_PROVIDER),
            label="AI Model Provider",
        )
        inserted_graph += ai_model_provider_capability.rdf()

        # Build label→URI lookup from already-persisted providers and models
        # so we reuse existing nodes instead of creating duplicates.
        provider_by_label: dict[str, URIRef] = {
            str(row["label"]): URIRef(str(row["uri"]))
            for row in self.list_nexus_ai_providers()
            if row.get("label") and row.get("uri")
        }
        model_by_label: dict[str, URIRef] = {
            str(row["label"]): URIRef(str(row["uri"]))
            for row in self.list_nexus_ai_models()
            if row.get("label") and row.get("uri")
        }

        for agent_cls in agents:
            module_name = str(agent_cls.__module__)
            class_name = str(agent_cls.__name__)
            class_path = f"{module_name}/{class_name}"
            if class_path in nexus_agent_class_paths:
                continue

            name = getattr(agent_cls, "name", None)
            if not isinstance(name, str) or name is None:
                continue
            logger.debug(f"Adding agent '{name}' ({class_path}) to nexus graph")

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
                    agent_intents.append(agent_intent)

            is_abi_agent = class_name == "AbiAgent"

            agent_roles: list = []
            if not is_abi_agent:
                if "naas_abi_core." in module_name:
                    agent_roles.append(core_role)
                elif "naas_abi_marketplace.ai." in module_name:
                    agent_roles.append(ai_role)
                elif "naas_abi_marketplace.applications." in module_name:
                    agent_roles.append(application_role)
                elif "naas_abi_marketplace.domains." in module_name:
                    agent_roles.append(domain_role)

            # Add AI provider (cco:ont00001180 instance) to nexus graph if not seen yet
            provider_name = getattr(agent_cls, "provider", None)
            org_uri: URIRef | None = None
            if isinstance(provider_name, str) and provider_name:
                if provider_name in provider_by_label:
                    org_uri = provider_by_label[provider_name]
                else:
                    import uuid as _uuid

                    new_org_uri = URIRef(f"http://ontology.naas.ai/abi/{_uuid.uuid4()}")
                    inserted_graph.add((new_org_uri, RDF.type, _CCO_ORGANIZATION))
                    inserted_graph.add((new_org_uri, RDF.type, OWL.NamedIndividual))
                    inserted_graph.add(
                        (new_org_uri, RDFS.label, Literal(provider_name))
                    )
                    inserted_graph.add(
                        (new_org_uri, _NEXUS_HAS_CAPABILITIES, _NEXUS_AI_MODEL_PROVIDER)
                    )
                    provider_by_label[provider_name] = new_org_uri
                    org_uri = new_org_uri

            # Add AI model to nexus graph if not seen yet
            model_id = getattr(agent_cls, "model", None)
            agent_model: AIModel | URIRef | None = None
            if isinstance(model_id, str) and model_id:
                if model_id in model_by_label:
                    agent_model = model_by_label[model_id]
                else:
                    new_model = AIModel(
                        label=model_id,
                        model_id=model_id,
                        has_provider=[org_uri] if org_uri else None,
                    )
                    inserted_graph += new_model.rdf()
                    model_by_label[model_id] = URIRef(new_model._uri)
                    agent_model = new_model

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
                has_agent_role=agent_roles or None,
                uses_model=[agent_model] if agent_model else None,
            )
            for agent_intent in agent_intents:
                inserted_graph += agent_intent.rdf()

            if is_abi_agent:
                abi_agent_object = agent
            else:
                sub_nexus_agents.append(agent)

        # Assign supervisor role and subagent links to AbiAgent only if it has subagents
        all_nexus_agents: list[Agent] = []
        if abi_agent_object is not None:
            if sub_nexus_agents:
                abi_agent_object.has_agent_role = [supervisor_role]
                abi_agent_object.has_subagent = [
                    URIRef(sub._uri) for sub in sub_nexus_agents
                ]
            all_nexus_agents.append(abi_agent_object)
        all_nexus_agents.extend(sub_nexus_agents)

        for agent in all_nexus_agents:
            inserted_graph += agent.rdf()

        if not _dry_run:
            self.__triple_store.insert(
                inserted_graph, graph_name=self.__nexus_graph_uri
            )
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

    def initialize_nexus_graph_views(self, _dry_run: bool = False) -> Graph:
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

        if not _dry_run:
            self.__triple_store.insert(
                inserted_graph, graph_name=self.__nexus_graph_uri
            )
        return inserted_graph

    def dry_run(self) -> Graph:
        """Build the full Nexus graph without touching the triple store.

        Saves the resulting triples to object storage at naas_abi/nexus/nexus.ttl
        so the output can be inspected without side-effects.
        """
        from rdflib.namespace import OWL, RDF, RDFS, XSD

        graph = Graph()
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        graph.bind("nexus", self.__nexus_namespace)

        graph += self.initialize_nexus_graphs(_dry_run=True)
        graph += self.initialize_nexus_agents(_dry_run=True)
        # graph += self.initialize_nexus_graph_views(_dry_run=True)

        self.__storage_utils.save_triples(
            graph=graph,
            dir_path="naas_abi/nexus",
            file_name="nexus.ttl",
        )
        logger.debug(
            f"[dry_run] Nexus graph ({len(graph)} triples) saved to naas_abi/nexus/nexus.ttl"
        )
        return graph

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, NexusPlatformPipelineParameters):
            raise ValueError(
                "Parameters must be of type NexusPlatformPipelineParameters"
            )

        # Initialize Nexus Platform
        from rdflib.namespace import OWL, RDF, RDFS, XSD

        # Fast path: if the inputs haven't changed since the last successful
        # rebuild, skip the whole pipeline. This is the common case on warm
        # API boots and turns ~6 SPARQL round trips + writes into 2 reads.
        current_signature = self._compute_signature()
        if not self.__force_update:
            stored_signature = self._read_stored_signature()
            if stored_signature is not None and stored_signature == current_signature:
                logger.debug("Nexus platform signature unchanged; skipping rebuild.")
                return Graph()

        # Ensure the nexus graph exists, then clear it so removed agents
        # don't linger. Clearing only happens on the rebuild path — pure
        # construction of the pipeline is now non-destructive.
        if self.__nexus_graph_uri not in self.__triple_store.list_graphs():
            self.__triple_store.create_graph(self.__nexus_graph_uri)
            logger.debug(f"Nexus graph created at {self.__nexus_graph_uri}")
        else:
            logger.debug(f"Nexus graph cleared at {self.__nexus_graph_uri}")
            self.__triple_store.clear_graph(self.__nexus_graph_uri)

        graph = Graph()
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        graph.bind("nexus", self.__nexus_namespace)

        graph += self.initialize_nexus_graphs()
        graph += self.initialize_nexus_agents()
        # graph += self.initialize_nexus_graph_views()

        # Persist the new signature so the next boot can short-circuit.
        self._write_signature(current_signature)
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
    object_storage = engine.services.object_storage

    pipeline = NexusPlatformPipeline(
        NexusPlatformPipelineConfiguration(
            triple_store=triple_store, object_storage=object_storage
        )
    )
    pipeline.run(NexusPlatformPipelineParameters())
