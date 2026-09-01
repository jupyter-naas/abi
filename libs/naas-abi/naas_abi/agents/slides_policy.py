"""Slides chat policy: research first, then write; stronger model than mini.

Owned by SlidesAgent. AbiAgent plus an open-deck model override is fallback only.
Slides tools and Nexus chat share this module so a current-events brief cannot
skip web_search and dump template filler into deck.html.
"""

from __future__ import annotations

import re
from typing import Any

from naas_abi_core.services.agent.context import (
    slides_active_slug,
    slides_research_queries,
    slides_research_required,
)

# OpenRouter id. This environment's OPENAI_API_KEY is an OpenRouter key, so
# a native Anthropic / ChatGPT registry id (api.anthropic.com / api.openai.com)
# 401s. Route slides through OpenRouter instead.
DEFAULT_SLIDES_MODEL = "anthropic/claude-sonnet-5"

# Shared copy for SlidesAgent (primary) and AbiAgent (fallback if a deck is open).
SLIDES_GUIDELINES = """- You edit the open presentation HTML only (Coder workspace files via sidecar when available; Forgejo for version history). Preview is that HTML. PPTX is an export reconstructed from the live .slide DOM at 1280x720. Do not edit buildPptx, FOOTER_TXT, or other script strings.
- Never ask which deck, slug, file, or template when open-deck context is present. Omit slug on tool calls; tools default to the open deck.
- A new deck is already a seed. The user's first message is the brief for that open deck.html. Do not ask which file to edit. Default to 6-8 slides after research unless they specified length.
- Research loop (required, not optional) for news, current events, "what is going on", country or company briefings, or any factual deck:
  1. Call web_search first. Run 2 to 4 queries (latest developments, context, key actors, dates). Include the current year. Stop searching after 4 queries.
  2. Optionally one second-pass query to contradict or confirm named sources, still within the 4-query budget.
  3. Outline 6-8 sections against the open template.
  4. Then write or replace HTML in the open deck.html with real claims, dates, and named sources. Do not keep searching instead of writing.
- Do not write slides from training data alone when the brief is time-sensitive. Slides write tools will reject the edit until web_search has run.
- Do not leave template filler (Presentation Title, Agenda: Context / Approach / Plan, lorem). Keep the seed template CSS and structure (Minimal Light, Pitch Dark, or Executive). Replace section titles and body copy only. Do not invent a new design system.
- Cite sources in speaker-visible lines or footer/source lines if the template allows, without wrecking layout.
- Tiny copy edits (title typo, color tweak) may skip search. A first-message create/brief may not.
- Prefer replace_in_slides_deck for copy edits (matches plain text and HTML entities like &amp; so cover &lt;h1&gt; and body copy update in Preview and PPTX).
- For cover / title / slide 1 edits: call replace_in_slides_deck with section_index=0 and occurrence=0. Never use occurrence=1 for the title (that hits &lt;title&gt;/menubar before the cover &lt;h1&gt; Preview shows). Confirm cover_h1_updated is true in the tool result.
- Use list_slides_sections then read_slides_section for targeted inspection.
- Use write_slides_section to replace one &lt;section&gt; only. Keep .deck / .slide 1280x720, cover h1, and theme CSS variables.
- Avoid read_slides_deck with include_assets=true. Default reads redact embedded data-URLs on purpose.
- Avoid write_slides_deck unless creating or restructuring the whole presentation."""

SLIDES_AGENT_SYSTEM_PROMPT = f"""<role>
You are Slides, the office agent for Nexus Slides. You research, then write the open HTML deck. You are not Abi with a slides hat.
</role>

<objective>
Turn the user's brief into a researched HTML presentation in the open deck.html. HTML is the live source of truth. PPTX is export-from-DOM only.
</objective>

<context>
You will receive an open-deck block (slug, path, branch, today) when the user is in Slides. Edit that file. Do not invent a second deck. Do not dump or rewrite the full file for a small text change.
</context>

<tasks>
1. If the brief needs facts (news, current events, country or company briefing, "what is going on"): call web_search first (2 to 4 queries), then outline, then write.
2. If the brief is a tiny copy edit, inspect the open section and use replace_in_slides_deck.
3. After writes, report what changed in the open deck. Do not claim Preview updated unless the tool result confirms it.
</tasks>

<slides_guidelines>
{SLIDES_GUIDELINES}
</slides_guidelines>

<skill>
[SKILL]
</skill>

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

# Mini / free models skip tools and invent filler. Do not use them for slides
# creation even if the UI still has them selected from an earlier turn.
_WEAK_SLIDES_MODEL_IDS = frozenset(
    {
        "gpt-4.1-mini",
        "openai/gpt-4.1-mini",
        "gpt-5-mini",
        "openai/gpt-5-mini",
        "gpt-5-nano",
        "openai/gpt-5-nano",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
    }
)

_COPY_EDIT_RE = re.compile(
    r"\b("
    r"rename|retitle|fix typo|change the title|tweak|"
    r"make it (darker|lighter|dark|light)|"
    r"change (the )?(color|font|theme)"
    r")\b",
    re.IGNORECASE,
)
_RESEARCH_RE = re.compile(
    r"\b("
    r"what'?s going on|going on in|current events?|today|now|"
    r"news|latest|briefing|situation|update|developments?|"
    r"who is|what happened"
    r")\b",
    re.IGNORECASE,
)
_CREATE_RE = re.compile(
    r"\b("
    r"create|make|build|write|draft|generate|"
    r"presentation|deck|slides|brief"
    r")\b",
    re.IGNORECASE,
)

_UNRESEARCHED_WRITE_ERROR = (
    "Research required before editing this deck. Call web_search first with "
    "2 to 4 queries (latest developments, context, key actors, dates). "
    "Then retry this write."
)

MAX_SLIDES_SEARCHES = 4
_SEARCH_BUDGET_MESSAGE = (
    "Search budget reached (4 queries). Do not call web_search or web_fetch "
    "again. Outline 6-8 slides against the open template and write the open "
    "deck.html now with researched claims, dates, actors, and sources."
)


def is_weak_slides_model(model_id: str | None) -> bool:
    raw = (model_id or "").strip().lower()
    if not raw:
        return True
    if raw in _WEAK_SLIDES_MODEL_IDS:
        return True
    if raw.endswith(":free"):
        return True
    return raw.endswith("/gpt-4.1-mini")


def configured_slides_model() -> str:
    try:
        from naas_abi import ABIModule

        configured = getattr(
            ABIModule.get_instance().configuration,
            "abi_slides_agent_model",
            None,
        )
        if configured and str(configured).strip():
            return str(configured).strip()
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_SLIDES_MODEL


def resolve_slides_llm_model(
    incoming: str | None,
    slides_default: str | None = None,
) -> str:
    """Pick a reasoning model for slides. Ignore mini/free selections."""
    default = (slides_default or "").strip() or configured_slides_model()
    raw = (incoming or "").strip()
    if raw and not is_weak_slides_model(raw):
        return raw
    return default


def open_slides_slug(client_context: dict | None) -> str:
    if not isinstance(client_context, dict):
        return ""
    slides = client_context.get("slides")
    if not isinstance(slides, dict):
        return ""
    return str(slides.get("slug") or "").strip()


def is_slides_agent_ref(agent_ref: str | None) -> bool:
    """True when the in-process agent target is SlidesAgent (class, path, or name)."""
    raw = (agent_ref or "").strip().lower()
    if not raw:
        return False
    if "slidesagent" in raw:
        return True
    if raw == "slides" or raw.endswith("/slides"):
        return True
    return False


def apply_slides_model_override(
    incoming: str | None,
    client_context: dict | None,
    agent_ref: str | None = None,
) -> str | None:
    """Upgrade mini/free models for SlidesAgent, or for Abi when a deck is open."""
    if is_slides_agent_ref(agent_ref) or open_slides_slug(client_context):
        return resolve_slides_llm_model(incoming)
    return incoming


def slides_brief_requires_research(message: str, has_prior_assistant: bool) -> bool:
    """True when the model must call web_search before writing HTML."""
    text = (message or "").strip()
    if not text:
        return False
    copy_edit = bool(_COPY_EDIT_RE.search(text))
    researchy = bool(_RESEARCH_RE.search(text))
    createy = bool(_CREATE_RE.search(text))
    if copy_edit and not researchy and not createy:
        return False
    if not has_prior_assistant:
        return True
    # Follow-up "write the deck now" must not reset the research gate.
    return researchy


def bind_slides_research_policy(
    message: str,
    has_prior_assistant: bool,
    client_context: dict | None,
) -> bool:
    """Set request-scoped research gates. Returns whether search is required."""
    slug = open_slides_slug(client_context) or (slides_active_slug.get() or "").strip()
    if not slug:
        slides_research_required.set(False)
        return False
    slides_active_slug.set(slug)
    required = slides_brief_requires_research(message, has_prior_assistant)
    slides_research_required.set(required)
    if required:
        slides_research_queries.set([])
    return required


def note_slides_web_search(query: str) -> None:
    """Record that web_search ran this turn (unlocks slides writes)."""
    if not slides_research_required.get():
        return
    text = (query or "").strip()
    if not text:
        return
    bucket = slides_research_queries.get()
    if bucket is None:
        slides_research_queries.set([text])
        return
    bucket.append(text)


def reject_unresearched_slides_write() -> dict[str, Any] | None:
    """Block deck writes until web_search has run for a research brief."""
    if not slides_research_required.get():
        return None
    queries = slides_research_queries.get()
    if queries:
        return None
    return {"error": _UNRESEARCHED_WRITE_ERROR}


def slides_search_budget_remaining() -> int:
    queries = slides_research_queries.get() or []
    return max(0, MAX_SLIDES_SEARCHES - len(queries))


def attach_slides_research_note(tool: Any) -> Any:
    """Wrap a web_search tool so successful calls unlock slides writes."""
    original = getattr(tool, "func", None)
    if original is None:
        return tool

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if slides_research_required.get() and slides_search_budget_remaining() <= 0:
            return _SEARCH_BUDGET_MESSAGE
        query = kwargs.get("query")
        if query is None and args:
            query = args[0]
        if isinstance(query, str) and query.strip():
            note_slides_web_search(query)
        return original(*args, **kwargs)

    tool.func = wrapped
    return tool


def _openrouter_api_key(abi: Any) -> str | None:
    """Prefer the OpenRouter module key; this env often stores it as OPENAI_API_KEY."""
    import os

    for name, module in (getattr(getattr(abi, "engine", None), "modules", {}) or {}).items():
        if "openrouter" not in str(name).lower():
            continue
        key = getattr(getattr(module, "configuration", None), "openrouter_api_key", None)
        if key:
            return str(key)
    for env_name in ("OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        raw = (os.environ.get(env_name) or "").strip()
        if raw.startswith("sk-or-"):
            return raw
    routed = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    return routed or None


def openrouter_slides_model_id(model_id: str) -> str:
    """Map a slides model id onto an OpenRouter provider/model slug.

    Bare GPT ids stay ``openai/...``. Bare Claude / Sonnet / Opus / Haiku ids
    become ``anthropic/...``. Never rewrite ``claude-sonnet-5`` to
    ``openai/claude-sonnet-5``.
    """
    raw = (model_id or "").strip()
    if not raw:
        return DEFAULT_SLIDES_MODEL
    if "/" in raw:
        return raw
    hay = raw.lower()
    if hay.startswith(("claude", "anthropic")) or any(
        token in hay for token in ("sonnet", "opus", "haiku")
    ):
        return f"anthropic/{raw}"
    return f"openai/{raw}"


def slides_reasoning_extra_body(model_id: str) -> dict[str, Any] | None:
    """OpenRouter unified ``reasoning.effort`` for GPT-5 and Claude Sonnet 5.

    Both families accept this payload on OpenRouter. Skip it for unknown ids
    so we do not send an invalid body.
    """
    hay = (model_id or "").lower()
    if not any(token in hay for token in ("gpt-5", "o3", "o4", "sonnet", "opus", "gemini")):
        return None
    return {"reasoning": {"effort": "high"}}


def load_slides_chat_model(model_id: str | None = None) -> Any:
    """Build the slides chat model via OpenRouter, not api.openai.com."""
    from langchain_openai import ChatOpenAI
    from naas_abi import ABIModule
    from naas_abi_core.models.Model import ChatModel
    from pydantic import SecretStr

    resolved = resolve_slides_llm_model(model_id)
    or_id = openrouter_slides_model_id(resolved)
    abi = ABIModule.get_instance()
    api_key = _openrouter_api_key(abi)
    if not api_key:
        return abi.engine.services.model_registry.get_chat_model(
            resolved,
            provider=abi.configuration.abi_agent_provider,
        )
    extra = slides_reasoning_extra_body(or_id)
    chat = ChatModel(
        model_id=or_id,
        provider="openrouter",
        model=ChatOpenAI(
            model=or_id,
            api_key=SecretStr(str(api_key)),
            base_url="https://openrouter.ai/api/v1",
            timeout=180,
            **({"extra_body": extra} if extra else {}),
        ),
    )
    return bind_slides_reasoning(chat, or_id)


def bind_slides_reasoning(chat_model: Any, model_id: str) -> Any:
    """Turn on high reasoning effort without replacing the LangChain chat class.

    ``model.bind(...)`` returns a RunnableBinding, which Agent rejects. Set the
    attribute on the live ChatOpenAI (or equivalent) instead.
    """
    if not (slides_active_slug.get() or "").strip():
        return chat_model
    hay = (model_id or "").lower()
    if not any(token in hay for token in ("gpt-5", "o3", "o4", "sonnet", "opus", "gemini")):
        return chat_model
    lc = getattr(chat_model, "model", chat_model)
    if not hasattr(lc, "reasoning_effort"):
        return chat_model
    try:
        lc.reasoning_effort = "high"
    except Exception:  # noqa: BLE001
        return chat_model
    return chat_model
