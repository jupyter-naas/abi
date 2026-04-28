from pathlib import Path
from typing import Optional

from langchain_core.embeddings import Embeddings
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)


class _NoopEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        del text
        return [0.0]


class OntologyEngineerAgent(IntentAgent):
    """
    Ontology Engineer Agent.

    Run agent in terminal: LOG_LEVEL=DEBUG uv run abi chat ontology_engineer OntologyEngineerAgent
    """

    name: str = "Ontology Engineer"
    description: str = (
        "Ontology specialist grounded on the BFO 7 Buckets framework to answer "
        "ontology questions and propose ontology-compliant modeling."
    )
    logo_url: str = (
        "https://triplydb.com/imgs/avatars/d/6000a72bcbf91b03347f4a93.png?v=1"
    )
    system_prompt: str = """<role>
You are an ontology engineering specialist focused on BFO and the 7 Buckets framework.
</role>

<objective>
Help users understand ontologies by providing precise, practical, and ontology-grounded insights.
</objective>

<context>
Use the following ontology as the primary grounding source:
[BFO_7_BUCKETS_ONTOLOGY]
</context>

<tasks>
1. Answer ontology questions using the grounded ontology first, then explain clearly in plain language.
2. When users ask for ontology creation (new classes or properties), produce ontology snippets that follow the same style and standards as the grounding ontology.
3. Keep answers operational: include relevant classes/properties, rationale, and valid Turtle snippets when modeling is requested.
</tasks>

<operating_guidelines>
- Always use the BFO 7 Buckets framework as the conceptual basis.
- For a new class:
  - Declare it as `a owl:Class`.
  - Provide `rdfs:label`.
  - Provide `skos:definition`.
  - Provide `skos:example`.
  - Include relevant `rdfs:subClassOf` and OWL restrictions aligned with BFO modeling patterns.
- For a new object property:
  - Declare it as `a owl:ObjectProperty`.
  - Always include `rdfs:label` and `skos:definition`.
  - Add `rdfs:domain` and `rdfs:range` whenever they are known, implied, or needed for clarity and consistency.
  - Include `owl:inverseOf` when a clear inverse relation exists.
</operating_guidelines>

<constraints>
- Preserve the user language.
- Be concise and precise.
- If uncertainty remains, ask a focused clarification question before generating ontology artifacts.
</constraints>
"""

    @staticmethod
    def get_model(
        api_key: str,
        model_name: str = "gpt-5.1",
        base_url: str = "https://api.openai.com/v1",
        provider: str = "openai",
    ) -> ChatModel:
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        return ChatModel(
            model_id=model_name,
            provider=provider,
            model=ChatOpenAI(
                model=model_name,
                base_url=base_url,
                api_key=SecretStr(api_key),
            ),
        )

    @staticmethod
    def get_bfo_7_buckets_ontology() -> str:
        ontology_path = (
            Path(__file__).resolve().parent.parent
            / "ontologies"
            / "imports"
            / "domain-level"
            / "BFO7BucketsProcessOntology.ttl"
        )

        if ontology_path.exists():
            return ontology_path.read_text(encoding="utf-8")

        return (
            "Ontology file not found at "
            "`naas_abi/ontologies/imports/domain-level/BFO7BucketsProcessOntology.ttl`."
        )

    @classmethod
    def _build_agent(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "OntologyEngineerAgent":
        from naas_abi import ABIModule

        api_key = (
            ABIModule.get_instance()
            .engine.modules["naas_abi_marketplace.ai.chatgpt"]
            .configuration.openai_api_key
        )

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace(
                    "[BFO_7_BUCKETS_ONTOLOGY]", cls.get_bfo_7_buckets_ontology()
                )
            )

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=cls.get_model(api_key=api_key),
            tools=[],
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
    ) -> "OntologyEngineerAgent":
        return cls._build_agent(
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
        )


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> OntologyEngineerAgent:
    return OntologyEngineerAgent._build_agent(
        agent_shared_state=agent_shared_state,
        agent_configuration=agent_configuration,
    )
