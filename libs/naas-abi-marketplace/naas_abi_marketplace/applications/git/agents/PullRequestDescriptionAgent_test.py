import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.git.agents.PullRequestDescriptionAgent import (
        PullRequestDescriptionAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.git"])

    return PullRequestDescriptionAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Pull Request" in result or "PullRequest" in result or "PR" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "pull request" in result.lower()
        or "description" in result.lower()
        or "git" in result.lower()
        or "github" in result.lower()
    ), result


@pytest.mark.parametrize("description", [None, "", "   "])
def test_store_pull_request_description_empty_is_recoverable(agent, description):
    tool = agent._tools_by_name["store_pull_request_description"]

    args = {} if description is None else {"description": description}
    result = tool.invoke(args)

    assert "ERROR" in result, result
    assert "description" in result.lower(), result
