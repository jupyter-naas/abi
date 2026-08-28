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


def test_make_check_and_make_fix_tools_registered(agent):
    assert "make_check" in agent._tools_by_name
    assert "make_fix" in agent._tools_by_name


def test_system_prompt_requires_make_check_before_pr():
    from naas_abi_marketplace.applications.git.agents.GitAgent import GitAgent

    prompt = GitAgent.system_prompt.lower()
    assert "make_check" in prompt
    assert "make check" in prompt or "make_check" in prompt
    assert "do not create or update a pr until" in prompt or "first call `make_check`" in prompt


def test_make_check_reports_failure_without_makefile(agent, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = agent._tools_by_name["make_check"].invoke({})
    assert result.startswith("MAKE CHECK FAILED"), result


def test_make_check_timeout_decodes_bytes_output(agent, monkeypatch):
    import subprocess

    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["make", "check"],
            timeout=600,
            output=b"ran ruff\n",
            stderr=b"still typechecking\n",
        )

    monkeypatch.setattr(subprocess, "run", _timeout)
    result = agent._tools_by_name["make_check"].invoke({})
    assert result.startswith("MAKE CHECK FAILED (timed out"), result
    assert "ran ruff" in result, result
    assert "still typechecking" in result, result


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
    # and must not create a commit. It must not instruct the agent to auto-stage.
    assert "Nothing is staged" in result, result
    assert "Ask the user to stage" in result, result
    assert "Do not stage files on your own" in result, result

def _commit_file(path, name, content):
    import subprocess

    (path / name).write_text(content)
    subprocess.run(["git", "add", "--", name], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"add {name}", "-n"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_git_add_then_commit(agent, tmp_path, monkeypatch):
    import subprocess

    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    # uv.lock is a tracked file that then gets modified (the real scenario).
    _commit_file(tmp_path, "uv.lock", "locked\n")
    (tmp_path / "uv.lock").write_text("locked v2\n")

    add_tool = agent._tools_by_name["git_add"]
    add_result = add_tool.invoke({"paths": ["uv.lock"]})
    assert "Staged: uv.lock" in add_result, add_result

    commit_tool = agent._tools_by_name["git_commit"]
    commit_result = commit_tool.invoke({"message": "chore: update lockfile"})
    assert "Nothing is staged" not in commit_result, commit_result

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True, check=False
    ).stdout
    assert "chore: update lockfile" in log, log


def test_git_add_skips_untracked_files(agent, tmp_path, monkeypatch):
    import subprocess

    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    _commit_file(tmp_path, "uv.lock", "locked\n")
    # A modified tracked file plus an unrelated untracked scratch file.
    (tmp_path / "uv.lock").write_text("locked v2\n")
    (tmp_path / "_KICKSTART.md").write_text("scratch\n")

    add_tool = agent._tools_by_name["git_add"]
    result = add_tool.invoke({"paths": ["uv.lock", "_KICKSTART.md"]})

    assert "Staged: uv.lock" in result, result
    assert "_KICKSTART.md (untracked)" in result, result

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "uv.lock" in staged, staged
    assert "_KICKSTART.md" not in staged, staged


def test_git_diff_staged_empty_is_explicit(agent, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    _commit_file(tmp_path, "uv.lock", "locked\n")

    result = agent._tools_by_name["git_diff_staged"].invoke({})
    assert "STAGED DIFF: empty" in result, result
    assert "Nothing is staged" in result, result


def test_git_diff_staged_lists_staged_files(agent, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    _commit_file(tmp_path, "uv.lock", "locked\n")
    (tmp_path / "uv.lock").write_text("locked v2\n")
    agent._tools_by_name["git_add"].invoke({"paths": ["uv.lock"]})

    result = agent._tools_by_name["git_diff_staged"].invoke({})
    assert "STAGED DIFF: empty" not in result, result
    assert "ARE staged" in result, result
    assert "uv.lock" in result, result


def test_git_status_summarizes_staged_files(agent, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    _commit_file(tmp_path, "uv.lock", "locked\n")
    (tmp_path / "uv.lock").write_text("locked v2\n")
    agent._tools_by_name["git_add"].invoke({"paths": ["uv.lock"]})

    result = agent._tools_by_name["git_status"].invoke({})
    assert "staged_count=1" in result, result
    assert "uv.lock" in result, result


def test_git_add_skips_unchanged_files(agent, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    _commit_file(tmp_path, "uv.lock", "locked\n")  # committed, now unchanged

    add_tool = agent._tools_by_name["git_add"]
    result = add_tool.invoke({"paths": ["uv.lock"]})
    assert "no changes" in result, result
