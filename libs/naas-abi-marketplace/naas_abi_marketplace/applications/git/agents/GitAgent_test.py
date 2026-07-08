import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.git.agents.GitAgent import (
        GitAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.git"])

    return GitAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    assert result is not None, result
    assert "git" in result.lower() or "pull request" in result.lower(), result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    assert result is not None, result
    lowered = result.lower()
    assert "commit" in lowered or "pull request" in lowered or "github" in lowered, (
        result
    )


def test_git_add_tool_registered(agent):
    assert "git_add" in agent._tools_by_name


def test_git_add_empty_paths(agent):
    tool = agent._tools_by_name["git_add"]
    result = tool.invoke({"paths": []})
    assert "No paths provided" in result, result


def _init_git_repo(path):
    import subprocess

    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "test"],
    ):
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)


def test_git_commit_nothing_staged_is_recoverable(agent, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    tool = agent._tools_by_name["git_commit"]
    result = tool.invoke({"message": "chore: update lockfile"})

    # Nothing is staged, so the tool must return a recoverable hint (not raise)
    # and must not create a commit.
    assert "Nothing is staged" in result, result
    assert "git_add" in result, result


def test_git_add_then_commit(agent, tmp_path, monkeypatch):
    import subprocess

    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("locked\n")

    add_tool = agent._tools_by_name["git_add"]
    add_result = add_tool.invoke({"paths": ["uv.lock"]})
    assert "Staged: uv.lock" in add_result, add_result

    commit_tool = agent._tools_by_name["git_commit"]
    commit_result = commit_tool.invoke({"message": "chore: update lockfile"})
    assert "Nothing is staged" not in commit_result, commit_result

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "chore: update lockfile" in log, log
