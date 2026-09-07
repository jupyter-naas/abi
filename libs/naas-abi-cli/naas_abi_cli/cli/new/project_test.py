"""`.abi` submodule detection for `abi new project`.

`_add_abi_submodule`'s return value decides whether the generated
`pyproject.toml` points uv at `.abi/libs/*` or at PyPI. A false positive is not
cosmetic: uv gets path sources for directories that do not exist, and the
`uv add` at the end of project creation fails, so scaffolding dies halfway.
Every path that does not leave a usable `.abi/libs` must report False.
"""

from __future__ import annotations

import importlib
import subprocess

project = importlib.import_module("naas_abi_cli.cli.new.project")

_FRAMEWORK_PACKAGES = {
    "naas-abi",
    "naas-abi-core",
    "naas-abi-marketplace",
    "naas-abi-cli",
}


def _submodule_dir(project_path):
    return project_path / project.ABI_SUBMODULE_PATH / "libs"


def test_returns_false_when_git_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: None)

    assert project._add_abi_submodule(str(tmp_path)) is False


def test_returns_false_when_the_clone_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    def fake_run(cmd, **_kwargs):
        if "submodule" in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)

    assert project._add_abi_submodule(str(tmp_path)) is False


def test_returns_false_when_the_clone_leaves_no_libs(tmp_path, monkeypatch) -> None:
    """A clone that 'succeeded' but has an unexpected layout is still unusable."""
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")
    monkeypatch.setattr(
        project.subprocess,
        "run",
        lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 0),
    )

    assert project._add_abi_submodule(str(tmp_path)) is False


def test_returns_true_when_libs_is_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    def fake_run(cmd, **_kwargs):
        if "submodule" in cmd:
            _submodule_dir(tmp_path).mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)

    assert project._add_abi_submodule(str(tmp_path)) is True


def test_git_init_is_skipped_when_already_a_repo(tmp_path, monkeypatch) -> None:
    """`git submodule add` needs a repo, but re-initialising one is not free."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if "submodule" in cmd:
            _submodule_dir(tmp_path).mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)

    assert project._add_abi_submodule(str(tmp_path)) is True
    assert not any("init" in cmd for cmd in calls)


# =============================================================================
# End-to-end wiring: `abi new project` must actually emit the live sources.
#
# The conditional above is only useful if `new_project` passes the flag through
# to the template render, so drive the real command with the network calls
# (submodule clone, `uv add`, `abi config validate`) stubbed out.
# =============================================================================

def _run_new_project(tmp_path, monkeypatch, *extra_args, submodule_ok: bool):
    import tomllib

    from click.testing import CliRunner

    def fake_run(cmd, **kwargs):
        if "submodule" in cmd and submodule_ok:
            (tmp_path / "demo" / project.ABI_SUBMODULE_PATH / "libs").mkdir(
                parents=True, exist_ok=True
            )
        elif "submodule" in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    result = CliRunner().invoke(
        project.new_project,
        ["demo", str(tmp_path), "--domain", "localhost",
         "--without-local-deploy", *extra_args],
    )
    assert result.exit_code == 0, result.output

    generated = (tmp_path / "demo" / "pyproject.toml").read_text(encoding="utf-8")
    return tomllib.loads(generated), generated


def _invoke_new_project(tmp_path, monkeypatch, *extra_args):
    """Drive the command as above, but return the CLI result, not the manifest."""
    from click.testing import CliRunner

    monkeypatch.setattr(
        project.subprocess,
        "run",
        lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 0),
    )
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    result = CliRunner().invoke(
        project.new_project,
        ["demo", str(tmp_path), "--domain", "localhost", "--without-local-deploy",
         "--without-abi-submodule", *extra_args],
    )
    assert result.exit_code == 0, result.output
    return result


def test_new_project_emits_live_sources(tmp_path, monkeypatch) -> None:
    doc, _ = _run_new_project(tmp_path, monkeypatch, submodule_ok=True)

    sources = doc["tool"]["uv"]["sources"]
    assert set(sources) == _FRAMEWORK_PACKAGES
    assert sources["naas-abi-core"] == {
        "path": ".abi/libs/naas-abi-core",
        "editable": True,
    }


def test_new_project_falls_back_to_pypi_when_the_clone_fails(
    tmp_path, monkeypatch
) -> None:
    doc, rendered = _run_new_project(tmp_path, monkeypatch, submodule_ok=False)

    assert "sources" not in doc["tool"]["uv"]
    assert "# [tool.uv.sources]" in rendered


def test_new_project_without_the_submodule_flag_uses_pypi(
    tmp_path, monkeypatch
) -> None:
    doc, _ = _run_new_project(
        tmp_path, monkeypatch, "--without-abi-submodule", submodule_ok=True
    )

    assert "sources" not in doc["tool"]["uv"]


# =============================================================================
# Next steps.
#
# `abi` is a child process and cannot cd the calling shell, so the closing
# report is the only thing telling the caller where the project went. It has to
# name the absolute path and hand back a `cd` line that actually works from
# where the caller stands.
# =============================================================================

def test_next_steps_report_the_project_path_and_how_to_start(
    tmp_path, monkeypatch
) -> None:
    result = _invoke_new_project(tmp_path, monkeypatch)

    assert str(tmp_path / "demo") in result.output
    assert "cd " in result.output
    assert "  abi dev up" in result.output


def test_cd_target_is_relative_when_the_project_is_below_the_cwd(
    tmp_path, monkeypatch
) -> None:
    """The caller asked for `demo` here; echoing an absolute path back is noise."""
    monkeypatch.chdir(tmp_path)

    assert project._cd_argument(str(tmp_path / "demo")) == "demo"


def test_cd_target_is_absolute_when_the_project_is_outside_the_cwd(
    tmp_path, monkeypatch
) -> None:
    """`../../..`-style paths are not more readable than the real location."""
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "nested").mkdir(parents=True)
    monkeypatch.chdir(elsewhere / "nested")
    target = str(tmp_path / "demo")

    assert project._cd_argument(target) == target


def test_cd_target_is_quoted_when_the_path_has_spaces(tmp_path, monkeypatch) -> None:
    """The line is meant to be pasted into a shell, so it must survive one."""
    monkeypatch.chdir(tmp_path)

    assert project._cd_argument(str(tmp_path / "my demo")) == "'my demo'"

