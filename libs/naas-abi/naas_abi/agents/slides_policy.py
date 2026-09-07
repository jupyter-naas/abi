"""Slides chat policy: research first, then write, on the configured model.

Used by AbiAgent, slides tools, and Nexus chat so a current-events brief cannot
skip web_search and dump template filler into deck.html.

The server owns the model for a slides turn. Whatever the composer had
selected, slides run on ``abi_slides_agent_model``, the id is checked at boot,
and a turn that overrides a selection says so at warning level.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from naas_abi_core.services.agent.context import (
    slides_active_slug,
    slides_brief,
    slides_creation_intent,
    slides_research_queries,
    slides_research_required,
)

# OpenRouter id. This environment's OPENAI_API_KEY is an OpenRouter key, so
# a native Anthropic / ChatGPT registry id (api.anthropic.com / api.openai.com)
# 401s. Route slides through OpenRouter instead.
DEFAULT_SLIDES_MODEL = "anthropic/claude-sonnet-5"

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
    """Return the configured slides model. The client's selection never wins.

    This used to hand back ``incoming`` unless it matched a list of weak model
    ids. That list was an allowlist of one written inside out: every model
    released after it was written counted as good enough for a deck until
    someone shipped a deck on it and added it, and it had already grown two
    Gemma spellings and three GPT variants that way.

    Overriding a user's choice is only acceptable because it is announced.
    Nothing on this path logged anything, which is how a mini model writing
    template filler survived long enough to cost a session of debugging.
    """
    effective = (slides_default or "").strip() or configured_slides_model()
    raw = (incoming or "").strip()
    if raw and raw != effective:
        import logging

        logging.getLogger(__name__).warning(
            "slides turn overriding the selected model %r with the configured "
            "slides model %r (abi_slides_agent_model). Slides always run on the "
            "configured model.",
            raw,
            effective,
        )
    return effective


def open_slides_slug(client_context: dict | None) -> str:
    if not isinstance(client_context, dict):
        return ""
    slides = client_context.get("slides")
    if not isinstance(slides, dict):
        return ""
    return str(slides.get("slug") or "").strip()


def apply_slides_model_override(
    incoming: str | None,
    client_context: dict | None,
    message: str | None,
) -> str | None:
    """Route slides work onto the configured slides model.

    Covers both an open deck and a deck asked for from the main chat, where a
    model that skips tools writes template filler into the whole deck.

    ``message`` is required rather than defaulting to ``None``. A default let a
    caller drop the user brief and silently keep the composer's model on the
    create-from-main-chat turn, which is the turn that writes the whole deck.
    Callers with genuinely no message must pass ``None`` on purpose.
    """
    if open_slides_slug(client_context):
        return resolve_slides_llm_model(incoming)
    if message is not None and slides_creation_requested(message):
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


_DECK_NOUN_RE = re.compile(
    r"\b(deck|presentation|présentation|slides|slide deck|slideshow|pitch"
    r"|diaporama|exposé)\b",
    re.IGNORECASE,
)
# French verbs matter: a brief written in French must arm the slides path too,
# otherwise it runs as an ordinary chat turn on whatever model was selected.
_MAKE_VERB_RE = re.compile(
    r"\b(create|make|build|draft|generate|prepare|put together|write|need|want"
    r"|fais|fait|faire|crée|cree|créer|creer|génère|genere|générer|generer"
    r"|prépare|prepare|préparer|rédige|redige|rédiger|construis|monte"
    r"|veux|voudrais|souhaite|besoin)\b",
    re.IGNORECASE,
)


def slides_creation_requested(message: str) -> bool:
    """True when the user is asking for a new deck on a surface with none open.

    Requires both a making verb and a deck noun so "summarise this document"
    or a passing mention of a slide does not hijack an ordinary chat turn.
    """
    text = (message or "").strip()
    if not text:
        return False
    return bool(_MAKE_VERB_RE.search(text) and _DECK_NOUN_RE.search(text))


def bind_slides_research_policy(
    message: str,
    has_prior_assistant: bool,
    client_context: dict | None,
) -> bool:
    """Set request-scoped research gates. Returns whether search is required."""
    # Slides tools name a new (or still untitled) deck after this brief.
    slides_brief.set((message or "").strip())
    slug = open_slides_slug(client_context) or (slides_active_slug.get() or "").strip()
    if not slug:
        # Main chat: no deck open yet. A deck request still has to research
        # before writing, and the agent needs a slides-sized step budget.
        creating = slides_creation_requested(message)
        slides_creation_intent.set(creating)
        if not creating:
            slides_research_required.set(False)
            return False
        required = slides_brief_requires_research(message, has_prior_assistant)
        slides_research_required.set(required)
        if required:
            slides_research_queries.set([])
        return required
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
    if not slides_search_tool_bound():
        # web_search is the only thing that can fill slides_research_queries,
        # so with no search tool bound this gate can never be satisfied. Held
        # shut, it fails every deck write on a factual brief forever while
        # telling the model to retry after a search it cannot run.
        import logging

        logging.getLogger(__name__).warning(
            "slides research gate opened: no web_search tool is bound, so the "
            "deck will be written without research"
        )
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


_SEARCH_STACK = "naas_abi.agents.tools.web_tools"


def slides_search_tool_bound() -> bool:
    """True when a web_search tool can be bound for this process.

    A probe rather than a flag written by the registration. The agent is built
    per request and the policy is armed per request, so a flag would have to be
    set before it is read, and the gate would take the wrong branch, silently,
    on any turn where that order slipped.
    """
    import importlib

    try:
        importlib.import_module(_SEARCH_STACK)
    except ImportError:
        return False
    return True


def slides_research_tools() -> list[Any]:
    """Bind the web tools the research gate depends on, or nothing.

    Extracted from AbiAgent so the gate and the registration agree on one
    source of search, instead of the gate assuming a tool the registration
    never managed to bind.
    """
    import importlib
    import logging

    try:
        stack = importlib.import_module(_SEARCH_STACK)
    except ImportError as exc:
        logging.getLogger(__name__).warning(
            "slides web search unavailable, the research gate will not be armed: %s",
            exc,
        )
        return []
    return [
        attach_slides_research_note(stack.make_web_search_tool()),
        stack.make_web_fetch_tool(),
    ]


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


def load_slides_chat_model(model_id: str) -> Any:
    """Build the slides chat model via OpenRouter, not api.openai.com.

    Raises ``ValueError`` on an empty ``model_id``. ``resolve_slides_llm_model``
    reads an empty value as "use the configured slides default", so a caller
    that dropped the model the turn was routed to built a model for a different
    model with no error and no log line. There is no safe default at this
    boundary: a caller holding no model id has lost information, and the loss
    has to be visible where it happens.
    """
    if not (model_id or "").strip():
        raise ValueError(
            "load_slides_chat_model requires the model id the turn was routed "
            "to. Resolve it with resolve_slides_llm_model first."
        )

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
    """Return a copy with high reasoning effort, leaving the caller's model alone.

    ``model.bind(...)`` returns a RunnableBinding, and Agent asserts
    ``isinstance(chat_model, BaseChatModel | ChatModel)``, so a bound model is
    rejected at construction. Writing the attribute instead is worse:
    ``AbiAgent.New`` calls this on the ChatModel the ModelRegistry handed it,
    and the registry hands back the registered entry itself, so the write
    outlives the request and every later caller of that canonical id inherits
    it.

    ``model_copy`` keeps the concrete chat class and shares the underlying
    OpenAI client, so the copy costs no connection setup.
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
        reasoning = lc.model_copy(update={"reasoning_effort": "high"})
    except Exception:  # noqa: BLE001
        return chat_model
    if lc is chat_model:
        return reasoning
    # The wrapper is shared too, so hand back a copy of it rather than
    # repointing the registry entry's model at the copy.
    wrapper = copy.copy(chat_model)
    wrapper.model = reasoning
    return wrapper
