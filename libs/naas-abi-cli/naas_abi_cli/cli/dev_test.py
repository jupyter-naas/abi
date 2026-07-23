"""Tests for the host split in `abi dev`.

The browser is not necessarily on the machine running the services — on WSL it
is a Windows app talking to a Linux VM, where `127.0.0.1` in the address bar is
Windows' own loopback and reaches nothing. So browser-facing URLs speak
`localhost` (the name WSL forwarding publishes), while binds and probes stay on
the literal. These two must not drift back together.
"""

import importlib
from typing import TYPE_CHECKING

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

    def fake_urlopen(url, timeout):  # noqa: ANN001
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
    reloaded = _reloaded(monkeypatch, ABI_DEV_BIND_HOST="0.0.0.0")
    try:
        assert reloaded.BIND_HOST == "0.0.0.0"
    finally:
        monkeypatch.undo()
        importlib.reload(dev)


def test_wildcard_bind_still_probes_loopback(monkeypatch) -> None:
    """0.0.0.0 is an accept-any address, not something you can dial."""
    reloaded = _reloaded(monkeypatch, ABI_DEV_BIND_HOST="0.0.0.0")
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
