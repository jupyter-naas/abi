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
    "naas-abi-proto",
    "naas-abi-sdk",
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


def _git(*args, cwd) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_the_submodule_clones_a_local_checkout(tmp_path) -> None:
    """`--abi-source <checkout>` tests a framework that is not on GitHub yet.

    Git refuses the file transport for submodules unless told otherwise
    (`transport 'file' not allowed`), so this runs the real git.
    """
    checkout = tmp_path / "abi"
    (checkout / "libs" / "naas-abi-sdk").mkdir(parents=True)
    (checkout / "libs" / "naas-abi-sdk" / "pyproject.toml").write_text("")
    _git("init", "-q", cwd=checkout)
    _git("add", ".", cwd=checkout)
    _git("commit", "-q", "-m", "init", cwd=checkout)
    target = tmp_path / "project"
    target.mkdir()

    assert project._add_abi_submodule(str(target), str(checkout)) is True
    assert (_submodule_dir(target) / "naas-abi-sdk" / "pyproject.toml").is_file()


def test_a_relative_source_is_cloned_from_where_the_command_ran(
    tmp_path, monkeypatch
) -> None:
    """git resolves a submodule's relative URL against the superproject's
    remote, not the caller's directory: pass it the absolute path."""
    (tmp_path / "abi").mkdir()
    monkeypatch.chdir(tmp_path)
    commands: list[list[str]] = []
    _invoke_new_project(tmp_path, monkeypatch, "--abi-source", "abi", commands=commands)

    [clone] = [cmd for cmd in commands if "submodule" in cmd]
    assert str(tmp_path / "abi") in clone
    assert "protocol.file.allow=always" in clone


def test_the_submodule_comes_from_github_by_default(tmp_path, monkeypatch) -> None:
    commands: list[list[str]] = []
    _invoke_new_project(tmp_path, monkeypatch, commands=commands)

    [clone] = [cmd for cmd in commands if "submodule" in cmd]
    assert project.ABI_SUBMODULE_URL in clone
    assert "protocol.file.allow=always" not in clone


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


def _invoke_new_project(tmp_path, monkeypatch, *extra_args, commands=None):
    """Drive the command as above, but return the CLI result, not the manifest.

    The submodule clone succeeds; ``commands`` collects every command run.
    """
    from click.testing import CliRunner

    def fake_run(cmd, **_kwargs):
        if commands is not None:
            commands.append(cmd)
        if "submodule" in cmd:
            (tmp_path / "demo" / project.ABI_SUBMODULE_PATH / "libs").mkdir(
                parents=True, exist_ok=True
            )
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    return CliRunner().invoke(
        project.new_project,
        ["demo", str(tmp_path), "--domain", "localhost", "--without-local-deploy",
         *extra_args],
    )


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
    doc, rendered = _run_new_project(
        tmp_path, monkeypatch, "--without-nats", submodule_ok=False
    )

    assert "sources" not in doc["tool"]["uv"]
    assert "# [tool.uv.sources]" in rendered


def test_new_project_without_the_submodule_flag_uses_pypi(
    tmp_path, monkeypatch
) -> None:
    doc, _ = _run_new_project(
        tmp_path,
        monkeypatch,
        "--without-abi-submodule",
        "--without-nats",
        submodule_ok=True,
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
    assert result.exit_code == 0, result.output

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



def test_new_project_generates_the_admin_password_in_env(tmp_path, monkeypatch) -> None:
    result = _invoke_new_project(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output

    env = (tmp_path / "demo" / ".env").read_text(encoding="utf-8")
    password = next(
        line.split("=", 1)[1]
        for line in env.splitlines()
        if line.startswith("NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD=")
    )
    assert len(password) >= 24
    assert password not in ("admin", "Admin1234!")
    assert "admin@example.com" in result.output
    assert "NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD" in result.output


def test_new_project_keeps_secrets_out_of_git_and_out_of_the_image(
    tmp_path, monkeypatch
) -> None:
    result = _invoke_new_project(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output

    project = tmp_path / "demo"
    ignored_by_git = (project / ".gitignore").read_text(encoding="utf-8").split()
    ignored_by_docker = (project / ".dockerignore").read_text(encoding="utf-8").split()
    # `.env.remote`, `.env.dokploy`, volume snapshots: all hold secrets.
    for name in (".env", ".env.*", ".snapshots/"):
        assert name in ignored_by_git, name
    for name in (".env", ".env.*", ".snapshots/", ".git"):
        assert name in ignored_by_docker, name
    # The `.abi` submodule is what the image installs the framework from.
    assert ".abi" not in ignored_by_docker


# =============================================================================
# NATS is the default; --without-nats keeps the classic in-process project.
# =============================================================================

def _env(tmp_path) -> dict[str, str]:
    lines = (tmp_path / "demo" / ".env").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def _config(tmp_path, name: str = "config.yaml") -> str:
    return (tmp_path / "demo" / name).read_text(encoding="utf-8")


def _uv_add(commands) -> list[str]:
    return next(cmd for cmd in commands if cmd[:2] == ["uv", "add"])


def test_new_project_runs_on_nats_by_default(tmp_path, monkeypatch) -> None:
    commands: list = []
    result = _invoke_new_project(tmp_path, monkeypatch, commands=commands)
    assert result.exit_code == 0, result.output

    for name in ("config.yaml", "config.local.yaml", "config.remote.yaml"):
        assert "\nnats:\n" in _config(tmp_path, name), name
    env = _env(tmp_path)
    assert len(env["NATS_JWT_SECRET"]) >= 32
    assert env["NATS_ABI_PASSWORD"] and env["NATS_MODULE_PASSWORD"]
    assert "naas-abi-sdk[agent]" in _uv_add(commands)
    # No legacy extras: Dagster and RabbitMQ are not installed.
    assert "naas-abi-core[all]" in _uv_add(commands)
    assert "nats-server" in result.output
    # The project's own module holds the default agent the engine loads.
    module = (tmp_path / "demo" / "src" / "demo" / "__init__.py").read_text()
    assert "naas_abi_core" in module
    # Module jobs schedule a NATS project: no Dagster orchestration.
    assert not (tmp_path / "demo" / "src" / "demo" / "orchestrations").exists()
    assert not (tmp_path / "demo" / "docker-compose.override.yml").exists()


def test_new_project_without_nats_is_the_classic_project(tmp_path, monkeypatch) -> None:
    commands: list = []
    result = _invoke_new_project(
        tmp_path, monkeypatch, "--without-nats", commands=commands
    )
    assert result.exit_code == 0, result.output

    for name in ("config.yaml", "config.local.yaml", "config.remote.yaml"):
        assert "\nnats:" not in _config(tmp_path, name), name
    assert 'adapter: "python_queue"' in _config(tmp_path)
    assert "NATS_JWT_SECRET" not in _env(tmp_path)
    assert not any("naas-abi-sdk" in arg for arg in _uv_add(commands))
    assert "nats-server" not in result.output
    # The legacy extras its Dagster and RabbitMQ setup runs on.
    assert "naas-abi-core[all,dagster,rabbitmq]" in _uv_add(commands)
    orchestrations = tmp_path / "demo" / "src" / "demo" / "orchestrations"
    assert (orchestrations / "DemoOrchestration.py").is_file()


def test_a_nats_project_refuses_to_skip_the_submodule(tmp_path, monkeypatch) -> None:
    """naas-abi-proto and naas-abi-sdk are not on PyPI: without the submodule
    the project could not install, so it fails before writing anything."""
    result = _invoke_new_project(tmp_path, monkeypatch, "--without-abi-submodule")

    assert result.exit_code != 0
    assert "--without-nats" in result.output
    assert not (tmp_path / "demo").exists()


def test_a_nats_project_stops_when_the_clone_fails(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    def fake_run(cmd, **_kwargs):
        if "submodule" in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    result = CliRunner().invoke(
        project.new_project,
        ["demo", str(tmp_path), "--domain", "localhost", "--without-local-deploy"],
    )

    assert result.exit_code != 0
    assert "naas-abi-sdk" in result.output
    # The half-made project is removed, so the same command can run again.
    assert not (tmp_path / "demo").exists()


def test_a_config_that_does_not_validate_is_reported_not_raised(
    tmp_path, monkeypatch
) -> None:
    """Without a TTY, a secret the config names but nobody set (OPENROUTER_API_KEY)
    fails the closing `abi config validate`: say what to do, not a traceback."""
    from click.testing import CliRunner

    def fake_run(cmd, **_kwargs):
        if "submodule" in cmd:
            (tmp_path / "demo" / project.ABI_SUBMODULE_PATH / "libs").mkdir(
                parents=True, exist_ok=True
            )
        if "validate" in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(project.subprocess, "run", fake_run)
    monkeypatch.setattr(project.shutil, "which", lambda _cmd: "/usr/bin/git")

    result = CliRunner().invoke(
        project.new_project,
        ["demo", str(tmp_path), "--domain", "localhost", "--without-local-deploy"],
    )

    assert result.exit_code == 1
    assert not isinstance(result.exception, subprocess.CalledProcessError)
    assert str(tmp_path / "demo") in result.output
    assert "abi config validate" in result.output
