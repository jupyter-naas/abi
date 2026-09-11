from pathlib import Path

import pytest
from naas_abi.agents.tools import nexus_source_tools as source
from naas_abi.agents.tools.nexus_source_tools import (
    CORE_ROOT,
    PACKAGE_ROOT,
    SourcePathError,
    list_source_dir,
    nexus_source_tools,
    read_source_file,
    resolve_source_path,
    search_source,
)

APPS_SERVICE = "naas_abi/apps/nexus/apps/api/app/services/apps/service.py"


def test_package_root_is_naas_abi() -> None:
    assert PACKAGE_ROOT.name == "naas_abi"
    assert (PACKAGE_ROOT / "agents" / "SlidesAgent.py").is_file()


@pytest.mark.parametrize(
    "raw",
    [
        APPS_SERVICE,
        "libs/naas-abi/" + APPS_SERVICE,
        ".abi/libs/naas-abi/" + APPS_SERVICE,
        "apps/nexus/apps/api/app/services/apps/service.py",
    ],
)
def test_resolve_accepts_repo_and_package_relative_paths(raw: str) -> None:
    assert (
        resolve_source_path(raw)
        == PACKAGE_ROOT / "apps/nexus/apps/api/app/services/apps/service.py"
    )


def test_resolve_maps_naas_abi_core_to_its_own_root() -> None:
    assert CORE_ROOT is not None
    for raw in (
        "naas_abi_core/services/agent/context.py",
        "libs/naas-abi-core/naas_abi_core/services/agent/context.py",
    ):
        assert resolve_source_path(raw) == CORE_ROOT / "services/agent/context.py"


def test_core_paths_display_with_their_prefix() -> None:
    result = read_source_file("naas_abi_core/services/agent/context.py", max_lines=3)
    assert result["path"] == "naas_abi_core/services/agent/context.py"


def test_core_root_cannot_be_escaped() -> None:
    with pytest.raises(SourcePathError):
        resolve_source_path("naas_abi_core/../../../pyproject.toml")


@pytest.mark.parametrize(
    "raw", ["../../../../etc/passwd", "/etc/passwd", "naas_abi/../../pyproject.toml"]
)
def test_resolve_refuses_paths_outside_the_package(raw: str) -> None:
    with pytest.raises(SourcePathError):
        resolve_source_path(raw)


@pytest.mark.parametrize(
    "name", [".env", ".env.local", "server.pem", "tls.key", "id_rsa", "local.sqlite"]
)
def test_resolve_refuses_secret_like_files(name: str) -> None:
    with pytest.raises(SourcePathError):
        resolve_source_path(f"naas_abi/apps/nexus/apps/api/{name}")


def test_env_example_is_readable() -> None:
    assert (
        resolve_source_path("naas_abi/apps/nexus/apps/api/.env.example").name
        == ".env.example"
    )


def test_read_returns_numbered_window_with_display_path() -> None:
    result = read_source_file(APPS_SERVICE, start_line=1, max_lines=5)
    assert result["path"] == APPS_SERVICE
    assert result["start_line"] == 1
    assert result["end_line"] == 5
    assert result["more"] is True
    assert result["content"].splitlines()[0].startswith("    1  ")


def test_read_caps_the_window() -> None:
    result = read_source_file(APPS_SERVICE, max_lines=10_000)
    assert result["end_line"] - result["start_line"] + 1 <= 800


def test_list_hides_generated_dirs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pkg").mkdir()
    root = tmp_path / "pkg"
    (root / "__pycache__").mkdir()
    (root / "src").mkdir()
    (root / "a.py").write_text("x = 1\n")
    (root / ".env").write_text("SECRET=1\n")
    monkeypatch.setattr(source, "PACKAGE_ROOT", root)

    result = list_source_dir("naas_abi")

    assert result["dirs"] == ["src/"]
    assert [f["name"] for f in result["files"]] == ["a.py"]


def test_search_finds_a_route_in_the_apps_adapter() -> None:
    result = search_source(
        r"@router\.patch",
        path="naas_abi/apps/nexus/apps/api/app/services/apps",
        glob="*.py",
    )
    paths = {m["path"] for m in result["matches"]}
    assert (
        "naas_abi/apps/nexus/apps/api/app/services/apps/adapters/primary/"
        "apps__primary_adapter__FastAPI.py"
    ) in paths


def test_search_treats_an_invalid_regex_as_literal() -> None:
    result = search_source(
        "resolve_app_enabled(", path="naas_abi/apps/nexus/apps/api/app/core"
    )
    assert result["matches"]


def test_search_skips_symlinks_that_escape_the_package(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "pkg"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("TOKEN = 'leak'\n")
    (root / "link.py").symlink_to(outside)
    (root / "inside.py").write_text("TOKEN = 'ok'\n")
    monkeypatch.setattr(source, "PACKAGE_ROOT", root)

    result = search_source("TOKEN", path="naas_abi")

    assert [m["path"] for m in result["matches"]] == ["naas_abi/inside.py"]


def test_missing_web_sources_are_reported_as_not_shipped(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "pkg"
    (root / "apps/nexus/apps/api").mkdir(parents=True)
    monkeypatch.setattr(source, "PACKAGE_ROOT", root)

    result = read_source_file("naas_abi/apps/nexus/apps/web/src/lib/feature-access.ts")

    assert "not shipped" in result["error"]


def test_tools_turn_refusals_into_errors_not_exceptions() -> None:
    tools = {t.name: t for t in nexus_source_tools()}
    assert set(tools) == {
        "list_nexus_source",
        "read_nexus_source",
        "search_nexus_source",
    }
    out = tools["read_nexus_source"].invoke({"path": "/etc/passwd"})
    assert "outside naas_abi and naas_abi_core" in out["error"]
