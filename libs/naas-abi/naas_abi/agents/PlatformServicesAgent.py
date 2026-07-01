from typing import Optional

from langchain_core.embeddings import Embeddings
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)

from naas_abi.agents.tools.platform_tools import platform_service_tools


class _NoopEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        del text
        return [0.0]


class PlatformServicesAgent(IntentAgent):
    """
    Platform Services Agent — a single entry point to the ABI platform's data
    services (knowledge graph, object storage, vector store, cache, key-value).

    Run agent in terminal: LOG_LEVEL=DEBUG uv run abi chat <module> PlatformServicesAgent
    """

    name: str = "Platform Services"
    description: str = (
        "Answers questions and runs operations across the platform's data "
        "services: the knowledge graph (SPARQL), object storage, vector store, "
        "cache, and key-value store."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    system_prompt: str = """<role>
You are the Platform Services agent. You give users direct access to the ABI
platform's data services so they can inspect and operate on their data.
</role>

<services>
- Knowledge graph (triple store): run SPARQL with `kg_sparql_query`, list named graphs with `kg_list_graphs`.
- Object storage: list objects with `storage_list_objects`, read one with `storage_get_object`.
- Vector store: list collections with `vector_list_collections`, get a collection size with `vector_collection_size`.
- Cache: `cache_get` / `cache_set`.
- Key-value store: `kv_get` / `kv_set`.
</services>

<tasks>
1. Pick the tool that matches the user's request and call it. Prefer a single, well-formed call.
2. For knowledge-graph questions, write a correct SPARQL query and run it with `kg_sparql_query`.
3. Report the actual tool output. If a tool returns an `error`, surface it plainly and suggest a fix.
</tasks>

<constraints>
- Only claim a result you actually got from a tool call. Never fabricate data.
- Keep responses concise; format tabular results as Markdown tables when helpful.
- These tools act on shared platform data — be careful with writes (`*_set`), and never invent destructive operations that aren't available to you.
</constraints>
"""

    @classmethod
    def _build_agent(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "PlatformServicesAgent":
        from naas_abi import ABIModule

        abi_module = ABIModule.get_instance()
        chat_model = abi_module.engine.services.model_registry.get_chat_model(
            abi_module.configuration.abi_agent_model,
            provider=abi_module.configuration.abi_agent_provider,
        )

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=platform_service_tools(),
            agents=[],
            intents=[],
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
            embedding_model=_NoopEmbeddings(),
            enable_default_intents=False,
        )

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "PlatformServicesAgent":
        return cls._build_agent(
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
        )


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> PlatformServicesAgent:
    return PlatformServicesAgent._build_agent(
        agent_shared_state=agent_shared_state,
        agent_configuration=agent_configuration,
    )
