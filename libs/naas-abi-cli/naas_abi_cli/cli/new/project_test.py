"""Tests for the post-scaffold guidance of `abi new project`.

Scaffolding lands in a *subdirectory*, so the shell is left one level above the
project. Without an explicit cd instruction the obvious next command — `abi dev
up` — runs outside the project, which used to start services against an env
with no `naas_abi_core` and fail 15s later with an unrelated-looking error.
"""

from naas_abi_cli.cli.new.project import _show_next_steps


def test_next_steps_tell_the_user_to_cd(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    _show_next_steps(str(tmp_path / "my-ai"))

    output = capsys.readouterr().out
    assert "cd my-ai" in output
    assert "abi dev up" in output


def test_next_steps_use_a_relative_path_the_user_can_paste(
    tmp_path, monkeypatch, capsys
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    project_path = str(workdir / "nested" / "my-ai")

    _show_next_steps(project_path)

    output = capsys.readouterr().out
    assert "cd nested/my-ai" in output
    # The absolute path is noise in a command the user is meant to copy.
    assert f"cd {project_path}" not in output


def test_next_steps_omit_cd_when_already_in_the_project(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    _show_next_steps(str(tmp_path))

    output = capsys.readouterr().out
    assert "cd " not in output
    assert "abi dev up" in output
