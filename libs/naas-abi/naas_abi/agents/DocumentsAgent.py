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


DOCUMENTS_GUIDELINES = """- When no document is open, call create_documents_project with a short topic title in the same language as the brief. The server loads the configured template. An open document is never replaced by a new one.
- If the document is Untitled, call rename_document first. "Rename this document" changes its sidebar name and cover; "change the heading" uses update_title.
- Plan, then write. Read the current document before editing: read_document returns editable content and template_fields, including field names, types and current values. Do not guess a template's structure.
- Research loop: use web_search for factual briefs requiring sources, then fill the document. Use sources relevant to the brief and cite them in the content. Do not invent client names, fees, dates or sources.
- Fill the open template with fill_document_slots. Base content uses title, subtitle, intro, sections ({heading, body, bullets?}), quote and tables ({heading, headers, rows}). Extra business fields use fields: {field_name: value}. Values are text, lists of text, or {headers, rows}, as described by template_fields.
- Adapt the business fields to the brief, including client, scope, team and next steps when present. Do not leave seed placeholder copy or a Slides Context / Approach / Plan outline. Required information not provided by the user must be reported as missing, never invented.
- Preserve document.html styles, logos, headers and footers. Do not append after the footer. The server applies content to the template. Do not write scripts or assets.
- For a later copy edit, use apply_document_commands with an exact visible passage. An ambiguous selection requires a more precise passage. A failed edit may be corrected; a successful write completes the editing batch for this turn.
- For a template change use apply_documents_template, read its template_fields, then fill it. This replaces the existing content with a seed, so preserve content that the user wants to retain in the new fields.
- After writing, distinguish saved from complete: content_complete=false, missing_slots or leftover_placeholders mean the document still needs work. Report those omissions accurately. Do not claim the result is ready merely because ok=true.
- Do not reread repeatedly or retry an identical failing request. Once the editing batch succeeds, report the changes and any missing information. Do not write the memo only in chat.
- Styles: Title is the cover H1, Heading 1/2/3 are H2/H3/H4. selected_section_index identifies the heading currently selected in the editor.
"""


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

# Keep sticky Documents turns for follow-up edits; release meta chat / acknowledgements.
_DOCUMENT_TURN_MARKERS = (
    "document",
    "rapport",
    "report",
    "memo",
    "note au",
    "section",
    "titre",
    "title",
    "heading",
    "subtitle",
    "intro",
    "rename",
    "renomm",
    "template",
    "tableau",
    "table",
    "quote",
    "citation",
    "paragraphe",
    "paragraph",
    "bullet",
    "fill",
    "slot",
    "rewrite",
    "réécr",
    "reecr",
    "modifie",
    "change the",
    "change le",
    "ajoute",
    "add a",
    "add the",
    "update the",
    "board",
    "formal",
    "formel",
    "chaleureux",
    "warmer",
    "shorter",
    "plus court",
)

_RELEASE_STICKY_SHORT = frozenset(
    {
        "ah",
        "ok",
        "okay",
        "oui",
        "non",
        "yes",
        "no",
        "yep",
        "nope",
        "merci",
        "thanks",
        "thx",
        "cool",
        "lol",
        "mdr",
        "yo",
        "hi",
        "hello",
        "salut",
    }
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
2. If the brief needs facts (news, current events, country or company briefing, "what is going on"): call web_search first (prefer one query, at most 4), read the template_fields and fill the open template with one fill_document_slots call. Do not leave seed placeholder copy. Do not append after the footer. Do not write the memo only in chat.
3. If the user asks for a theme or template, call apply_documents_template, then fill every seed slot, then stop.
4. If the open document is still Untitled, call rename_document first, then write. If the user asks to rename the document, call rename_document. Do not only edit the HTML title.
5. If the brief is a heading-only change, use update_title. Other tiny copy edits use one apply_document_commands replace_text, then stop.
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
- Always end the turn with a short user-visible reply. Never finish with empty content.
- If the user is chatting about you, the product, or anything that is not creating or editing the document, call request_help immediately. Do not answer with silence.
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

    @classmethod
    def retains_active_turn(cls, text: str) -> bool:
        """Keep sticky handoff for doc edits; release meta chat to the supervisor."""
        raw = (text or "").strip()
        if not raw:
            return False
        lowered = raw.lower()
        if lowered in _RELEASE_STICKY_SHORT:
            return False
        if any(phrase in lowered for phrase in _HANDOFF_PHRASES):
            return True
        if any(marker in lowered for marker in _DOCUMENT_TURN_MARKERS):
            return True
        words = lowered.split()
        # Short follow-ups like "plus formel" stay with Documents.
        return bool(len(words) <= 6 and "?" not in raw)

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
            enable_default_tools=False,
        )
