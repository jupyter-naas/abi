"""Documents chat policy: research first, then write, on the configured model.

Used by DocumentsAgent, sections tools, and Nexus chat so a current-events brief cannot
skip web_search and dump template filler into document.html.

The server owns the model for a sections turn. Whatever the composer had
selected, sections run on ``abi_documents_agent_model`` when it is set and on
``abi_agent_model`` when it is not, and either way a turn that overrides a
selection says so at warning level.

``abi_documents_agent_model`` is optional because ABI has no reasoning-capable id
it can ship: every one of them is registered by a marketplace or downstream
module that a given install may not enable. Set, it is checked against the
registry at boot, since it is then the only model any sections turn can run on
and a typo in it breaks every document rather than one. Unset, there is nothing to
check that the engine does not already check for ``abi_agent_model``.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from naas_abi_core.services.agent.context import (
    documents_active_slug,
    documents_brief,
    documents_creation_intent,
    documents_list_calls,
    documents_research_queries,
    documents_research_required,
    documents_section_read_indexes,
    documents_turn_active,
    documents_writes_completed,
)

# Last resort for callers that reach these helpers with no ABIModule
# registered, which in practice means no engine and no registry either. It is
# not a shipped default: ``abi_documents_agent_model`` is empty and sections follow
# ``abi_agent_model``.
#
# The comment that stood here said this id existed because a native Anthropic
# or ChatGPT registry id 401s against an OpenRouter key. That was the wrong
# diagnosis. OPENAI_BASE_URL was set and every OpenAI client in the process
# inherited it, so the requests were reaching the wrong endpoint.
DEFAULT_DOCUMENTS_MODEL = "anthropic/claude-sonnet-5"

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
    r"document|report|rapport|article|brief"
    r")\b",
    re.IGNORECASE,
)

_UNRESEARCHED_WRITE_ERROR = (
    "Research required before editing this document. Call web_search first with "
    "2 to 4 queries (latest developments, context, key actors, dates). "
    "Then retry this write."
)

MAX_DOCUMENTS_SEARCHES = 4
MAX_DOCUMENTS_SECTION_READS = 3
_SEARCH_BUDGET_MESSAGE = (
    "Search budget reached (4 queries). Do not call web_search or web_fetch "
    "again. Fill the open template with apply_document_commands. "
    "Do not leave seed placeholder copy. Do not append after the footer."
)
_LIST_ONCE_MESSAGE = (
    "list_document_sections already ran this turn. Use that outline. "
    "Do not list again. Fill the open template with apply_document_commands. "
    "Do not append after the footer."
)
_SECTION_READ_BUDGET_MESSAGE = (
    f"read_document_section budget reached ({MAX_DOCUMENTS_SECTION_READS} sections "
    "this turn). Do not read leftover sections. Write with "
    "apply_document_commands, then stop, or replace_in_document "
    "for one copy edit."
)
_SECTION_REREAD_MESSAGE = (
    "You already read this section this turn. Do not re-read it. "
    "Write or replace instead."
)
_SECTION_READ_AFTER_WRITE_MESSAGE = (
    "You already wrote this section this turn. Do not re-read it. "
    "Report what changed, or write a different section."
)
_READ_DOCUMENT_AFTER_WRITE_MESSAGE = (
    "Do not reread after writing. If leftover_placeholders is not empty, "
    "call apply_document_commands once with replace_text and replace_class. "
    "Do not call read_document."
)
_READ_DOCUMENT_ONCE_MESSAGE = (
    "read_document already ran this turn. Use that outline. "
    "Fill the open template with one apply_document_commands batch. "
    "Do not reread."
)
_REPLACE_ON_FILL_MESSAGE = (
    "replace_in_document is not available on a Documents fill turn. "
    "Call apply_document_commands once with replace_text and replace_class "
    "for every leftover seed slot. Do not reread."
)
_REPEAT_APPLY_MESSAGE = (
    "apply_document_commands already ran this turn. Stop. "
    "Do not call it again. Do not reread. Report leftover_placeholders."
)


def configured_documents_model() -> str:
    """The model a sections turn runs on: the sections model, else the agent model.

    ``abi_documents_agent_model`` is optional. Unset it does not mean "no sections
    model", it means "no sections-specific model", and the general agent model
    is the honest answer to that: it is the model the operator's chat already
    runs on and it is registered, because the engine resolves it in
    ``validate_defaults``. A sections brief would rather have a reasoning-capable
    model and the general default may not be one, which is why the setting
    exists, but a weaker registered model beats an id nothing registered.
    """
    try:
        from naas_abi import ABIModule

        configuration = ABIModule.get_instance().configuration
    except Exception:  # noqa: BLE001
        return DEFAULT_DOCUMENTS_MODEL
    for setting in ("abi_documents_agent_model", "abi_agent_model"):
        configured = getattr(configuration, setting, None)
        if configured and str(configured).strip():
            return str(configured).strip()
    return DEFAULT_DOCUMENTS_MODEL


def validate_configured_documents_model(
    registry: Any,
    configured: str | None = None,
) -> None:
    """Resolve the configured sections model, or refuse to start.

    Called at boot. Documents ignore the model the client selected, so this one id
    is the only model any sections turn can run on, and an id that does not
    resolve is not a degraded document but every document broken. Left unchecked it
    surfaces on whichever document someone opens next, which is exactly the shape
    of failure this whole change exists to remove.

    An empty ``configured`` is not checked. Nothing is being asserted about:
    no sections model was named, so sections follow the general agent model, and
    that id is already covered by ``ModelRegistryService.validate_defaults``.
    Checking it anyway is what made ABI fail its own boot, because the only id
    worth shipping as a sections default is registered by a downstream module and
    by nothing in ABI. This is deliberately not "fall back to
    ``configured_documents_model()``": that would resolve the general agent model
    under the sections key and report a mismatch against a setting the operator
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
            f"abi_documents_agent_model={model_id!r} is not registered as a chat model.\n"
            f"  -> set it under modules.naas_abi.config.abi_documents_agent_model, but no "
            f"loaded module registered a chat model with this id.\n"
            f"  -> likely cause: the module shipping that ModelDefinition is not enabled, "
            f"or the id is spelled differently there (the prefixed and bare forms are "
            f"two different canonical ids).\n"
            f"  -> currently registered model ids: {listing}"
        ) from exc


def resolve_documents_llm_model(
    incoming: str | None,
    sections_default: str | None = None,
) -> str:
    """Return the configured sections model. The client's selection never wins.

    This used to hand back ``incoming`` unless it matched a list of weak model
    ids. That list was an allowlist of one written inside out: every model
    released after it was written counted as good enough for a document until
    someone shipped a document on it and added it, and it had already grown two
    Gemma spellings and three GPT variants that way.

    Overriding a user's choice is only acceptable because it is announced.
    Nothing on this path logged anything, which is how a mini model writing
    template filler survived long enough to cost a session of debugging.
    """
    effective = (sections_default or "").strip() or configured_documents_model()
    raw = (incoming or "").strip()
    if raw and raw != effective:
        import logging

        logging.getLogger(__name__).warning(
            "sections turn overriding the selected model %r with the server's "
            "sections model %r (abi_documents_agent_model, or abi_agent_model when "
            "that is unset). Documents always run on the server's model.",
            raw,
            effective,
        )
    return effective


def open_documents_slug(client_context: dict | None) -> str:
    if not isinstance(client_context, dict):
        return ""
    documents = client_context.get("documents")
    if not isinstance(documents, dict):
        return ""
    return str(documents.get("slug") or "").strip()


def apply_documents_model_override(
    incoming: str | None,
    client_context: dict | None,
    message: str | None,
) -> str | None:
    """Route sections work onto the configured sections model.

    Covers both an open document and a document asked for from the main chat, where a
    model that skips tools writes template filler into the whole document.

    ``message`` is required rather than defaulting to ``None``. A default let a
    caller drop the user brief and silently keep the composer's model on the
    create-from-main-chat turn, which is the turn that writes the whole document.
    Callers with genuinely no message must pass ``None`` on purpose.
    """
    if open_documents_slug(client_context):
        return resolve_documents_llm_model(incoming)
    if message is not None and documents_creation_requested(message):
        return resolve_documents_llm_model(incoming)
    return incoming


def documents_brief_requires_research(message: str, has_prior_assistant: bool) -> bool:
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
    # Follow-up "write the document now" must not reset the research gate.
    return researchy


_DECK_NOUN_RE = re.compile(
    r"\b(document|documents|report|rapport|article|memo|paper|briefing"
    r"|sections)\b",
    re.IGNORECASE,
)
# French verbs matter: a brief written in French must arm the sections path too,
# otherwise it runs as an ordinary chat turn on whatever model was selected.
_MAKE_VERB_RE = re.compile(
    r"\b(create|make|build|draft|generate|prepare|put together|write|need|want"
    r"|fais|fait|faire|crée|cree|créer|creer|génère|genere|générer|generer"
    r"|prépare|prepare|préparer|rédige|redige|rédiger|construis|monte"
    r"|veux|voudrais|souhaite|besoin)\b",
    re.IGNORECASE,
)


def documents_creation_requested(message: str) -> bool:
    """True when the user is asking for a new document on a surface with none open.

    Requires both a making verb and a document noun so "summarise this document"
    or a passing mention of a section does not hijack an ordinary chat turn.
    """
    text = (message or "").strip()
    if not text:
        return False
    return bool(_MAKE_VERB_RE.search(text) and _DECK_NOUN_RE.search(text))


def bind_documents_research_policy(
    message: str,
    has_prior_assistant: bool,
    client_context: dict | None,
) -> bool:
    """Set request-scoped research gates. Returns whether search is required."""
    # Documents tools name a new (or still untitled) document after this brief.
    documents_brief.set((message or "").strip())
    slug = open_documents_slug(client_context) or (documents_active_slug.get() or "").strip()
    if not slug:
        # Main chat: no document open yet. A document request still has to research
        # before writing, and the agent needs a sections-sized step budget.
        creating = documents_creation_requested(message)
        documents_creation_intent.set(creating)
        if not creating:
            documents_research_required.set(False)
            return False
        documents_writes_completed.set([])
        _reset_sections_read_budget()
        required = documents_brief_requires_research(message, has_prior_assistant)
        documents_research_required.set(required)
        if required:
            documents_research_queries.set([])
        return required
    documents_active_slug.set(slug)
    documents_writes_completed.set([])
    _reset_sections_read_budget()
    required = documents_brief_requires_research(message, has_prior_assistant)
    documents_research_required.set(required)
    if required:
        documents_research_queries.set([])
    return required


def _reset_sections_read_budget() -> None:
    documents_list_calls.set(0)
    documents_section_read_indexes.set([])


def reject_repeat_list_document_sections() -> dict[str, Any] | None:
    """Refuse a second list_document_sections on this turn."""
    if documents_list_calls.get() >= 1:
        return {"error": _LIST_ONCE_MESSAGE}
    return None


def reject_read_document() -> dict[str, Any] | None:
    """Refuse a full-document reread after the first outline or any write."""
    if documents_writes_completed.get():
        return {"error": _READ_DOCUMENT_AFTER_WRITE_MESSAGE}
    if documents_list_calls.get() >= 1:
        return {"error": _READ_DOCUMENT_ONCE_MESSAGE}
    return None


def reject_replace_in_document_on_fill() -> dict[str, Any] | None:
    """Force apply_document_commands on a research/fill Documents turn."""
    if documents_turn_active() and documents_research_required.get():
        return {"error": _REPLACE_ON_FILL_MESSAGE}
    return None


def reject_repeat_apply_document_commands() -> dict[str, Any] | None:
    """One apply_document_commands persist per research/fill Documents turn."""
    if not (documents_turn_active() and documents_research_required.get()):
        return None
    written = documents_writes_completed.get() or []
    if "document commands" in written:
        return {"error": _REPEAT_APPLY_MESSAGE}
    return None


def note_documents_list() -> None:
    documents_list_calls.set(documents_list_calls.get() + 1)


def reject_documents_section_read(index: int) -> dict[str, Any] | None:
    """Refuse a re-read, a read after write, or a fourth unique section read."""
    written = documents_writes_completed.get() or []
    section_label = f"section {index + 1}"
    if section_label in written or "full document" in written:
        return {"error": _SECTION_READ_AFTER_WRITE_MESSAGE}
    seen = documents_section_read_indexes.get() or []
    if index in seen:
        return {"error": _SECTION_REREAD_MESSAGE}
    if len(seen) >= MAX_DOCUMENTS_SECTION_READS:
        return {"error": _SECTION_READ_BUDGET_MESSAGE}
    return None


def note_documents_section_read(index: int) -> None:
    bucket = documents_section_read_indexes.get()
    if bucket is None:
        documents_section_read_indexes.set([index])
        return
    if index not in bucket:
        bucket.append(index)


def note_documents_web_search(query: str) -> None:
    """Record that web_search ran this turn (unlocks sections writes)."""
    if not documents_research_required.get():
        return
    text = (query or "").strip()
    if not text:
        return
    bucket = documents_research_queries.get()
    if bucket is None:
        documents_research_queries.set([text])
        return
    bucket.append(text)


def reject_unresearched_documents_write() -> dict[str, Any] | None:
    """Block document writes until web_search has run for a research brief."""
    if not documents_research_required.get():
        return None
    queries = documents_research_queries.get()
    if queries:
        return None
    if not documents_search_tool_bound():
        # web_search is the only thing that can fill documents_research_queries,
        # so with no search tool bound this gate can never be satisfied. Held
        # shut, it fails every document write on a factual brief forever while
        # telling the model to retry after a search it cannot run.
        import logging

        logging.getLogger(__name__).warning(
            "sections research gate opened: no web_search tool is bound, so the "
            "document will be written without research"
        )
        return None
    return {"error": _UNRESEARCHED_WRITE_ERROR}


def documents_search_budget_remaining() -> int:
    queries = documents_research_queries.get() or []
    return max(0, MAX_DOCUMENTS_SEARCHES - len(queries))


def attach_documents_research_note(tool: Any) -> Any:
    """Wrap a web_search tool so successful calls unlock sections writes."""
    original = getattr(tool, "func", None)
    if original is None:
        return tool

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if documents_research_required.get() and documents_search_budget_remaining() <= 0:
            return _SEARCH_BUDGET_MESSAGE
        query = kwargs.get("query")
        if query is None and args:
            query = args[0]
        if isinstance(query, str) and query.strip():
            note_documents_web_search(query)
        return original(*args, **kwargs)

    tool.func = wrapped
    return tool


_SEARCH_STACK = "naas_abi.agents.tools.web_tools"


def documents_search_tool_bound() -> bool:
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


def documents_research_tools() -> list[Any]:
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
            "sections web search unavailable, the research gate will not be armed: %s",
            exc,
        )
        return []
    return [
        attach_documents_research_note(stack.make_web_search_tool()),
        stack.make_web_fetch_tool(),
    ]


def load_documents_chat_model(model_id: str) -> Any:
    """Return the registered chat model for the model this turn was routed to.

    The same lookup ``DocumentsAgent.New`` does, because it is the same question. The
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
    context window on every sections turn.

    Raises ``ValueError`` on an empty ``model_id``. ``resolve_documents_llm_model``
    reads an empty value as "use the configured sections default", so a caller
    that dropped the model the turn was routed to built a model for a different
    model with no error and no log line. There is no safe default at this
    boundary: a caller holding no model id has lost information, and the loss
    has to be visible where it happens.
    """
    if not (model_id or "").strip():
        raise ValueError(
            "load_documents_chat_model requires the model id the turn was routed "
            "to. Resolve it with resolve_documents_llm_model first."
        )

    from naas_abi import ABIModule

    abi = ABIModule.get_instance()
    resolved = resolve_documents_llm_model(model_id)
    chat = abi.engine.services.model_registry.get_chat_model(
        resolved,
        provider=abi.configuration.abi_agent_provider,
    )
    return bind_documents_reasoning(chat, resolved)


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


def bind_documents_reasoning(
    chat_model: Any,
    model_id: str,
    *,
    force: bool = False,
) -> Any:
    """Return a copy with high reasoning effort, leaving the caller's model alone.

    ``force=True`` is for DocumentsAgent.New: that agent only does sections work, so
    it must carry reasoning even when no document is open yet (main-chat create).
    Callers that still share a catalog model (the in-process retarget path)
    keep the default: bind only when a sections turn is already in progress.

    A fallback, not the design. The right home for reasoning config is the
    ``ModelDefinition`` that describes the model, next to its context window
    and its endpoint, where it is visible in the catalog and applies to every
    caller rather than to sections only. This exists because roughly thirty
    reasoning-capable models are registered upstream with no reasoning config
    at all, so on an install with ``abi_documents_agent_model`` unset it is the
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
    if not force and not (documents_active_slug.get() or "").strip():
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
        # max_tokens form would fail every sections turn.
        return chat_model
    try:
        reasoning = lc.model_copy(update={"reasoning_effort": "high"})
    except Exception:  # noqa: BLE001
        return chat_model
    import logging

    logging.getLogger(__name__).warning(
        "sections turn supplying reasoning_effort=high to %r, whose registration "
        "declares no reasoning config. Declare it on that ModelDefinition "
        "instead: this fallback is invisible from the model catalog and "
        "applies to sections only, so the same model answers a document differently "
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
