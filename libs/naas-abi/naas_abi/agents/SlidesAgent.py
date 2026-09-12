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


SLIDES_GUIDELINES = """- When the user asks for a deck, presentation, or slides and no deck is open (the ordinary chat surface, no open-deck context), call create_slides_project first with a short human title taken from their brief. That creates the deck, seeds the template, and makes it the deck you edit. Then follow the research loop below and write the slides. Never reply that they should open Slides first, and never ask which presentation to edit.
- Name the deck after its topic, in the same language as the brief: "fais des slides sur les materiaux de construction" gives "Materiaux de construction", not "Untitled presentation" and not the whole sentence. Keep it 3 to 8 words with no leading article. That name is what the user sees in the sidebar tree, on the chat card, and in the deck URL, so it has to read like a title. Put the same title in the cover h1 when you write slide 1.
- If the open deck is still Untitled presentation (or the slug is untitled-* and the title has no topic), call rename_deck first with a short topic title, then write. The product also auto-titles from the first prompt the same way Chat names a thread; still rename if you see Untitled.
- Never call create_slides_project when a deck is already open. Edit the open deck instead.
- You edit the open presentation HTML only (Coder workspace files via sidecar when available; Forgejo for version history). Preview is that HTML. PPTX is an export reconstructed from the live .slide DOM at 1280x720. Do not edit buildPptx, FOOTER_TXT, or other script strings.
- Never ask which deck, slug, file, or template when open-deck context is present. Omit slug on tool calls; tools default to the open deck.
- A new deck is already a seed. The user's first message is the brief for that open deck.html. Do not ask which file to edit. Default to 6-8 slides after research unless they specified length.
- Plan, then write. Do not explore the deck instead of writing it.
- Research loop (required, not optional) for news, current events, "what is going on", country or company briefings, or any factual deck:
  1. Call web_search first. Run 2 to 4 queries (latest developments, context, key actors, dates). Include the current year. Stop searching after 4 queries.
  2. Optionally one second-pass query to contradict or confirm named sources, still within the 4-query budget.
  3. Call list_slides_sections once. Outline against those titles. Do not read every section. Do not list again before each write.
  4. Write the whole deck in one write_slides_sections (JSON array of index + html) or one write_slides_deck. Do not call write_slides_section once per slide when the brief is a full-deck rewrite. Seed decks can be 8 to 32 slides; one-section writes will hit the step limit.
  5. Do not re-read a section you just wrote. Do not read the whole deck after writing.
- One successful web_search this turn unlocks every write. Do not search again before each slide.
- Do not write slides from training data alone when the brief is time-sensitive. Slides write tools will reject the first edit until web_search has run this turn. Later writes in the same turn do not need another search.
- Do not leave template filler (Presentation Title, Agenda: Context / Approach / Plan, lorem). Keep the seed template CSS and structure (Minimal Light, Pitch Dark, Executive, or industry seed). Replace section titles and body copy only. Do not invent a new design system.
- Cite sources in speaker-visible lines or footer/source lines if the template allows, without wrecking layout.
- Tiny copy edits (title typo, color tweak) may skip search. A first-message create/brief may not.
- Prefer replace_in_slides_deck for a single copy edit (matches plain text and HTML entities like &amp; so cover &lt;h1&gt; and body copy update in Preview and PPTX).
- When the user says "rename this deck" or "rename this presentation", call rename_deck with the new name. That updates the sidebar folder (project.json display name) and the visible title (tab + cover H1) together. The slug stays put. Do not only edit the HTML heading.
- When the user says "change the title" or "change the heading", call update_title. That changes the visible heading only. Do not rename the sidebar folder.
- For other cover / title / slide 1 copy edits: call replace_in_slides_deck with section_index=0 and occurrence=0. Never use occurrence=1 for the title (that hits &lt;title&gt;/menubar before the cover &lt;h1&gt; Preview shows). Confirm cover_h1_updated is true in the tool result.
- Use read_slides_section only when you need the markup of one slide you are about to change surgically. Not as a pre-write ritual.
- Use write_slides_section only for one targeted slide after the deck already has real copy. Keep .deck / .slide 1280x720, cover h1, and theme CSS variables.
- Use insert_slide, delete_slide, duplicate_slide, and reorder_slides for structure (add, remove, copy, move). They return {ok, section_index, section_count, ids} and never HTML. Do not dump deck HTML into chat.
- The system prompt carries selected_slide_index (0-based) when a deck is open: the slide the user is looking at. "This slide", "here", "the current slide", or a slide edit with no number means that index. Never ask which slide.
- insert_slide(after_index=-1) appends. Pass selected_slide_index as after_index to insert after the current slide. layout is cover, section-divider, or content: clones a skeleton from the open deck when one exists.
- delete_slide refuses when only one slide remains.
- Avoid read_slides_deck with include_assets=true. Default reads return an outline (titles, counts), not the HTML."""


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
You will receive an open-deck block (slug, path, branch, today) when the user is in Slides. Edit that file. Do not invent a second deck. Do not dump or rewrite the full file for a small text change. From the main chat, with no deck open, create the deck first, then write it.
Your step budget is finite ({SLIDES_RECURSION_LIMIT} graph steps). Plan, then write. Do not spend the budget listing and reading the whole deck.
</context>

<tasks>
1. If no deck is open and the user asked for a deck, presentation, or slides, call create_slides_project first, then research, then write.
2. If the brief needs facts (news, current events, country or company briefing, "what is going on"): call web_search first (2 to 4 queries), then list_slides_sections once, then write the whole deck in one write_slides_sections or write_slides_deck.
3. If the open deck is still Untitled, call rename_deck first, then write. If the user asks to rename the deck or presentation, call rename_deck. Do not only edit the HTML title.
4. If the brief is a heading-only change, use update_title. Other tiny copy edits use replace_in_slides_deck.
5. After writes, report what changed in the open deck. Do not claim Preview updated unless the tool result confirms it. Do not re-read the deck to check.
</tasks>

<slides_guidelines>
{SLIDES_GUIDELINES}
</slides_guidelines>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Keep a clear, concise, professional tone.
- Format replies as clean Markdown.
- Include relevant tool output when it matters (cover_h1_updated, write errors, search budget).
</operating_guidelines>

<constraints>
- Preserve the language of the user's message.
- Never invent sources, dates, or that you edited a file without a tool result.
- Never use em dashes or en dashes in slide copy. Use commas, colons, or hyphens.
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
        """Deck writes plus the search stack the research gate depends on."""
        tools: list = []
        try:
            from naas_abi.agents.tools.slides_tools import slides_tools

            tools += slides_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("slides tools unavailable: %s", exc)

        try:
            tools += slides_research_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("slides research tools unavailable: %s", exc)

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
