import subprocess
from pathlib import Path

import pytest

from naas_abi_cli.cli import bootstrap


def test_find_abi_project_root_from_nested_folder(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_path = project_root / "src" / "pkg"
    nested_path.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["naas-abi-cli"]\n',
        encoding="utf-8",
    )

    resolved_root = bootstrap.find_abi_project_root(nested_path)

    assert resolved_root == project_root


def test_find_abi_project_root_returns_none_for_non_abi_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_path = project_root / "src"
    nested_path.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["requests"]\n',
        encoding="utf-8",
    )

    resolved_root = bootstrap.find_abi_project_root(nested_path)

    assert resolved_root is None


def test_maybe_rerun_in_project_context_skips_when_guard_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(bootstrap.REEXEC_ENV_VAR, "true")

    assert bootstrap.maybe_rerun_in_project_context(["config", "validate"]) is False


def test_maybe_rerun_in_project_context_executes_uv_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    nested_path = project_root / "src" / "feature"
    nested_path.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["naas-abi-core"]\n',
        encoding="utf-8",
    )

    called: dict[str, object] = {}
    info: dict[str, object] = {}

    def _fake_run(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        called["arguments"] = args[0]
        called["cwd"] = kwargs["cwd"]
        called["check"] = kwargs["check"]
        called["env"] = kwargs["env"]

    monkeypatch.delenv(bootstrap.REEXEC_ENV_VAR, raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.setattr(bootstrap.sys, "argv", ["abi"])
    monkeypatch.setattr(bootstrap, "find_abi_project_root", lambda: project_root)
    monkeypatch.setattr(bootstrap.Path, "cwd", lambda: nested_path)
    monkeypatch.setattr(bootstrap, "_get_system_cli_version", lambda: "1.0.0")
    monkeypatch.setattr(bootstrap, "_get_project_cli_version", lambda _: "1.1.0")
    monkeypatch.setattr(
        bootstrap,
        "_show_rerun_info",
        lambda root, system, project: info.update(
            {"root": root, "system": system, "project": project}
        ),
    )
    monkeypatch.setattr(bootstrap.subprocess, "run", _fake_run)

    result = bootstrap.maybe_rerun_in_project_context(["module", "list"])

    assert result is True
    assert called["arguments"] == [
        "uv",
        "run",
        "--project",
        str(project_root),
        "--active",
        "abi",
        "module",
        "list",
    ]
    assert called["cwd"] == str(nested_path)
    assert called["check"] is True
    env = called["env"]
    assert isinstance(env, dict)
    assert env[bootstrap.REEXEC_ENV_VAR] == "true"
    assert info == {"root": project_root, "system": "1.0.0", "project": "1.1.0"}


def test_maybe_rerun_in_project_context_falls_back_when_uv_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["naas-abi-cli"]\n',
        encoding="utf-8",
    )

    def _missing_uv(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise FileNotFoundError("uv not found")

    monkeypatch.delenv(bootstrap.REEXEC_ENV_VAR, raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.setattr(bootstrap.sys, "argv", ["abi"])
    monkeypatch.setattr(bootstrap, "find_abi_project_root", lambda: project_root)
    monkeypatch.setattr(bootstrap, "_get_system_cli_version", lambda: "1.0.0")
    monkeypatch.setattr(bootstrap, "_get_project_cli_version", lambda _: "1.1.0")
    monkeypatch.setattr(bootstrap, "_show_rerun_info", lambda *_: None)
    monkeypatch.setattr(bootstrap.subprocess, "run", _missing_uv)

    assert bootstrap.maybe_rerun_in_project_context(["config", "validate"]) is False


def test_maybe_rerun_in_project_context_propagates_reexec_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["naas-abi-cli"]\n',
        encoding="utf-8",
    )

    def _failing_uv(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise subprocess.CalledProcessError(returncode=4, cmd=["uv"])

    monkeypatch.delenv(bootstrap.REEXEC_ENV_VAR, raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.setattr(bootstrap.sys, "argv", ["abi"])
    monkeypatch.setattr(bootstrap, "find_abi_project_root", lambda: project_root)
    monkeypatch.setattr(bootstrap, "_get_system_cli_version", lambda: "1.0.0")
    monkeypatch.setattr(bootstrap, "_get_project_cli_version", lambda _: "1.1.0")
    monkeypatch.setattr(bootstrap, "_show_rerun_info", lambda *_: None)
    monkeypatch.setattr(bootstrap.subprocess, "run", _failing_uv)

    with pytest.raises(SystemExit, match="4") as error:
        bootstrap.maybe_rerun_in_project_context(["config", "validate"])

    assert error.value.code == 4
