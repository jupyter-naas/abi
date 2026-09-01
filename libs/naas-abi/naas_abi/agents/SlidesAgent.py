from langchain_core.embeddings import Embeddings
from naas_abi.skills.slides_policy import (
    SLIDES_AGENT_SYSTEM_PROMPT,
    configured_slides_model,
    load_slides_chat_model,
    resolve_slides_llm_model,
)
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


class SlidesAgent(IntentAgent):
    """Office agent for Nexus Slides.

    Research 2 to 4 web_search queries, then write the open deck.html.
    HTML is the live source. PPTX is export-from-DOM only.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi SlidesAgent
    """

    name: str = "Slides"
    description: str = (
        "Office agent for Nexus Slides. Researches with web_search, then writes "
        "the open deck.html. HTML is the live source; PPTX is export from the DOM."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = 80
    system_prompt: str = SLIDES_AGENT_SYSTEM_PROMPT
    suggestions: list[dict] = [
        {
            "label": "Situation brief",
            "value": (
                "Create a briefing on what's going on now. "
                "Research first, then write the open deck."
            ),
            "description": "2 to 4 web searches, then 6-8 researched slides",
        },
        {
            "label": "Company brief",
            "value": "Write a 6-slide company briefing from current sources.",
            "description": "Research the company, then replace the template copy",
        },
        {
            "label": "What can you do?",
            "value": "What can you do with this open deck?",
            "description": "Tools and the research-then-write loop",
        },
    ]

    @staticmethod
    def get_tools() -> list:
        """Explicit office set: deck writes, research, slides skill. Not Abi's sink."""
        tools: list = []
        try:
            from naas_abi.tools.slides_tools import slides_tools

            tools += slides_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("slides tools unavailable: %s", exc)

        try:
            from naas_abi.skills.slides_policy import attach_slides_research_note
            from naas_abi.tools.web_tools import (
                make_web_fetch_tool,
                make_web_search_tool,
            )

            tools += [
                attach_slides_research_note(make_web_search_tool()),
                make_web_fetch_tool(),
            ]
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("web search tools unavailable: %s", exc)

        try:
            from naas_abi.skills.office_skills import office_skill_tools

            tools += office_skill_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("office skills unavailable: %s", exc)

        return tools

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_slides_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_slides_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "SlidesAgent":
        resolved = resolve_slides_llm_model(model_id)
        chat_model = load_slides_chat_model(resolved)
        tools = cls.get_tools()

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        if agent_configuration is None:
            from naas_abi.skills.office_skills import load_office_skill

            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace(
                    "[TOOLS]", tools_section
                ).replace("[SKILL]", load_office_skill("slides"))
            )

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            intents=[],
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
            embedding_model=_NoopEmbeddings(),
            enable_default_intents=False,
            enable_default_tools=True,
        )
