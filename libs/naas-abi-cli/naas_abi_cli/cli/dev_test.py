"""Tests for the host split in `abi dev`.

The browser is not necessarily on the machine running the services — on WSL it
is a Windows app talking to a Linux VM, where `127.0.0.1` in the address bar is
Windows' own loopback and reaches nothing. So browser-facing URLs speak
`localhost` (the name WSL forwarding publishes), while binds and probes stay on
the literal. These two must not drift back together.
"""

import importlib
from typing import TYPE_CHECKING

import click
import pytest

# `naas_abi_cli.cli` re-exports the click Group as `dev`, which shadows the
# module of the same name — import the module explicitly.
dev = importlib.import_module("naas_abi_cli.cli.dev")

if TYPE_CHECKING:
    # The importlib call above is opaque to mypy, so `dev.ServiceSpec` reads as
    # an undefined name. Pull the type in statically instead; this branch never
    # executes, so the runtime shadowing described above still does not bite.
    from naas_abi_cli.cli.dev import ServiceSpec


PORTS = {"oxigraph": 7878, "api": 9879, "dagster": 11000, "nexus-web": 12000}


def _spec(name: str, port: int) -> "ServiceSpec":
    return dev._service_spec(name, port)


# =============================================================================
# Browser-facing URLs
# =============================================================================

def test_service_url_uses_localhost() -> None:
    assert dev._service_url(12000) == "http://localhost:12000"


def test_service_url_never_emits_the_ipv4_literal() -> None:
    for port in PORTS.values():
        assert "127.0.0.1" not in dev._service_url(port)


def test_api_env_points_the_frontend_at_localhost(monkeypatch) -> None:
    """FRONTEND_URL builds magic links — it must match the origin the user is on."""
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env, cmd=cmd) or 1234,
    )

    dev._launch_api(_spec("api", PORTS["api"]), PORTS)

    env = captured["env"]
    assert env["FRONTEND_URL"] == f"http://localhost:{PORTS['nexus-web']}"
    assert env["PUBLIC_WEB_HOST"] == f"localhost:{PORTS['nexus-web']}"


def test_api_allows_both_loopback_origins_for_cors(monkeypatch) -> None:
    """We hand out localhost, but a hand-typed 127.0.0.1 should still work."""
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
    )

    dev._launch_api(_spec("api", PORTS["api"]), PORTS)

    origins = captured["env"]["ABI_CORS_EXTRA_ORIGINS"].split(",")
    nexus_port = PORTS["nexus-web"]
    assert f"http://localhost:{nexus_port}" in origins
    assert f"http://127.0.0.1:{nexus_port}" in origins


def test_api_preserves_preexisting_cors_origins(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setenv("ABI_CORS_EXTRA_ORIGINS", "https://example.test")
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
    )

    dev._launch_api(_spec("api", PORTS["api"]), PORTS)

    assert "https://example.test" in captured["env"]["ABI_CORS_EXTRA_ORIGINS"].split(",")


def test_api_env_defaults_abi_api_key(monkeypatch) -> None:
    """Missing ABI_API_KEY must not leave the API child unauthenticated."""
    captured: dict = {}
    monkeypatch.delenv("ABI_API_KEY", raising=False)
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
    )

    dev._launch_api(_spec("api", PORTS["api"]), PORTS)

    assert captured["env"]["ABI_API_KEY"] == "abi"


def test_api_env_preserves_explicit_abi_api_key(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setenv("ABI_API_KEY", "custom-dev-key")
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
    )

    dev._launch_api(_spec("api", PORTS["api"]), PORTS)

    assert captured["env"]["ABI_API_KEY"] == "custom-dev-key"


def test_ensure_default_api_key_writes_env_when_missing(
    monkeypatch, tmp_path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=1\n")
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    monkeypatch.delenv("ABI_API_KEY", raising=False)

    key = dev._ensure_default_api_key_env()

    assert key == "abi"
    assert "ABI_API_KEY=abi" in env_file.read_text()
    assert "OTHER=1" in env_file.read_text()


def test_ensure_default_api_key_does_not_overwrite_env_file(
    monkeypatch, tmp_path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ABI_API_KEY=keep-me\n")
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    monkeypatch.delenv("ABI_API_KEY", raising=False)

    key = dev._ensure_default_api_key_env()

    assert key == "keep-me"
    assert env_file.read_text().count("ABI_API_KEY=") == 1
    assert "ABI_API_KEY=keep-me" in env_file.read_text()


# =============================================================================
# Bind / probe targets stay on the literal
# =============================================================================

def test_oxigraph_binds_the_ipv4_literal(monkeypatch) -> None:
    """Server-to-server hop: no DNS, no ::1 ambiguity."""
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(cmd=cmd) or 1234,
    )

    dev._launch_oxigraph(_spec("oxigraph", PORTS["oxigraph"]))

    cmd = captured["cmd"]
    assert f"127.0.0.1:{PORTS['oxigraph']}" in cmd


def test_oxigraph_url_is_not_browser_facing() -> None:
    assert dev._oxigraph_url(PORTS) == f"http://127.0.0.1:{PORTS['oxigraph']}"


def test_dagster_binds_the_ipv4_literal(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(cmd=cmd) or 1234,
    )

    dev._launch_dagster(_spec("dagster", PORTS["dagster"]), PORTS)

    cmd = captured["cmd"]
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"


def test_health_probe_targets_the_literal(monkeypatch) -> None:
    """`localhost` may resolve to ::1 and report a live IPv4 service as down."""
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        raise ConnectionError("probe stub")

    monkeypatch.setattr(dev.urllib.request, "urlopen", fake_urlopen)

    assert dev._http_ready(9879, path="/health") is False
    assert seen == ["http://127.0.0.1:9879/health"]


# =============================================================================
# Escape hatches for WSL setups where forwarding misbehaves
# =============================================================================

def _reloaded(monkeypatch, **env):
    """Re-import dev with `env` applied, since hosts are resolved at import."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(dev)


def test_browser_host_is_overridable(monkeypatch) -> None:
    """WSL mirrored-mode users may need to point at the VM address directly."""
    reloaded = _reloaded(monkeypatch, ABI_DEV_BROWSER_HOST="172.24.80.1")
    try:
        assert reloaded._service_url(12000) == "http://172.24.80.1:12000"
    finally:
        monkeypatch.undo()
        importlib.reload(dev)


def test_bind_host_is_overridable(monkeypatch) -> None:
    # The literal is the subject of the assertion, not a bind: these tests
    # check that the override is honoured and that probes stay on loopback.
    reloaded = _reloaded(monkeypatch, ABI_DEV_BIND_HOST="0.0.0.0")  # nosec B104
    try:
        assert reloaded.BIND_HOST == "0.0.0.0"  # nosec B104
    finally:
        monkeypatch.undo()
        importlib.reload(dev)


def test_wildcard_bind_still_probes_loopback(monkeypatch) -> None:
    """0.0.0.0 is an accept-any address, not something you can dial."""
    reloaded = _reloaded(monkeypatch, ABI_DEV_BIND_HOST="0.0.0.0")  # nosec B104
    try:
        assert reloaded.PROBE_HOST == "127.0.0.1"
        assert reloaded._oxigraph_url(PORTS) == f"http://127.0.0.1:{PORTS['oxigraph']}"
    finally:
        monkeypatch.undo()
        importlib.reload(dev)


def test_custom_browser_host_is_allowed_by_cors(monkeypatch) -> None:
    """A custom host that isn't in the CORS list is a silent browser failure."""
    reloaded = _reloaded(monkeypatch, ABI_DEV_BROWSER_HOST="172.24.80.1")
    try:
        captured: dict = {}
        monkeypatch.setattr(
            reloaded,
            "_spawn",
            lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
        )
        reloaded._launch_api(
            reloaded._service_spec("api", PORTS["api"]), PORTS
        )

        origins = captured["env"]["ABI_CORS_EXTRA_ORIGINS"].split(",")
        nexus_port = PORTS["nexus-web"]
        assert f"http://172.24.80.1:{nexus_port}" in origins
        # The defaults must survive alongside the override.
        assert f"http://localhost:{nexus_port}" in origins
        assert f"http://127.0.0.1:{nexus_port}" in origins
    finally:
        monkeypatch.undo()
        importlib.reload(dev)


# =============================================================================
# Project-root resolution
#
# Nothing chdir's to the project root before `abi dev` runs, so the working
# directory is whatever the user typed from. Resolving the root from cwd rather
# than trusting it is what keeps `.abi/dev`, `storage/` and `.dagster/` in one
# place and stops services launching against an env with no `naas_abi_core`.
# =============================================================================

PYPROJECT = """\
[project]
name = "my-ai"
dependencies = ["naas-abi-core[all]>=2.21.1"]
"""


@pytest.fixture(autouse=True)
def _clear_project_root_cache():
    """`_project_root` memoizes; a stale entry would leak across tests."""
    cache_clear = getattr(dev._project_root, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()
    yield
    cache_clear = getattr(dev._project_root, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()


def _make_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    return tmp_path.resolve()


def test_project_root_resolves_from_the_project_root(monkeypatch, tmp_path) -> None:
    root = _make_project(tmp_path)
    monkeypatch.chdir(root)

    assert dev._project_root() == root


def test_project_root_resolves_upward_from_a_subdirectory(
    monkeypatch, tmp_path
) -> None:
    """The quiet failure: cwd is a real project subdir, so nothing looks wrong.

    Trusting cwd here scatters dev state into `src/` while the bootstrap has
    already re-execed against the *project* venv — it appears to work.
    """
    root = _make_project(tmp_path)
    nested = root / "src" / "my_ai" / "agents"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert dev._project_root() == root


def test_dev_artifacts_stay_in_the_project_root(monkeypatch, tmp_path) -> None:
    """`.abi/dev` must not follow the user's cwd down into the project."""
    root = _make_project(tmp_path)
    nested = root / "src"
    nested.mkdir()
    monkeypatch.chdir(nested)

    assert dev._dev_dir() == root / dev.DEV_DIR_NAME
    assert dev._instance_path() == root / dev.DEV_DIR_NAME / dev.INSTANCE_FILENAME
    assert nested not in dev._instance_path().parents


def test_project_root_refuses_to_run_outside_a_project(monkeypatch, tmp_path) -> None:
    """`abi new project` scaffolds into a subdir, so this is the default slip."""
    outside = tmp_path / "not-a-project"
    outside.mkdir()
    monkeypatch.chdir(outside)

    with pytest.raises(click.ClickException) as excinfo:
        dev._project_root()

    message = str(excinfo.value)
    # The message has to name the fix, not just the symptom: the observed
    # failure was a misleading "oxigraph did not become ready" 15s later.
    assert "No ABI project found" in message
    assert "cd <project-name>" in message


def test_ports_are_stable_regardless_of_invocation_directory(
    monkeypatch, tmp_path
) -> None:
    """Offsets hash the project path — a cwd-derived root reallocates ports."""
    root = _make_project(tmp_path)
    nested = root / "src"
    nested.mkdir()

    monkeypatch.chdir(root)
    from_root = dev._compute_offset(dev._project_root())

    dev._project_root.cache_clear()
    monkeypatch.chdir(nested)
    from_nested = dev._compute_offset(dev._project_root())

    assert from_root == from_nested
