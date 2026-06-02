import pytest
from naas_abi_core import logger
from naas_abi_marketplace.applications.x.agents.XAgent import XAgent

# Tool names the agent should expose. API tools come from the XIntegration
# `as_tools` factory; SPARQL tools come from XSparqlQueries.ttl via the
# templatablesparqlquery module.
EXPECTED_API_TOOL_NAMES = {
    "x_get_user_by_id",
    "x_get_user_by_username",
    "x_get_users_by_ids",
    "x_get_users_by_usernames",
    "x_get_user_tweets",
    "x_get_user_mentions",
    "x_get_user_liked_tweets",
    "x_get_user_followers",
    "x_get_user_following",
    "x_get_tweet_by_id",
    "x_get_tweets_by_ids",
    "x_search_recent_tweets",
}

EXPECTED_SPARQL_TOOL_NAMES = {
    "find_top_liked_tweets",
    "find_top_retweeted_tweets",
    "find_top_impression_tweets",
    "find_top_engaging_tweets",
    "find_tweets_by_author",
    "find_tweets_containing_keyword",
    "find_tweets_in_language",
    "find_tweets_since",
    "find_tweet_by_id",
    "find_top_authors_by_tweet_count",
    "find_language_distribution",
}


@pytest.fixture
def agent() -> XAgent:
    return XAgent.New()


# ---------------------------------------------------------------------------
# Tool wiring — verify both tool families are loaded on the agent
# ---------------------------------------------------------------------------


def test_get_tools_returns_x_sparql_tools():
    sparql_tools = XAgent.get_tools()

    names = {tool.name for tool in sparql_tools}
    missing = EXPECTED_SPARQL_TOOL_NAMES - names
    assert not missing, (
        f"XAgent.get_tools() is missing expected SPARQL tools: {sorted(missing)}. "
        f"Got: {sorted(names)}"
    )
    logger.info(f"SPARQL tools exposed by XAgent: {sorted(names)}")


def test_agent_exposes_api_and_sparql_tools(agent: XAgent):
    names = {tool.name for tool in agent.tools}

    missing_api = EXPECTED_API_TOOL_NAMES - names
    missing_sparql = EXPECTED_SPARQL_TOOL_NAMES - names
    assert not missing_api, f"Missing API tools on agent: {sorted(missing_api)}"
    assert not missing_sparql, f"Missing SPARQL tools on agent: {sorted(missing_sparql)}"
    logger.info(f"Agent total tools: {len(agent.tools)}")


# ---------------------------------------------------------------------------
# Routing — check the agent picks the right tool family per question
# ---------------------------------------------------------------------------


def _tool_call_names(agent: XAgent) -> set[str]:
    """Collect the names of every tool invoked during the last agent run.

    The Agent base class records LangChain messages on the shared state; tool
    invocations show up as ``ToolMessage`` entries carrying ``name`` (the
    tool's registered name).
    """
    names: set[str] = set()
    state = getattr(agent, "state", None)
    if state is None:
        return names
    for thread in getattr(state, "threads", {}).values():
        for msg in getattr(thread, "messages", []) or []:
            name = getattr(msg, "name", None)
            if name:
                names.add(name)
    return names


def _assert_routed_to(
    agent: XAgent, prompt: str, expected: set[str], forbidden: set[str] = frozenset()
):
    result = agent.invoke(prompt)
    assert result is not None, f"Agent returned None for prompt {prompt!r}"
    called = _tool_call_names(agent)
    logger.info(f"Prompt: {prompt!r} → tools called: {sorted(called)}")
    assert called & expected, (
        f"Expected the agent to call one of {sorted(expected)} for prompt "
        f"{prompt!r}, but it called {sorted(called) or 'no tools'}."
    )
    bad = called & forbidden
    assert not bad, (
        f"Agent called a forbidden tool {sorted(bad)} for prompt {prompt!r}; "
        f"all tools called: {sorted(called)}"
    )


def test_routes_most_liked_question_to_sparql_tool(agent: XAgent):
    _assert_routed_to(
        agent,
        "From the tweets in the knowledge graph, what are the 5 most liked tweets?",
        expected={"find_top_liked_tweets"},
        forbidden={"x_search_recent_tweets"},
    )


def test_routes_top_authors_question_to_sparql_tool(agent: XAgent):
    _assert_routed_to(
        agent,
        "Who are the top 3 most prolific authors in the X graph?",
        expected={"find_top_authors_by_tweet_count"},
        forbidden={"x_search_recent_tweets"},
    )


def test_routes_keyword_question_to_sparql_tool(agent: XAgent):
    _assert_routed_to(
        agent,
        "Show 5 tweets from the graph that contain the word 'roland'.",
        expected={"find_tweets_containing_keyword"},
        forbidden={"x_search_recent_tweets"},
    )


def test_routes_language_distribution_question_to_sparql_tool(agent: XAgent):
    _assert_routed_to(
        agent,
        "What languages are represented in the X graph, and how many tweets per language?",
        expected={"find_language_distribution"},
        forbidden={"x_search_recent_tweets"},
    )


def test_routes_handle_lookup_to_api_tool(agent: XAgent):
    _assert_routed_to(
        agent,
        "Look up the @NASA account on X live and tell me its description.",
        expected={"x_get_user_by_username"},
        forbidden=EXPECTED_SPARQL_TOOL_NAMES,
    )


def test_routes_live_search_to_api_tool(agent: XAgent):
    _assert_routed_to(
        agent,
        "Search X right now for English tweets about python from the last day "
        "(max 5 results).",
        expected={"x_search_recent_tweets"},
        forbidden=EXPECTED_SPARQL_TOOL_NAMES,
    )
