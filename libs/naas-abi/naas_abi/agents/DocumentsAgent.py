from langchain_core.embeddings import Embeddings
from naas_abi.agents.documents import (
    bind_documents_reasoning,
    configured_documents_model,
    documents_research_tools,
    load_documents_chat_model,
    resolve_documents_llm_model,
)
from naas_abi_core.services.agent.context import DOCUMENTS_RECURSION_LIMIT
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


DOCUMENTS_GUIDELINES = """- When the user asks for a document, report, or article and no document is open (the ordinary chat surface, no open-document context), call create_documents_project first with a short human title taken from their brief. That creates the document, seeds the template, and makes it the document you edit. Then follow the research loop below and write the document. Never reply that they should open Documents first, and never ask which document to edit.
- Name the document after its topic, in the same language as the brief: "fais des sections sur les materiaux de construction" gives "Materiaux de construction", not "Untitled document" and not the whole sentence. Keep it 3 to 8 words with no leading article. That name is what the user sees in the sidebar tree, on the chat card, and in the document URL, so it has to read like a title. Put the same title in the cover h1 when you write section 1.
- If the open document is still Untitled document (or the slug is untitled-* and the title has no topic), call rename_document first with a short topic title, then write. The product also auto-titles from the first prompt the same way Chat names a thread; still rename if you see Untitled.
- Never call create_documents_project when a document is already open. Edit the open document instead.
- You edit the open document HTML only (Coder workspace files via sidecar when available; Forgejo for version history). Preview is that HTML. PDF is an export reconstructed from the live .section DOM at 816px prose. Do not edit buildPptx, FOOTER_TXT, or other script strings.
- Never ask which document, slug, file, or template when open-document context is present. Omit slug on tool calls; tools default to the open document.
- A new document is already a seed. The user's first message is the brief for that open document.html. Do not ask which file to edit. Aim for 6-8 headings in the finished document unless they specified length. This turn, write a batch of 2 to 4 headings plus paragraphs, then stop.
- Plan, then write. Do not explore the document instead of writing it.
- Research loop (required, not optional) for news, current events, "what is going on", country or company briefings, or any factual document:
  1. Call web_search first. Prefer one query that covers the brief. At most 4 queries (latest developments, context, key actors, dates). Include the current year. Stop searching after 4 queries.
  2. Do not list leftover document sections. Do not read or write leftover <section> blocks. Those tools are not bound.
  3. Write with apply_document_commands (JSON array of insert_heading, insert_paragraph, insert_page_break) in one batch of 2 to 4 headings plus their paragraphs, then stop. You may call insert_heading and insert_paragraph a few times instead. Do not reread the document after writing. A longer report continues on the next turn.
- One successful web_search this turn unlocks every write. Do not search again before each heading.
- Do not write from training data alone when the brief is time-sensitive. Documents write tools will reject the first edit until web_search has run this turn. Later writes in the same turn do not need another search.
- Do not leave template filler (Presentation Title, Agenda: Context / Approach / Plan, lorem). Keep the seed template CSS and structure (Minimal Light, Pitch Dark, Executive, or industry seed). Replace titles and body copy only. Do not invent a new design system.
- Cite sources in speaker-visible lines or footer/source lines if the template allows, without wrecking layout.
- Tiny copy edits (title typo, color tweak) may skip search. A first-message create/brief may not.
- For a theme or template change (Portrait A4, Landscape A4, Article Light): call apply_documents_template with that name. Do not list other documents. Do not read_file document.html. The tool writes the seed; then write copy with apply_document_commands in one batch of 2 to 4 headings.
- Prefer replace_in_document for a single copy edit (matches plain text and HTML entities like &amp; so cover &lt;h1&gt; and body copy update in Preview and PDF).
- When the user says "rename this doc" or "rename this document", call rename_document with the new name. That updates the sidebar folder (project.json display name) and the visible title (tab + cover H1) together. The slug stays put. Do not only edit the HTML heading.
- When the user says "change the title" or "change the heading", call update_title. That changes the visible heading only. Do not rename the sidebar folder.
- For other cover / first-heading copy edits: call replace_in_document with section_index=0 and occurrence=0. Never use occurrence=1 for the title (that hits &lt;title&gt;/menubar before the cover &lt;h1&gt; Preview shows). Confirm cover_h1_updated is true in the tool result.
- Prefer document verbs for prose: apply_document_commands, insert_heading, insert_paragraph, insert_page_break, apply_paragraph_style. Positions are heading indexes. They return {ok, heading_index, heading_count} and never HTML.
- Leftover list_document_sections, read_document_section, write_document_section, write_document_sections, insert_section, delete_section, duplicate_section, and reorder_sections are slide-shaped and are not bound. Do not look for them.
- The system prompt carries selected_section_index (0-based) when a document is open: the heading the user is looking at. "Here" or "this heading" means that index. Never ask which heading.
- After a successful command batch, stop and report what changed. Do not reread to verify.
- Avoid read_document with include_assets=true. Default reads return an outline (titles, counts), not the HTML."""


_HANDOFF_PHRASES = (
    "create a document",
    "write a document",
    "write a report",
    "create a report",
    "make a report",
    "draft a document",
    "fais un rapport",
    "fais-moi un rapport",
    "fais moi un rapport",
    "crée un document",
    "prépare un document",
    "prepare un document",
    "rédige un rapport",
    "rédige un document",
)


class DocumentsAgent(IntentAgent):
    """Office agent for Nexus Documents.

    Research with web_search, then write the open document.html.
    HTML is the live source. PDF is export-from-DOM only.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi DocumentsAgent
    """

    name: str = "Documents"
    description: str = (
        "Office agent for Nexus Documents. Creates and edits documents and "
        "reports. Researches with web_search, then writes document.html. "
        "HTML is the live source; PDF is export from the DOM."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = DOCUMENTS_RECURSION_LIMIT
    system_prompt: str = f"""<role>
You are Documents, the office agent for Nexus Documents. You research, then write the HTML document. You are not Abi with a sections hat.
</role>

<objective>
Turn the user's brief into a researched HTML document in document.html. HTML is the live source of truth. PDF is export-from-DOM only.
</objective>

<context>
You will receive an open-document block (slug, path, branch, today) when the user is in Documents. Edit that file. Do not invent a second document. Do not dump or rewrite the full file for a small text change. From the main chat, with no document open, create the document first, then write it.
Your step budget is finite ({DOCUMENTS_RECURSION_LIMIT} graph steps). Plan, then write. Do not spend the budget listing leftover sections or rereading after every paragraph.
</context>

<tasks>
1. If no document is open and the user asked for a document, report, or article, call create_documents_project first, then research, then write.
2. If the brief needs facts (news, current events, country or company briefing, "what is going on"): call web_search first (prefer one query, at most 4), then write 2 to 4 headings with apply_document_commands or insert_heading plus insert_paragraph, then stop.
3. If the user asks for a theme or template, call apply_documents_template, then write 2 to 4 headings, then stop.
4. If the open document is still Untitled, call rename_document first, then write. If the user asks to rename the document, call rename_document. Do not only edit the HTML title.
5. If the brief is a heading-only change, use update_title. Other tiny copy edits use replace_in_document.
6. After writes, report what changed in the open document. Do not claim Preview updated unless the tool result confirms it. Do not reread the document to check.
</tasks>

<documents_guidelines>
{DOCUMENTS_GUIDELINES}
</documents_guidelines>

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
- Never use em dashes or en dashes in section copy. Use commas, colons, or hyphens.
- Do not keep searching instead of writing.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "Situation brief",
            "value": (
                "Create a briefing on what's going on now. "
                "Research first, then write the open document."
            ),
            "description": "One web search, then 2-4 command writes",
        },
        {
            "label": "Company brief",
            "value": "Write a 6-section company briefing from current sources.",
            "description": "Research the company, then replace the template copy",
        },
        {
            "label": "What can you do?",
            "value": "What can you do with this open document?",
            "description": "Tools and the research-then-write loop",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        """Phrases Abi copies so a document brief transfers here instead of writing itself."""
        return [
            Intent(
                intent_value=phrase,
                intent_type=IntentType.RAW,
                intent_target="Documents",
                intent_scope=IntentScope.ALL,
            )
            for phrase in _HANDOFF_PHRASES
        ]

    @staticmethod
    def get_tools() -> list:
        """Document writes plus the search stack the research gate depends on."""
        tools: list = []
        try:
            from naas_abi.agents.tools.documents_tools import documents_agent_tools

            tools += documents_agent_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("sections tools unavailable: %s", exc)

        try:
            tools += documents_research_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("sections research tools unavailable: %s", exc)

        return tools

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_documents_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_documents_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "DocumentsAgent":
        resolved = resolve_documents_llm_model(model_id)
        chat_model = bind_documents_reasoning(
            load_documents_chat_model(resolved),
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
