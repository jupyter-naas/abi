from langchain_core.embeddings import Embeddings
from naas_abi.agents.slides import (
    bind_slides_reasoning,
    configured_slides_model,
    load_slides_chat_model,
    resolve_slides_llm_model,
    slides_research_tools,
)
from naas_abi_core.services.agent.context import SLIDES_RECURSION_LIMIT
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentScope,
    IntentType,
)


class _NoopEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        del text
        return [0.0]


# The only deck tools the model is shown. ``slides_tools()`` also builds the
# raw HTML writers (write_slides_section, write_slides_sections,
# write_slides_deck) for the HTTP API and the code editor; the model never
# sees them. Every tool named in the procedure below is in this tuple and
# nothing else is.
SLIDES_ALLOWED_TOOLS = (
    "create_slides_project",
    "build_slides_deck",
    "replace_in_slides_deck",
    "insert_slide",
    "delete_slide",
    "duplicate_slide",
    "reorder_slides",
    "slides_history",
)
# Research is web_search only. web_fetch is how the model went off-procedure
# (fetched a page, then wrote HTML from it).
_SLIDES_SUPPORT_TOOLS = ("web_search",)

# The procedure. One copy, in the prompt. Each step names the one tool that
# does it and what its result must show before the model moves on. A second
# copy of these steps anywhere else is a bug: the model follows whichever one
# it read last.
SLIDES_PROCEDURE = """The deck is HTML. You never write that HTML. Each step below names the one tool that does it and what its result must show before you move on. If the tool is not listed here, you do not have it.

## 1. Target the deck

The open-deck block gives `slug`, `slide_count`, and `selected_slide_index`. Omit `slug` on every call. "This slide", "here", or no slide means `selected_slide_index`. Indexes are 0-based: slide 2 is 1. Do not ask which deck or which slide.

If no deck is open, call `create_slides_project` once with a short title in the user's language, 3 to 8 words, no leading article. "fais des slides sur les materiaux de construction" is "Materiaux de construction". Never the whole sentence, never "Untitled presentation".

Success: the block or the tool result shows a slug. Do not call `create_slides_project` again.

## 2. New briefing

1. `web_search` two to four times. Include the current year. Stop at four.
2. `build_slides_deck` once with the whole outline.

Each row is `{layout, title, subtitle, body}`. `layout` is `cover`, `section-divider`, or `content`. The first row is cover. Subtitle is one line, 80 characters or fewer. Body is a list of short bullets on content slides only. The deck is as long as the story, usually 8 to 14 slides. Do not stop at the number of slides in the seed. No HTML, no CSS, no lorem, no "Presentation Title", no "Agenda: Context / Approach / Plan".

Success: `ok` is true, `rejected` is empty, `section_count` is 8 or more. If `rejected` is not empty, shorten those rows and call `build_slides_deck` again. Do not read the deck afterwards.

## 3. Copy edit

`replace_in_slides_deck` with plain text. For the cover title pass `section_index` 0 and `occurrence` 0.

Success: `replacements` is 1 or more. Cover title: `cover_h1_updated` is true.

## 4. Structure

| Job | Tool | Success |
| --- | --- | --- |
| Add one slide | `insert_slide` | `section_count` grew by 1 |
| Remove a slide | `delete_slide` | `section_count` shrank by 1 |
| Copy a slide | `duplicate_slide` | `section_count` grew by 1 |
| Move a slide | `reorder_slides` | `ids` in the new order |

## Rules

- One write per request, then report what changed from the tool result. Do not claim Preview updated unless the result says so.
- You have no tool that places a photo. If the user asks for one, say so in one sentence and do the rest of the request.
- Do not set `top`, `left`, or `width`. Do not touch `buildPptx` or `FOOTER_TXT`.
- Do not re-read the deck after a write.
- No em dashes or en dashes in slide copy.
- Keep the user's language."""


_HANDOFF_PHRASES = (
    "create a presentation",
    "create a deck",
    "make slides",
    "build slides",
    "write a deck",
    "fais des slides",
    "crée une présentation",
    "crée une presentation",
    "prépare un diaporama",
    "prepare un diaporama",
    "monte un diaporama",
    "rédige une présentation",
)


class SlidesAgent(IntentAgent):
    """Office agent for Nexus Slides.

    Research 2 to 4 web_search queries, then write the open deck.html.
    HTML is the live source. PPTX is export-from-DOM only.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi SlidesAgent
    """

    name: str = "Slides"
    description: str = (
        "Office agent for Nexus Slides. Creates and edits slide decks and "
        "presentations. Researches with web_search, then writes deck.html. "
        "HTML is the live source; PPTX is export from the DOM."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = SLIDES_RECURSION_LIMIT
    system_prompt: str = f"""<role>
You are Slides, the office agent for Nexus Slides. You research, then write the HTML deck. You are not Abi with a slides hat.
</role>

<objective>
Turn the user's brief into a researched HTML presentation in deck.html. HTML is the live source of truth. PPTX is export-from-DOM only.
</objective>

<context>
You will receive an open-deck block (slug, path, branch, today, slide_count, selected_slide_index) when the user is in Slides. Edit that deck. Do not invent a second one. From the main chat, with no deck open, create the deck first, then write it.
Your step budget is finite ({SLIDES_RECURSION_LIMIT} graph steps). Plan, then write.
</context>

<procedure>
{SLIDES_PROCEDURE}
</procedure>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Keep a clear, concise, professional tone. Format replies as clean Markdown.
- Quote the tool result fields the procedure names as success (section_count, cover_h1_updated, replacements, error).
- Questions about how Slides is built: read naas_abi/agents/SlidesAgent.py, then naas_abi/tools/slides_tools.py. Cite the paths you read.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message.
- Never invent sources, dates, or that you edited a file without a tool result.
- Do not keep searching instead of writing.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "Situation brief",
            "value": (
                "Create a briefing on what's going on now. "
                "Research first, then write the open deck."
            ),
            "description": "2 to 4 web searches, then one outline build",
        },
        {
            "label": "Company brief",
            "value": "Write a company briefing from current sources.",
            "description": "Research the company, then build the deck from an outline",
        },
        {
            "label": "What can you do?",
            "value": "What can you do with this open deck?",
            "description": "Tools and the research-then-write loop",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        """Phrases Abi copies so a deck brief transfers here instead of writing itself."""
        return [
            Intent(
                intent_value=phrase,
                intent_type=IntentType.RAW,
                intent_target="Slides",
                intent_scope=IntentScope.ALL,
            )
            for phrase in _HANDOFF_PHRASES
        ]

    @staticmethod
    def get_tools() -> list:
        """``SLIDES_ALLOWED_TOOLS``, plus web_search and read-only source tools.

        ``slides_tools()`` also builds the raw HTML writers the HTTP API and
        the code editor use. The model never sees those: every deck tool it
        is shown is named in ``SLIDES_PROCEDURE``. Anything else is an escape
        hatch from the procedure.
        """
        tools: list = []
        try:
            from naas_abi.tools.slides_tools import slides_tools

            allowed = set(SLIDES_ALLOWED_TOOLS)
            tools += [t for t in slides_tools() if t.name in allowed]
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("slides tools unavailable: %s", exc)

        try:
            support = set(_SLIDES_SUPPORT_TOOLS)
            tools += [t for t in slides_research_tools() if t.name in support]
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("slides research tools unavailable: %s", exc)

        # Read-only source tools so "how is Slides built?" is answered from code.
        from naas_abi.tools.nexus_source_tools import nexus_source_tools

        tools += nexus_source_tools()
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
        chat_model = bind_slides_reasoning(
            load_slides_chat_model(resolved),
            resolved,
            force=True,
        )
        tools = cls.get_tools()

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        if agent_configuration is None:
            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            intents=cls.handoff_intents(),
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
            embedding_model=_NoopEmbeddings(),
            enable_default_intents=False,
            enable_default_tools=True,
        )
