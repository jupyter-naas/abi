import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi.agents.documents.policy import (
    DEFAULT_DOCUMENTS_MODEL,
    MAX_DOCUMENTS_SEARCHES,
    MAX_DOCUMENTS_SECTION_READS,
    apply_documents_model_override,
    attach_documents_research_note,
    bind_documents_reasoning,
    bind_documents_research_policy,
    configured_documents_model,
    load_documents_chat_model,
    note_documents_list,
    note_documents_section_read,
    note_documents_web_search,
    reject_repeat_list_document_sections,
    reject_documents_section_read,
    reject_unresearched_documents_write,
    resolve_documents_llm_model,
    documents_brief_requires_research,
    documents_research_tools,
    documents_search_budget_remaining,
    documents_search_tool_bound,
    validate_configured_documents_model,
)
from naas_abi_core.services.agent.context import (
    note_documents_write,
    documents_active_slug,
    documents_brief,
    documents_list_calls,
    documents_research_queries,
    documents_research_required,
    documents_section_read_indexes,
    documents_writes_completed,
)


def test_default_sections_model_is_claude_sonnet_5() -> None:
    assert DEFAULT_DOCUMENTS_MODEL == "anthropic/claude-sonnet-5"


@contextmanager
def _configured(
    sections_model: str,
    agent_model: str,
    registry: Any = None,
    agent_provider: str | None = None,
) -> Iterator[None]:
    """Register an ABIModule whose configuration the policy will read.

    ``configured_documents_model`` reads ``ABIModule.get_instance()``, so the
    fallback cannot be observed without a module registered as the
    process-wide instance. Constructing one registers it, so the previous
    instance has to be put back afterwards or every later test in the process
    inherits this throwaway configuration.
    """
    from naas_abi import ABIModule
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        GlobalConfig,
    )
    from naas_abi_core.module.Module import BaseModule

    previous = BaseModule._instances.get(ABIModule)
    ABIModule(
        SimpleNamespace(services=SimpleNamespace(model_registry=registry)),  # type: ignore[arg-type]
        ABIModule.Configuration(
            global_config=GlobalConfig(ai_mode="cloud"),
            abi_agent_model=agent_model,
            abi_agent_provider=agent_provider,
            abi_documents_agent_model=sections_model,
        ),
    )
    try:
        yield
    finally:
        if previous is None:
            BaseModule._instances.pop(ABIModule, None)
        else:
            BaseModule._instances[ABIModule] = previous


def test_configured_documents_model_falls_back_to_the_general_agent_model() -> None:
    """With no sections model named, sections run on the model the rest of chat uses.

    The alternative is an id ABI ships but cannot resolve. A sections turn wants
    a reasoning-capable model and the general default may well not be one, but
    an operator who never named a sections model is better served by the model
    their chat already runs on than by a canonical id no loaded module
    registered.
    """
    with _configured(sections_model="", agent_model="claude-sonnet-5"):
        assert configured_documents_model() == "claude-sonnet-5"


def test_configured_documents_model_prefers_the_sections_model_when_it_is_named() -> None:
    """The fallback must not outrank an explicit setting."""
    with _configured(
        sections_model="anthropic/claude-sonnet-5",
        agent_model="google/gemma-4-26b-a4b-it:free",
    ):
        assert configured_documents_model() == "anthropic/claude-sonnet-5"


def test_sections_turn_warns_when_the_fallback_overrides_the_selection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Being overridden by the fallback is still being overridden.

    The warning exists so a user whose model was swapped out finds out, and
    that is worth exactly as much when the winner is the general agent model
    as when it is a configured sections model. Muting it on this path would put
    the quietest branch back where the original bug lived.
    """
    with (
        _configured(sections_model="", agent_model="claude-sonnet-5"),
        caplog.at_level(logging.WARNING, logger="naas_abi.agents.documents.policy"),
    ):
        effective = resolve_documents_llm_model("gpt-4.1-mini")

    assert effective == "claude-sonnet-5"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "gpt-4.1-mini" in message
    assert "claude-sonnet-5" in message


def test_resolve_documents_llm_model_always_returns_the_configured_model() -> None:
    """Every incoming selection resolves to the configured sections model.

    The previous version returned the caller's selection unless it appeared in
    a hand-maintained list of nine weak model ids, which is an allowlist of one
    written inside out: every model released after the list was written was
    treated as good enough for a document until someone shipped a document on it and
    added it. A strong-looking selection is checked here alongside the weak
    ones so the rule is one rule, not a lookup.
    """
    assert resolve_documents_llm_model("gpt-4.1-mini", sections_default="gpt-5") == "gpt-5"
    assert (
        resolve_documents_llm_model("google/gemma-4-26b-a4b-it:free", sections_default="gpt-5")
        == "gpt-5"
    )
    assert resolve_documents_llm_model("gpt-5.2", sections_default="gpt-5") == "gpt-5"
    assert resolve_documents_llm_model(None, sections_default="gpt-5") == "gpt-5"
    assert resolve_documents_llm_model(None, sections_default=None) == DEFAULT_DOCUMENTS_MODEL


def test_resolve_documents_llm_model_warns_when_it_overrides_the_selection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Replacing the user's model silently is the bug this design replaces.

    The server now decides the sections model outright, so a user who picks Opus
    for a document gets the configured model instead. That is the accepted
    tradeoff, but only because it is announced. Nothing on this path logged
    anything before, which is why a mini model writing template filler took a
    full session to find.
    """
    with caplog.at_level(logging.WARNING, logger="naas_abi.agents.documents.policy"):
        effective = resolve_documents_llm_model("gpt-5.2", sections_default="gpt-5")

    assert effective == "gpt-5"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "gpt-5.2" in message
    assert "gpt-5" in message


def test_resolve_documents_llm_model_is_quiet_when_nothing_was_overridden(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A warning on every sections turn is a warning nobody reads.

    Only a genuine substitution is worth a line: the selection already being
    the sections model, or there being no selection at all, took nothing away
    from the user.
    """
    with caplog.at_level(logging.WARNING, logger="naas_abi.agents.documents.policy"):
        assert resolve_documents_llm_model("gpt-5", sections_default="gpt-5") == "gpt-5"
        assert resolve_documents_llm_model(None, sections_default="gpt-5") == "gpt-5"
        assert resolve_documents_llm_model("", sections_default="gpt-5") == "gpt-5"

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_apply_documents_model_override_when_document_open() -> None:
    """Inverted: a strong selection no longer survives an open document either.

    This assertion used to read ``== "gpt-5.2"``. The client's selection won
    whenever it was not on the weak list, so the configured sections model was
    only ever a fallback, and adding a model to the list was the only way to
    route a document onto it. The configured model now owns every sections turn, and
    the pair of assertions below is the whole behaviour change.
    """
    assert apply_documents_model_override("gpt-4.1-mini", None, None) == "gpt-4.1-mini"
    assert (
        apply_documents_model_override("gpt-4.1-mini", {"documents": {}}, None) == "gpt-4.1-mini"
    )
    assert (
        apply_documents_model_override(
            "gpt-4.1-mini",
            {"documents": {"slug": "iran-now"}},
            None,
        )
        == configured_documents_model()
    )
    assert (
        apply_documents_model_override(
            "gpt-5.2",
            {"documents": {"slug": "iran-now"}},
            None,
        )
        == configured_documents_model()
    )


def test_first_create_brief_requires_research() -> None:
    assert documents_brief_requires_research(
        "create a document about what's going on in iran now",
        has_prior_assistant=False,
    )
    assert documents_brief_requires_research(
        "Iran situation briefing",
        has_prior_assistant=False,
    )


def test_copy_edit_does_not_require_research() -> None:
    assert not documents_brief_requires_research(
        "change the title to Q3 Review",
        has_prior_assistant=True,
    )
    assert not documents_brief_requires_research(
        "fix typo on section 2",
        has_prior_assistant=False,
    )


def test_followup_news_brief_still_requires_research() -> None:
    assert documents_brief_requires_research(
        "add the latest news from today",
        has_prior_assistant=True,
    )


def test_followup_write_now_does_not_require_another_search() -> None:
    assert not documents_brief_requires_research(
        "Insert the drafted copy into the open file. Do not search.",
        has_prior_assistant=True,
    )


def test_write_gate_blocks_until_web_search() -> None:
    documents_research_required.set(True)
    documents_research_queries.set([])
    blocked = reject_unresearched_documents_write()
    assert blocked is not None
    assert "web_search" in blocked["error"]

    note_documents_web_search("Iran latest developments 2026")
    assert reject_unresearched_documents_write() is None
    documents_research_required.set(False)
    documents_research_queries.set(None)


@contextmanager
def _unimportable(*prefixes: str) -> Iterator[None]:
    """Make each prefix and its submodules raise ImportError on import.

    Monkeypatching the imported name would test a different failure. The one
    that ships is an ImportError raised while the module is being loaded, in a
    deployment where the package simply is not installed, so the finder has to
    be the thing that refuses.
    """

    def blocked(fullname: str) -> bool:
        return any(
            fullname == prefix or fullname.startswith(f"{prefix}.") for prefix in prefixes
        )

    class _Blocker:
        def find_spec(self, fullname: str, path=None, target=None) -> None:
            if blocked(fullname):
                raise ImportError(f"blocked by test: {fullname}")
            # Falling through to None hands everything else to the real finders.

    blocker = _Blocker()
    evicted = {name: mod for name, mod in sys.modules.items() if blocked(name)}
    for name in evicted:
        del sys.modules[name]
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(evicted)


def test_research_tools_bind_from_this_package() -> None:
    """ABI has to own the search stack the sections gate depends on.

    The tools must resolve from this package. A deployment that does not have
    a sibling application on the path still has to bind search.
    """
    bound = {tool.name for tool in documents_research_tools()}

    assert bound == {"web_search", "web_fetch"}


def test_write_gate_opens_when_no_search_tool_can_be_bound() -> None:
    """A gate whose precondition is unsatisfiable must not block.

    Only ``web_search`` can fill ``documents_research_queries``. With no search
    tool bound the gate rejected every document write on a factual brief forever,
    and told the model to retry after a search it could not run.
    """
    with _unimportable("naas_abi.agents.tools.web_tools"):
        assert documents_research_tools() == []
        bind_documents_research_policy(
            "create a document about what's going on in iran now",
            has_prior_assistant=False,
            client_context={"documents": {"slug": "iran-now"}},
        )
        try:
            assert documents_research_queries.get() == []
            assert reject_unresearched_documents_write() is None
        finally:
            documents_research_required.set(False)
            documents_research_queries.set(None)
            documents_active_slug.set(None)


def test_write_gate_still_blocks_while_search_is_available() -> None:
    """The open-on-missing-search branch must not disarm the working gate."""
    documents_research_required.set(True)
    documents_research_queries.set([])
    try:
        assert documents_search_tool_bound() is True
        blocked = reject_unresearched_documents_write()
        assert blocked is not None
    finally:
        documents_research_required.set(False)
        documents_research_queries.set(None)


def test_bind_policy_sets_gate_for_open_document() -> None:
    required = bind_documents_research_policy(
        "create a document about what's going on in iran now",
        has_prior_assistant=False,
        client_context={"documents": {"slug": "iran-now"}},
    )
    assert required is True
    assert documents_research_required.get() is True
    assert documents_research_queries.get() == []
    assert documents_active_slug.get() == "iran-now"
    documents_research_required.set(False)
    documents_research_queries.set(None)
    documents_active_slug.set(None)


def test_search_budget_stops_after_four_queries() -> None:
    documents_research_required.set(True)
    documents_research_queries.set([])

    class _Tool:
        def __init__(self) -> None:
            self.calls = 0

        def func(self, query: str, max_results: int = 8) -> str:
            self.calls += 1
            return f"ok:{query}"

    wrapped = attach_documents_research_note(_Tool())
    for i in range(MAX_DOCUMENTS_SEARCHES):
        assert wrapped.func(f"q{i}").startswith("ok:")
    blocked = wrapped.func("one more")
    assert "Search budget reached" in blocked
    assert documents_search_budget_remaining() == 0
    documents_research_required.set(False)
    documents_research_queries.set(None)


def test_documents_creation_requested_detects_a_document_brief_in_main_chat() -> None:
    from naas_abi.agents.documents.policy import documents_creation_requested

    assert documents_creation_requested("create a document about the latest news about AI")
    assert documents_creation_requested("Make me a document on Q3 revenue")
    assert documents_creation_requested("build a report on the Iran situation")
    assert documents_creation_requested("write me a competitive report")
    # Not a document request.
    assert not documents_creation_requested("what is the capital of France?")
    assert not documents_creation_requested("summarise this document")
    assert not documents_creation_requested("")


def test_documents_creation_requested_detects_a_french_document_brief() -> None:
    """A French brief must arm the sections path, not fall through to plain chat."""
    from naas_abi.agents.documents.policy import documents_creation_requested

    assert documents_creation_requested(
        "fais un rapport de la concurrence entre les cabinets"
    )
    assert documents_creation_requested("crée un document sur Saint-Gobain")
    assert documents_creation_requested("prépare un document sur l'hydrogène vert")
    # Not a document request.
    assert not documents_creation_requested("quelle est la capitale de la France ?")
    assert not documents_creation_requested("résume ce document")


def test_research_policy_records_the_brief_for_naming() -> None:
    """The document name comes from the brief, so the turn has to keep it."""
    from naas_abi_core.services.agent.context import documents_brief

    token = documents_brief.set(None)
    try:
        bind_documents_research_policy(
            "fais des sections sur les matériaux de construction",
            False,
            None,
        )
        assert documents_brief.get() == "fais des sections sur les matériaux de construction"
    finally:
        documents_brief.reset(token)


def test_research_policy_arms_from_main_chat_without_an_open_document() -> None:
    """Capability A: a news document asked for in the main chat still researches."""
    from naas_abi_core.services.agent.context import (
        documents_creation_intent,
        documents_research_required,
    )

    tokens = (
        documents_research_required.set(False),
        documents_creation_intent.set(False),
    )
    try:
        required = bind_documents_research_policy(
            "create a document about the latest news about AI",
            False,
            None,
        )
        assert required is True
        assert documents_research_required.get() is True
        assert documents_creation_intent.get() is True
    finally:
        documents_research_required.reset(tokens[0])
        documents_creation_intent.reset(tokens[1])


def test_research_policy_stays_off_for_ordinary_main_chat() -> None:
    from naas_abi_core.services.agent.context import (
        documents_creation_intent,
        documents_research_required,
    )

    tokens = (
        documents_research_required.set(False),
        documents_creation_intent.set(False),
    )
    try:
        assert bind_documents_research_policy("what is 2 + 2?", False, None) is False
        assert documents_research_required.get() is False
        assert documents_creation_intent.get() is False
    finally:
        documents_research_required.reset(tokens[0])
        documents_creation_intent.reset(tokens[1])


def test_load_documents_chat_model_rejects_a_missing_model_id() -> None:
    """A caller that has no model id must not silently get the configured one.

    resolve_documents_llm_model treats an empty model id as "use the default", so
    a caller that dropped the model the turn was routed to built a chat model
    for a different model with no error and no log line. Removing the parameter
    default does not close that: passing None explicitly reaches the same
    resolve call. The information loss has to raise.
    """
    for missing in (None, "", "   "):
        with pytest.raises(ValueError, match="model id"):
            load_documents_chat_model(missing)  # type: ignore[arg-type]


def test_load_documents_chat_model_returns_the_model_the_registry_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registry already holds the sections model. Ask it, do not rebuild it.

    This asserts identity, not shape. A hand-built ChatOpenAI with the same id
    and the same base_url compares fine on inspection and is still wrong: it
    drops whatever the registration carries that a constructor call cannot
    guess, which for this model is extra_body reasoning effort, the retry
    count and the context window.

    ``OPENROUTER_API_KEY`` is set deliberately. The deleted code sniffed the
    environment for an ``sk-or-`` key and built its own client whenever it
    found one, so an ambient key changed which object a sections turn ran on.
    With the key present the identity assertion is the difference between the
    two implementations.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    registry = _registry_with_sections_model("anthropic/claude-sonnet-5")
    registered = registry.get_chat_model(
        "anthropic/claude-sonnet-5",
        provider="openrouter",
    )

    with _configured(
        sections_model="anthropic/claude-sonnet-5",
        agent_model="google/gemma-4-26b-a4b-it:free",
        registry=registry,
        agent_provider="openrouter",
    ):
        loaded = load_documents_chat_model("anthropic/claude-sonnet-5")

    assert loaded is registered


def test_load_documents_chat_model_raises_when_nothing_registered_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unresolvable sections model must fail here, not fall back silently.

    The version this replaces answered a missing registration by constructing
    a client for the id anyway, so a model nothing had registered still
    produced an object and failed later at the provider, as an HTTP error with
    no mention of the registry or of the config key that named the id. A silent
    fallback at this boundary is the bug class the branch exists to remove, so
    the registry's error has to reach the caller.
    """
    from naas_abi_core.services.model_registry.ModelRegistryPort import (
        ModelNotFoundError,
    )
    from naas_abi_core.services.model_registry.ModelRegistryService import (
        ModelRegistryService,
    )

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    with (
        _configured(
            sections_model="anthropic/claude-sonnet-5",
            agent_model="google/gemma-4-26b-a4b-it:free",
            registry=ModelRegistryService(),
            agent_provider="openrouter",
        ),
        pytest.raises(ModelNotFoundError, match="anthropic/claude-sonnet-5"),
    ):
        load_documents_chat_model("anthropic/claude-sonnet-5")


def _registry_with_sections_model(
    canonical_id: str = "claude-sonnet-5",
    extra_body: dict | None = None,
) -> Any:
    """A ModelRegistry holding one entry, wrapped the way production wraps it.

    A mock cannot show this bug. The leak is a plain attribute write onto the
    LangChain object the registry stores, so the object under test has to be a
    real ChatOpenAI inside a real ChatModel inside a real registry.

    ``extra_body`` is where a registration declares reasoning for an OpenRouter
    model, which is how the downstream install this policy was written against
    declares it.
    """
    from langchain_openai import ChatOpenAI
    from naas_abi_core.models.Model import ChatModel
    from naas_abi_core.services.model_registry.ModelRegistryService import (
        ModelRegistryService,
    )
    from pydantic import SecretStr

    registry = ModelRegistryService()
    registry.register(
        canonical_id,
        ChatModel(
            model_id="anthropic/claude-sonnet-5",
            provider="openrouter",
            model=ChatOpenAI(
                model="anthropic/claude-sonnet-5",
                api_key=SecretStr("sk-or-test"),
                base_url="https://openrouter.ai/api/v1",
                timeout=180,
                extra_body=extra_body,
            ),
        ),
    )
    return registry


def test_bind_documents_reasoning_leaves_a_declared_registration_alone() -> None:
    """A registration that already asks for reasoning is not asked twice.

    One request would then carry the same decision in two places, extra_body's
    reasoning.effort and a top-level reasoning_effort. Duplication is the mild
    version. OpenRouter rejects reasoning.effort alongside reasoning.max_tokens
    with a 400, so a registration spelling its reasoning with max_tokens would
    have every sections turn fail outright, and the cause would read as a
    provider problem rather than as this function's contribution.
    """
    registry = _registry_with_sections_model(extra_body={"reasoning": {"effort": "high"}})
    shared = registry.get_chat_model("claude-sonnet-5", provider="openrouter")

    token = documents_active_slug.set("iran-now")
    try:
        bound = bind_documents_reasoning(shared, "anthropic/claude-sonnet-5")
    finally:
        documents_active_slug.reset(token)

    assert bound is shared
    assert bound.model.reasoning_effort is None
    assert bound.model.extra_body == {"reasoning": {"effort": "high"}}


def test_bind_documents_reasoning_says_so_when_it_supplies_the_effort(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Supplying effort the registration did not ask for has to be audible.

    While this fires, the model runs on a setting that appears nowhere near
    its ModelDefinition and applies on no other path. Silent, that is the same
    model answering a document differently than it answers anything else, with
    nothing to read that explains the difference. Naming the model is the
    point: the fix is to declare reasoning on that registration, and a line
    that does not say which one sends the reader to look through thirty.
    """
    registry = _registry_with_sections_model()
    shared = registry.get_chat_model("claude-sonnet-5", provider="openrouter")

    token = documents_active_slug.set("iran-now")
    try:
        with caplog.at_level(logging.WARNING, logger="naas_abi.agents.documents.policy"):
            bound = bind_documents_reasoning(shared, "anthropic/claude-sonnet-5")
    finally:
        documents_active_slug.reset(token)

    assert bound.model.reasoning_effort == "high"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "anthropic/claude-sonnet-5" in warnings[0].getMessage()


def test_bind_documents_reasoning_force_applies_without_an_open_document() -> None:
    """DocumentsAgent.New has no slug yet; main-chat create still needs reasoning."""
    registry = _registry_with_sections_model()
    shared = registry.get_chat_model("claude-sonnet-5", provider="openrouter")

    token = documents_active_slug.set("")
    try:
        bound = bind_documents_reasoning(shared, "anthropic/claude-sonnet-5", force=True)
    finally:
        documents_active_slug.reset(token)

    assert shared.model.reasoning_effort is None
    assert bound.model.reasoning_effort == "high"


def test_bind_documents_reasoning_leaves_the_shared_registry_model_clean() -> None:
    """A sections turn must not write reasoning effort into the shared catalog.

    AbiAgent.New calls bind_documents_reasoning on whatever the ModelRegistry
    handed it, and the registry hands back the registered entry itself rather
    than a copy. Writing the attribute through therefore outlives the request:
    every later caller of that canonical id inherits high reasoning effort,
    sections or not, permanently, with nothing recording that it happened.

    Asserting only that the returned object reads "high" would pass against
    the write-through version, so the original and a second fetch are checked
    too.
    """
    registry = _registry_with_sections_model()
    shared = registry.get_chat_model("claude-sonnet-5", provider="openrouter")

    token = documents_active_slug.set("iran-now")
    try:
        bound = bind_documents_reasoning(shared, "anthropic/claude-sonnet-5")
    finally:
        documents_active_slug.reset(token)

    assert shared.model.reasoning_effort is None
    assert bound.model.reasoning_effort == "high"
    refetched = registry.get_chat_model("claude-sonnet-5", provider="openrouter")
    assert refetched.model.reasoning_effort is None


def test_bind_documents_reasoning_keeps_the_chat_class_and_shares_the_client() -> None:
    """The copy has to stay a chat model, and has to stay cheap.

    ``model.bind(...)`` is the obvious way to avoid the write, but it returns a
    RunnableBinding and Agent asserts isinstance(chat_model, BaseChatModel |
    ChatModel), so a bound model is rejected at construction. A model_copy
    keeps the concrete class, and it shares the underlying OpenAI client rather
    than opening a new connection pool per sections turn.
    """
    from langchain_openai import ChatOpenAI

    registry = _registry_with_sections_model()
    shared = registry.get_chat_model("claude-sonnet-5", provider="openrouter")

    token = documents_active_slug.set("iran-now")
    try:
        bound = bind_documents_reasoning(shared, "anthropic/claude-sonnet-5")
    finally:
        documents_active_slug.reset(token)

    assert isinstance(bound.model, ChatOpenAI)
    assert bound.model.root_client is shared.model.root_client


def test_model_override_upgrades_a_document_request_from_main_chat() -> None:
    """The document request from the main chat is the turn that writes the document.

    No document is open on that turn, so the brief is the only signal that the
    sections model should own it. Without this branch a chat-created document runs
    on whatever the composer had selected and comes out as template junk.
    """
    # No document open and no document asked for: leave the user's choice alone.
    assert (
        apply_documents_model_override("gpt-4.1-mini", None, "what is 2 + 2?")
        == "gpt-4.1-mini"
    )
    # No document open, but the user asked for one.
    assert (
        apply_documents_model_override(
            "gpt-4.1-mini",
            None,
            "create a document about the latest news about AI",
        )
        == DEFAULT_DOCUMENTS_MODEL
    )


def test_validate_configured_documents_model_rejects_an_unregistered_id() -> None:
    """A typo in ``abi_documents_agent_model`` has to fail the boot.

    It cannot fail the turn any more. The configured model is now the only
    model a sections turn can run on, so a mistyped id is not a degraded document,
    it is every document broken, discovered whenever someone next opens Documents.
    The message carries the id because that is the thing to go and fix.
    """
    from naas_abi_core.services.model_registry.ModelRegistryPort import (
        DefaultModelNotResolvedError,
    )
    from naas_abi_core.services.model_registry.ModelRegistryService import (
        ModelRegistryService,
    )

    with pytest.raises(DefaultModelNotResolvedError, match="claude-sonnet-5-typo"):
        validate_configured_documents_model(
            ModelRegistryService(),
            "anthropic/claude-sonnet-5-typo",
        )


def test_validate_configured_documents_model_skips_when_nothing_is_configured() -> None:
    """No sections model configured is a valid configuration, not a boot failure.

    No module in ABI registers ``anthropic/claude-sonnet-5``; it arrives with
    a downstream application. ABI shipping it as the sections default therefore
    made ABI's own boot fail its own check, with an empty
    registry and nothing an operator of a bare ABI could do about it. Unset has
    to mean "sections follow the general agent model" and skip the check, while a
    value that was actually typed still gets resolved or refused.
    """
    from naas_abi_core.services.model_registry.ModelRegistryService import (
        ModelRegistryService,
    )

    for unset in (None, "", "   "):
        validate_configured_documents_model(ModelRegistryService(), unset)


def test_validate_configured_documents_model_accepts_a_registered_id() -> None:
    """Registered means registered, not constructible.

    No provider is passed to the registry on purpose. ``get_chat_model`` falls
    back to building an off-catalog model through the provider's chat factory,
    and a factory will build any id it is handed, so pinning a provider here
    would make every possible typo resolve and the check would assert nothing.
    """
    validate_configured_documents_model(_registry_with_sections_model(), "claude-sonnet-5")


def test_list_document_sections_is_once_per_turn() -> None:
    tokens = (
        documents_list_calls.set(0),
        documents_section_read_indexes.set([]),
        documents_writes_completed.set([]),
    )
    try:
        assert reject_repeat_list_document_sections() is None
        note_documents_list()
        blocked = reject_repeat_list_document_sections()
        assert blocked is not None
        assert "already ran this turn" in blocked["error"]
    finally:
        documents_list_calls.reset(tokens[0])
        documents_section_read_indexes.reset(tokens[1])
        documents_writes_completed.reset(tokens[2])


def test_section_read_budget_is_three_unique_sections() -> None:
    tokens = (
        documents_section_read_indexes.set([]),
        documents_writes_completed.set([]),
    )
    try:
        for index in range(MAX_DOCUMENTS_SECTION_READS):
            assert reject_documents_section_read(index) is None
            note_documents_section_read(index)
        blocked = reject_documents_section_read(MAX_DOCUMENTS_SECTION_READS)
        assert blocked is not None
        assert "budget reached" in blocked["error"]
        assert reject_documents_section_read(0) is not None
        assert "already read" in reject_documents_section_read(0)["error"]
    finally:
        documents_section_read_indexes.reset(tokens[0])
        documents_writes_completed.reset(tokens[1])


def test_section_read_refuses_a_section_already_written() -> None:
    tokens = (
        documents_section_read_indexes.set([]),
        documents_writes_completed.set([]),
    )
    try:
        note_documents_write("section 18")
        blocked = reject_documents_section_read(17)
        assert blocked is not None
        assert "already wrote" in blocked["error"]
        assert reject_documents_section_read(0) is None
    finally:
        documents_section_read_indexes.reset(tokens[0])
        documents_writes_completed.reset(tokens[1])


def test_bind_documents_research_policy_resets_the_read_budget() -> None:
    tokens = (
        documents_list_calls.set(4),
        documents_section_read_indexes.set([0, 1, 2]),
        documents_active_slug.set("untitled-mtsqs99k"),
        documents_brief.set(None),
    )
    try:
        bind_documents_research_policy(
            "adapt this document for Sanofi",
            has_prior_assistant=True,
            client_context={"documents": {"slug": "untitled-mtsqs99k"}},
        )
        assert documents_list_calls.get() == 0
        assert documents_section_read_indexes.get() == []
        assert reject_repeat_list_document_sections() is None
    finally:
        documents_list_calls.reset(tokens[0])
        documents_section_read_indexes.reset(tokens[1])
        documents_active_slug.reset(tokens[2])
        documents_brief.reset(tokens[3])
