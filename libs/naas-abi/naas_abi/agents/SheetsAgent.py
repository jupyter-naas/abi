from pathlib import Path

from langchain_core.embeddings import Embeddings
from naas_abi.agents.sheets import (
    bind_sheets_reasoning,
    configured_sheets_model,
    load_sheets_chat_model,
    resolve_sheets_llm_model,
    sheets_research_tools,
)
from naas_abi_core.services.agent.context import SHEETS_RECURSION_LIMIT
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


SHEETS_SKILL = (Path(__file__).parent / "sheets/skills/nexus-sheets/SKILL.md").read_text(encoding="utf-8")


SHEETS_GUIDELINES = """- When the user asks for a spreadsheet or workbook and none is open, call create_sheets_project first with a short title from their brief (and template_id when known), then edit via write_sheets_workbook only as needed.
- Never call create_sheets_project when a workbook is already open; edit it instead.
- Finance intents must seed the matching template, not a blank toy grid:
  - P&L / income statement / monthly P&L → template_id monthly-pnl-v1
  - Budget vs actuals / variance → template_id budget-vs-actuals-v1
  - Cash runway / burn / cash rollforward → template_id cash-runway-v1
  - Otherwise blank grid-light-v1
- After a finance seed loads, edit Assumptions inputs and labels. Keep every total, margin, variance, and check cell as a formula. Never paste a computed total over a formula. Never replace the workbook with a 4-row sample grid.
- The source of truth is the JSON block inside workbook.html (application/vnd.nexus.sheet+json). Use read_sheets_workbook before large edits and write_sheets_workbook to persist tabs/rows.
- Use evaluate_sheets_formulas after formula edits (read-only check; it does not bake values). Checks / Tie-out Status must be OK.
- Use import_dataset_to_sheet to pull live rows from a Nexus dataset (namespace/name) into a tab.
- For time-sensitive numeric briefs, call web_search first (2–4 queries), then write from sources.
- Omit slug on tool calls when open-workbook context is present.
- Do not dump full workbook HTML in chat; report slug, tab names, and row counts."""


SHEETS_OUTPUT_QUALITY = """Workbook quality (audit-workpaper bar):
- Formulas over literals: totals, subtotals, margins, variance %, rollforwards, and check diffs must be ``=`` formulas that reference cells. Do not hardcode a result you calculated in your head.
- Assumptions / Drivers on their own tab. Calculations reference those cells (including cross-sheet refs like Assumptions!C2 or 'P&L'!B4). No magic numbers inside formulas.
- Multiple tabs when the brief is financial: Assumptions, the statement or schedule, and a Checks (or Tie-out) tab with OK/BREAK formulas (IF + ABS on diffs).
- Label units in headers (e.g. EUR '000). Periods are real months. Inputs live on Assumptions; formula cells stay formulas.
- Supported formula surface: arithmetic, A1 refs, cross-sheet refs, SUM, IF, ABS, ROUND. Prefer SUM(range) for totals.
- After edits, call evaluate_sheets_formulas and fix any BREAK / #ERR before claiming the workbook is done.
- XLSX export preserves formula strings; do not ask the user to treat export as values-only."""


_HANDOFF_PHRASES = (
    "create a spreadsheet",
    "create a workbook",
    "make sheets",
    "build sheets",
    "write a workbook",
    "fais des sheets",
    "crée une spreadsheet",
    "prépare un tableur",
    "prepare un tableur",
    "monte un tableur",
)


class SheetsAgent(IntentAgent):
    """Office agent for Nexus Sheets.

    Research 2 to 4 web_search queries, then write the open workbook.html.
    The JSON grid block in workbook.html is the live source; XLSX is export-only.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi SheetsAgent
    """

    name: str = "Sheets"
    description: str = (
        "Office agent for Nexus Sheets. Creates and edits HTML workbooks with a "
        "JSON grid model, evaluates formulas, and imports dataset rows."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = SHEETS_RECURSION_LIMIT
    system_prompt: str = f"""<role>
You are Sheets, the office agent for Nexus Sheets. You research, then write the HTML workbook. You are not Abi with a sheets hat.
</role>

<objective>
Turn the user's brief into a researched, formula-correct spreadsheet in workbook.html. The JSON grid model is the live source of truth. XLSX export is derived from that model and must keep formulas.
</objective>

<context>
You will receive an open-workbook block (slug, path, branch, today) when the user is in Sheets. Edit that file. Do not invent a second workbook. Do not dump or rewrite the full file for a small text change. From the main chat, with no workbook open, create the workbook first (correct finance template when applicable), then edit Assumptions / formulas.
Your step budget is finite ({SHEETS_RECURSION_LIMIT} graph steps). Plan, then write. Do not spend the budget listing and reading the whole workbook.
</context>

<tasks>
1. If no workbook is open and the user asked for a workbook, spreadsheet, or sheets, call create_sheets_project first (with the matching finance template_id when the brief is P&L, budget vs actuals, or runway), then research if needed, then customize.
2. If the brief needs facts (news, current events, country or company briefing, "what is going on"): call web_search first (2 to 4 queries), then read_sheets_workbook once, then write with formulas.
3. After adding or changing ``=`` formulas, call evaluate_sheets_formulas and fix BREAKs. For live data, use import_dataset_to_sheet.
4. After writes, report what changed in the open workbook (tabs, key formulas, check status). Do not claim Preview updated unless the tool result confirms it. Do not re-read the workbook to check.
</tasks>

<sheets_guidelines>
{SHEETS_GUIDELINES}
</sheets_guidelines>

<sheets_output_quality>
{SHEETS_OUTPUT_QUALITY}
</sheets_output_quality>

<spreadsheet_skill>
{SHEETS_SKILL}
</spreadsheet_skill>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Keep a clear, concise, professional tone.
- Format replies as clean Markdown.
- Include relevant tool output when it matters (template_id, check Status, write errors, search budget).
</operating_guidelines>

<constraints>
- Preserve the language of the user's message.
- Never invent sources, dates, or that you edited a file without a tool result.
- Never use em dashes or en dashes in cell copy. Use commas, colons, or hyphens.
- Do not keep searching instead of writing.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "Monthly P&L",
            "value": (
                "Build a monthly P&L in EUR thousands with Assumptions, "
                "statement, and Checks that all read OK."
            ),
            "description": "Seed monthly-pnl-v1, then tune inputs",
        },
        {
            "label": "Budget vs actuals",
            "value": "Create a budget vs actuals workbook with variance % and tie-out checks.",
            "description": "Seed budget-vs-actuals-v1",
        },
        {
            "label": "Cash runway",
            "value": "Build a 12-month cash runway rollforward with hiring costs and Checks OK.",
            "description": "Seed cash-runway-v1",
        },
        {
            "label": "What can you do?",
            "value": "What can you do with this open workbook?",
            "description": "Tools and the research-then-write loop",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        """Phrases Abi copies so a workbook brief transfers here instead of writing itself."""
        return [
            Intent(
                intent_value=phrase,
                intent_type=IntentType.RAW,
                intent_target="Sheets",
                intent_scope=IntentScope.ALL,
            )
            for phrase in _HANDOFF_PHRASES
        ]

    @staticmethod
    def get_tools() -> list:
        """Workbook writes plus the search stack the research gate depends on."""
        tools: list = []
        try:
            from naas_abi.tools.sheets_tools import sheets_tools

            tools += sheets_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("sheets tools unavailable: %s", exc)

        try:
            tools += sheets_research_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("sheets research tools unavailable: %s", exc)

        return tools

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_sheets_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_sheets_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "SheetsAgent":
        resolved = resolve_sheets_llm_model(model_id)
        chat_model = bind_sheets_reasoning(
            load_sheets_chat_model(resolved),
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
