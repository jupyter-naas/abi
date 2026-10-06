"""Sheets chat policy: research first, then write, on the configured model.

Used by SheetsAgent, sheets tools, and Nexus chat so a current-events brief cannot
skip web_search and dump template filler into workbook.html.

The server owns the model for a sheets turn. Whatever the composer had
selected, sheets run on ``abi_sheets_agent_model`` when it is set and on
``abi_agent_model`` when it is not, and either way a turn that overrides a
selection says so at warning level.

``abi_sheets_agent_model`` is optional because ABI has no reasoning-capable id
it can ship: every one of them is registered by a marketplace or downstream
module that a given install may not enable. Set, it is checked against the
registry at boot, since it is then the only model any sheets turn can run on
and a typo in it breaks every workbook rather than one. Unset, there is nothing to
check that the engine does not already check for ``abi_agent_model``.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from naas_abi_core.services.agent.context import (
    sheets_active_slug,
    sheets_brief,
    sheets_creation_intent,
    sheets_list_calls,
    sheets_research_queries,
    sheets_research_required,
    sheets_section_read_indexes,
    sheets_writes_completed,
)

# Last resort for callers that reach these helpers with no ABIModule
# registered, which in practice means no engine and no registry either. It is
# not a shipped default: ``abi_sheets_agent_model`` is empty and sheets follow
# ``abi_agent_model``.
#
# The comment that stood here said this id existed because a native Anthropic
# or ChatGPT registry id 401s against an OpenRouter key. That was the wrong
# diagnosis. OPENAI_BASE_URL was set and every OpenAI client in the process
# inherited it, so the requests were reaching the wrong endpoint.
DEFAULT_SHEETS_MODEL = "anthropic/claude-sonnet-5"

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
    r"workbook|workbook|sheets|brief"
    r")\b",
    re.IGNORECASE,
)

_UNRESEARCHED_WRITE_ERROR = (
    "Research required before editing this workbook. Call web_search first with "
    "2 to 4 queries (latest developments, context, key actors, dates). "
    "Then retry this write."
)

MAX_SHEETS_SEARCHES = 4
MAX_SHEETS_SECTION_READS = 3
_SEARCH_BUDGET_MESSAGE = (
    "Search budget reached (4 queries). Do not call web_search or web_fetch "
    "again. Call list_sheets_sections once, then write the open workbook.html in "
    "one write_sheets_sections or write_sheets_workbook. Do not read every section."
)
_LIST_ONCE_MESSAGE = (
    "list_sheets_sections already ran this turn. Use that outline. "
    "Do not list again. Write with write_sheets_sections or write_sheets_workbook."
)
_SECTION_READ_BUDGET_MESSAGE = (
    f"read_sheets_section budget reached ({MAX_SHEETS_SECTION_READS} sheets "
    "this turn). Do not read every section. Write the workbook with "
    "write_sheets_sections or write_sheets_workbook, or replace_in_sheets_workbook "
    "for one copy edit."
)
_SECTION_REREAD_MESSAGE = (
    "You already read this section this turn. Do not re-read it. "
    "Write or replace instead."
)
_SECTION_READ_AFTER_WRITE_MESSAGE = (
    "You already wrote this section this turn. Do not re-read it. "
    "Report what changed, or write a different slide."
)


def configured_sheets_model() -> str:
    """The model a sheets turn runs on: the sheets model, else the agent model.

    ``abi_sheets_agent_model`` is optional. Unset it does not mean "no sheets
    model", it means "no sheets-specific model", and the general agent model
    is the honest answer to that: it is the model the operator's chat already
    runs on and it is registered, because the engine resolves it in
    ``validate_defaults``. A sheets brief would rather have a reasoning-capable
    model and the general default may not be one, which is why the setting
    exists, but a weaker registered model beats an id nothing registered.
    """
    try:
        from naas_abi import ABIModule

        configuration = ABIModule.get_instance().configuration
    except Exception:  # noqa: BLE001
        return DEFAULT_SHEETS_MODEL
    for setting in ("abi_sheets_agent_model", "abi_agent_model"):
        configured = getattr(configuration, setting, None)
        if configured and str(configured).strip():
            return str(configured).strip()
    return DEFAULT_SHEETS_MODEL


def validate_configured_sheets_model(
    registry: Any,
    configured: str | None = None,
) -> None:
    """Resolve the configured sheets model, or refuse to start.

    Called at boot. Sheets ignore the model the client selected, so this one id
    is the only model any sheets turn can run on, and an id that does not
    resolve is not a degraded workbook but every workbook broken. Left unchecked it
    surfaces on whichever workbook someone opens next, which is exactly the shape
    of failure this whole change exists to remove.

    An empty ``configured`` is not checked. Nothing is being asserted about:
    no sheets model was named, so sheets follow the general agent model, and
    that id is already covered by ``ModelRegistryService.validate_defaults``.
    Checking it anyway is what made ABI fail its own boot, because the only id
    worth shipping as a sheets default is registered by a downstream module and
    by nothing in ABI. This is deliberately not "fall back to
    ``configured_sheets_model()``": that would resolve the general agent model
    under the sheets key and report a mismatch against a setting the operator
    never edited.

    ``registry.get_chat_model`` is called without a provider deliberately. With
    one it falls back to constructing an off-catalog model through that
    provider's chat factory, and a factory builds whatever id it is handed, so
    every typo would resolve and this would assert nothing. Registered-only is
    also what ``ModelRegistryService.validate_defaults`` requires of the engine
    defaults, so an operator sees one rule rather than two.
    """
    model_id = (configured or "").strip()
    if not model_id:
        return

    from naas_abi_core.services.model_registry.ModelRegistryPort import (
        DefaultModelNotResolvedError,
        ModelNotFoundError,
        ProviderNotConfiguredError,
    )

    try:
        registry.get_chat_model(model_id)
    except (ModelNotFoundError, ProviderNotConfiguredError) as exc:
        registered = sorted(registry.list_canonical_ids())
        listing = ", ".join(repr(i) for i in registered) if registered else "(none)"
        raise DefaultModelNotResolvedError(
            f"abi_sheets_agent_model={model_id!r} is not registered as a chat model.\n"
            f"  -> set it under modules.naas_abi.config.abi_sheets_agent_model, but no "
            f"loaded module registered a chat model with this id.\n"
            f"  -> likely cause: the module shipping that ModelDefinition is not enabled, "
            f"or the id is spelled differently there (the prefixed and bare forms are "
            f"two different canonical ids).\n"
            f"  -> currently registered model ids: {listing}"
        ) from exc


def resolve_sheets_llm_model(
    incoming: str | None,
    sheets_default: str | None = None,
) -> str:
    """Return the configured sheets model. The client's selection never wins.

    This used to hand back ``incoming`` unless it matched a list of weak model
    ids. That list was an allowlist of one written inside out: every model
    released after it was written counted as good enough for a workbook until
    someone shipped a workbook on it and added it, and it had already grown two
    Gemma spellings and three GPT variants that way.

    Overriding a user's choice is only acceptable because it is announced.
    Nothing on this path logged anything, which is how a mini model writing
    template filler survived long enough to cost a session of debugging.
    """
    effective = (sheets_default or "").strip() or configured_sheets_model()
    raw = (incoming or "").strip()
    if raw and raw != effective:
        import logging

        logging.getLogger(__name__).warning(
            "sheets turn overriding the selected model %r with the server's "
            "sheets model %r (abi_sheets_agent_model, or abi_agent_model when "
            "that is unset). Sheets always run on the server's model.",
            raw,
            effective,
        )
    return effective


def open_sheets_slug(client_context: dict | None) -> str:
    if not isinstance(client_context, dict):
        return ""
    sheets = client_context.get("sheets")
    if not isinstance(sheets, dict):
        return ""
    return str(sheets.get("slug") or "").strip()


def apply_sheets_model_override(
    incoming: str | None,
    client_context: dict | None,
    message: str | None,
) -> str | None:
    """Route sheets work onto the configured sheets model.

    Covers both an open workbook and a workbook asked for from the main chat, where a
    model that skips tools writes template filler into the whole workbook.

    ``message`` is required rather than defaulting to ``None``. A default let a
    caller drop the user brief and silently keep the composer's model on the
    create-from-main-chat turn, which is the turn that writes the whole workbook.
    Callers with genuinely no message must pass ``None`` on purpose.
    """
    if open_sheets_slug(client_context):
        return resolve_sheets_llm_model(incoming)
    if message is not None and sheets_creation_requested(message):
        return resolve_sheets_llm_model(incoming)
    return incoming


def sheets_brief_requires_research(message: str, has_prior_assistant: bool) -> bool:
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
    # Follow-up "write the workbook now" must not reset the research gate.
    return researchy


_DECK_NOUN_RE = re.compile(
    r"\b(workbook|workbook|présentation|sheets|slide workbook|sheetshow|pitch"
    r"|diaporama|exposé)\b",
    re.IGNORECASE,
)
# French verbs matter: a brief written in French must arm the sheets path too,
# otherwise it runs as an ordinary chat turn on whatever model was selected.
_MAKE_VERB_RE = re.compile(
    r"\b(create|make|build|draft|generate|prepare|put together|write|need|want"
    r"|fais|fait|faire|crée|cree|créer|creer|génère|genere|générer|generer"
    r"|prépare|prepare|préparer|rédige|redige|rédiger|construis|monte"
    r"|veux|voudrais|souhaite|besoin)\b",
    re.IGNORECASE,
)


def sheets_creation_requested(message: str) -> bool:
    """True when the user is asking for a new workbook on a surface with none open.

    Requires both a making verb and a workbook noun so "summarise this document"
    or a passing mention of a slide does not hijack an ordinary chat turn.
    """
    text = (message or "").strip()
    if not text:
        return False
    return bool(_MAKE_VERB_RE.search(text) and _DECK_NOUN_RE.search(text))


def bind_sheets_research_policy(
    message: str,
    has_prior_assistant: bool,
    client_context: dict | None,
) -> bool:
    """Set request-scoped research gates. Returns whether search is required."""
    # Sheets tools name a new (or still untitled) workbook after this brief.
    sheets_brief.set((message or "").strip())
    slug = open_sheets_slug(client_context) or (sheets_active_slug.get() or "").strip()
    if not slug:
        # Main chat: no workbook open yet. A workbook request still has to research
        # before writing, and the agent needs a sheets-sized step budget.
        creating = sheets_creation_requested(message)
        sheets_creation_intent.set(creating)
        if not creating:
            sheets_research_required.set(False)
            return False
        sheets_writes_completed.set([])
        _reset_sheets_read_budget()
        required = sheets_brief_requires_research(message, has_prior_assistant)
        sheets_research_required.set(required)
        if required:
            sheets_research_queries.set([])
        return required
    sheets_active_slug.set(slug)
    sheets_writes_completed.set([])
    _reset_sheets_read_budget()
    required = sheets_brief_requires_research(message, has_prior_assistant)
    sheets_research_required.set(required)
    if required:
        sheets_research_queries.set([])
    return required


def _reset_sheets_read_budget() -> None:
    sheets_list_calls.set(0)
    sheets_section_read_indexes.set([])


def reject_repeat_list_sheets_sections() -> dict[str, Any] | None:
    """Refuse a second list_sheets_sections on this turn."""
    if sheets_list_calls.get() >= 1:
        return {"error": _LIST_ONCE_MESSAGE}
    return None


def note_sheets_list() -> None:
    sheets_list_calls.set(sheets_list_calls.get() + 1)


def reject_sheets_section_read(index: int) -> dict[str, Any] | None:
    """Refuse a re-read, a read after write, or a fourth unique section read."""
    written = sheets_writes_completed.get() or []
    slide_label = f"slide {index + 1}"
    if slide_label in written or "full workbook" in written:
        return {"error": _SECTION_READ_AFTER_WRITE_MESSAGE}
    seen = sheets_section_read_indexes.get() or []
    if index in seen:
        return {"error": _SECTION_REREAD_MESSAGE}
    if len(seen) >= MAX_SHEETS_SECTION_READS:
        return {"error": _SECTION_READ_BUDGET_MESSAGE}
    return None


def note_sheets_section_read(index: int) -> None:
    bucket = sheets_section_read_indexes.get()
    if bucket is None:
        sheets_section_read_indexes.set([index])
        return
    if index not in bucket:
        bucket.append(index)


def note_sheets_web_search(query: str) -> None:
    """Record that web_search ran this turn (unlocks sheets writes)."""
    if not sheets_research_required.get():
        return
    text = (query or "").strip()
    if not text:
        return
    bucket = sheets_research_queries.get()
    if bucket is None:
        sheets_research_queries.set([text])
        return
    bucket.append(text)


def reject_unresearched_sheets_write() -> dict[str, Any] | None:
    """Block workbook writes until web_search has run for a research brief."""
    if not sheets_research_required.get():
        return None
    queries = sheets_research_queries.get()
    if queries:
        return None
    if not sheets_search_tool_bound():
        # web_search is the only thing that can fill sheets_research_queries,
        # so with no search tool bound this gate can never be satisfied. Held
        # shut, it fails every workbook write on a factual brief forever while
        # telling the model to retry after a search it cannot run.
        import logging

        logging.getLogger(__name__).warning(
            "sheets research gate opened: no web_search tool is bound, so the "
            "workbook will be written without research"
        )
        return None
    return {"error": _UNRESEARCHED_WRITE_ERROR}


def sheets_search_budget_remaining() -> int:
    queries = sheets_research_queries.get() or []
    return max(0, MAX_SHEETS_SEARCHES - len(queries))


def attach_sheets_research_note(tool: Any) -> Any:
    """Wrap a web_search tool so successful calls unlock sheets writes."""
    original = getattr(tool, "func", None)
    if original is None:
        return tool

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if sheets_research_required.get() and sheets_search_budget_remaining() <= 0:
            return _SEARCH_BUDGET_MESSAGE
        query = kwargs.get("query")
        if query is None and args:
            query = args[0]
        if isinstance(query, str) and query.strip():
            note_sheets_web_search(query)
        return original(*args, **kwargs)

    tool.func = wrapped
    return tool


_SEARCH_STACK = "naas_abi.tools.web_tools"


def sheets_search_tool_bound() -> bool:
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


def sheets_research_tools() -> list[Any]:
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
            "sheets web search unavailable, the research gate will not be armed: %s",
            exc,
        )
        return []
    return [
        attach_sheets_research_note(stack.make_web_search_tool()),
        stack.make_web_fetch_tool(),
    ]


def load_sheets_chat_model(model_id: str) -> Any:
    """Return the registered chat model for the model this turn was routed to.

    The same lookup ``SheetsAgent.New`` does, because it is the same question. The
    registration owns the endpoint, the key, the timeout and whatever else the
    model needs; this function's job is to name the model, not to know how to
    reach it.

    It used to build its own ``ChatOpenAI``: sniff the environment for an
    ``sk-or-`` key, guess a vendor prefix from the model family, and hardcode
    the OpenRouter base_url. That was a workaround for a 401, and the 401 was
    not a key problem. ``OPENAI_BASE_URL`` was set, every OpenAI client in the
    process inherited it, and requests meant for one endpoint went to another.
    Building a second client here fixed the symptom for one call site while
    leaving the cause, and cost the registration's ``extra_body``, retries and
    context window on every sheets turn.

    Raises ``ValueError`` on an empty ``model_id``. ``resolve_sheets_llm_model``
    reads an empty value as "use the configured sheets default", so a caller
    that dropped the model the turn was routed to built a model for a different
    model with no error and no log line. There is no safe default at this
    boundary: a caller holding no model id has lost information, and the loss
    has to be visible where it happens.
    """
    if not (model_id or "").strip():
        raise ValueError(
            "load_sheets_chat_model requires the model id the turn was routed "
            "to. Resolve it with resolve_sheets_llm_model first."
        )

    from naas_abi import ABIModule

    abi = ABIModule.get_instance()
    resolved = resolve_sheets_llm_model(model_id)
    chat = abi.engine.services.model_registry.get_chat_model(
        resolved,
        provider=abi.configuration.abi_agent_provider,
    )
    return bind_sheets_reasoning(chat, resolved)


def declares_reasoning(langchain_model: Any) -> bool:
    """True when the registration already asked for reasoning itself.

    Reasoning reaches a provider by three routes and a registration may use any
    of them: ``reasoning_effort`` for the OpenAI-native field, ``reasoning``
    for the object form, and a ``reasoning`` key inside ``extra_body`` or
    ``model_kwargs`` for anything passed through to an OpenAI-compatible
    gateway. Checking only the first would read a registration that declared
    reasoning through OpenRouter's ``extra_body`` as having declared nothing.
    """
    if getattr(langchain_model, "reasoning_effort", None):
        return True
    if getattr(langchain_model, "reasoning", None):
        return True
    for attribute in ("extra_body", "model_kwargs"):
        payload = getattr(langchain_model, attribute, None)
        if isinstance(payload, dict) and payload.get("reasoning"):
            return True
    return False


def bind_sheets_reasoning(
    chat_model: Any,
    model_id: str,
    *,
    force: bool = False,
) -> Any:
    """Return a copy with high reasoning effort, leaving the caller's model alone.

    ``force=True`` is for SheetsAgent.New: that agent only does sheets work, so
    it must carry reasoning even when no workbook is open yet (main-chat create).
    Callers that still share a catalog model (the in-process retarget path)
    keep the default: bind only when a sheets turn is already in progress.

    A fallback, not the design. The right home for reasoning config is the
    ``ModelDefinition`` that describes the model, next to its context window
    and its endpoint, where it is visible in the catalog and applies to every
    caller rather than to sheets only. This exists because roughly thirty
    reasoning-capable models are registered upstream with no reasoning config
    at all, so on an install with ``abi_sheets_agent_model`` unset it is the
    only thing supplying effort to them.

    Both gates are load-bearing and neither is sufficient. ``reasoning_effort``
    on the class answers "can this client carry the field": ChatAnthropic and
    ChatGoogleGenerativeAI have no such field, so they fall out here. The id
    tokens answer "does this model understand it": ChatOpenAI carries the field
    for everything it wraps, including models that would reject it or bill for
    it and ignore it, so guarding on the class alone would send high effort to
    every OpenAI-compatible registration in the install. That is also why the
    sonnet, opus and gemini tokens stay. They look dead against a native client
    and are not: an Anthropic or Gemini model reached through OpenRouter is a
    ChatOpenAI, which is exactly the registration shape this fires on.

    ``model.bind(...)`` returns a RunnableBinding, and Agent asserts
    ``isinstance(chat_model, BaseChatModel | ChatModel)``, so a bound model is
    rejected at construction. Writing the attribute instead is worse:
    writing the attribute on the ChatModel the ModelRegistry handed over
    outlives the request and every later caller of that canonical id inherits
    it.

    ``model_copy`` keeps the concrete chat class and shares the underlying
    OpenAI client, so the copy costs no connection setup.
    """
    if not force and not (sheets_active_slug.get() or "").strip():
        return chat_model
    hay = (model_id or "").lower()
    if not any(token in hay for token in ("gpt-5", "o3", "o4", "sonnet", "opus", "gemini")):
        return chat_model
    lc = getattr(chat_model, "model", chat_model)
    if not hasattr(lc, "reasoning_effort"):
        return chat_model
    if declares_reasoning(lc):
        # The registration already decided. Adding a top-level reasoning_effort
        # on top of an extra_body reasoning block puts the same decision in a
        # request twice, and OpenRouter answers reasoning.effort alongside
        # reasoning.max_tokens with a 400, so a registration using the
        # max_tokens form would fail every sheets turn.
        return chat_model
    try:
        reasoning = lc.model_copy(update={"reasoning_effort": "high"})
    except Exception:  # noqa: BLE001
        return chat_model
    import logging

    logging.getLogger(__name__).warning(
        "sheets turn supplying reasoning_effort=high to %r, whose registration "
        "declares no reasoning config. Declare it on that ModelDefinition "
        "instead: this fallback is invisible from the model catalog and "
        "applies to sheets only, so the same model answers a workbook differently "
        "than it answers anything else.",
        model_id,
    )
    if lc is chat_model:
        return reasoning
    # The wrapper is shared too, so hand back a copy of it rather than
    # repointing the registry entry's model at the copy.
    wrapper = copy.copy(chat_model)
    wrapper.model = reasoning
    return wrapper
