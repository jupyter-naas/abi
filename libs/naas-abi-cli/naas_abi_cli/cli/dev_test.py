"""Tests for the host split in `abi dev`.

The browser is not necessarily on the machine running the services — on WSL it
is a Windows app talking to a Linux VM, where `127.0.0.1` in the address bar is
Windows' own loopback and reaches nothing. So browser-facing URLs speak
`localhost` (the name WSL forwarding publishes), while binds and probes stay on
the literal. These two must not drift back together.
"""

import importlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

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


def test_api_env_defaults_abi_api_key(monkeypatch, tmp_path) -> None:
    """Missing ABI_API_KEY must not leave the API child unauthenticated."""
    captured: dict = {}
    monkeypatch.delenv("ABI_API_KEY", raising=False)
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
    )

    dev._launch_api(_spec("api", PORTS["api"]), PORTS)

    key = captured["env"]["ABI_API_KEY"]
    assert key and key != "abi"
    assert f"ABI_API_KEY={key}" in (tmp_path / ".env").read_text()


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

    assert key != "abi" and len(key) >= 32
    assert f"ABI_API_KEY={key}" in env_file.read_text()
    assert "OTHER=1" in env_file.read_text()


def test_ensure_default_admin_env_generates_a_password(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD=admin\n")
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)

    email, password = dev._ensure_default_admin_env()

    assert email == "admin@example.com"
    assert password != "admin" and len(password) >= 24
    assert f"NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD={password}" in env_file.read_text()


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


# =============================================================================
# Boot visibility
#
# `Engine.load()` runs behind the api's lazy app factory and narrates itself
# only at DEBUG. At the library default (WARNING) a slow boot and a wedged one
# look identical from the log pane, so `abi dev up` raises the level itself.
# =============================================================================

def _captured_env(monkeypatch, launch, **kwargs) -> dict:
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(env=env) or 1234,
    )
    name = "api" if launch is dev._launch_api else "dagster"
    launch(_spec(name, PORTS[name]), PORTS, **kwargs)
    return captured["env"]


def test_api_and_dagster_default_to_debug(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    for launch in (dev._launch_api, dev._launch_dagster):
        assert _captured_env(monkeypatch, launch)["LOG_LEVEL"] == "DEBUG"


def test_explicit_log_level_wins(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    for launch in (dev._launch_api, dev._launch_dagster):
        env = _captured_env(monkeypatch, launch, log_level="info")
        assert env["LOG_LEVEL"] == "INFO"


def test_inherited_log_level_is_honoured(monkeypatch) -> None:
    """The new flag adds a knob; it must not take the existing one away."""
    monkeypatch.setenv("LOG_LEVEL", "warning")

    for launch in (dev._launch_api, dev._launch_dagster):
        assert _captured_env(monkeypatch, launch)["LOG_LEVEL"] == "WARNING"


def test_dagster_own_log_level_is_left_alone(monkeypatch) -> None:
    """Our loguru sink is LOG_LEVEL; dagster's daemon flag would only add noise."""
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(cmd=cmd) or 1234,
    )

    dev._launch_dagster(_spec("dagster", PORTS["dagster"]), PORTS)

    assert "--log-level" not in captured["cmd"]


# =============================================================================
# Ontology bootstrap ownership
#
# api and dagster share this stack's single oxigraph. The bootstrap is tens of
# thousands of triples, so having both apply it doubles the work and makes the
# two processes contend for the same writes.
# =============================================================================

def test_dagster_defers_the_ontology_bootstrap_to_the_api(monkeypatch) -> None:
    env = _captured_env(monkeypatch, dev._launch_dagster)

    assert env["ABI_SKIP_ONTOLOGY_LOADING"] == "true"


def test_dagster_bootstraps_when_the_api_is_not_running(monkeypatch) -> None:
    """Nothing else would load the schema, so the store would stay empty."""
    env = _captured_env(
        monkeypatch, dev._launch_dagster, skip_ontology_loading=False
    )

    assert "ABI_SKIP_ONTOLOGY_LOADING" not in env


def test_api_always_owns_the_bootstrap(monkeypatch) -> None:
    assert "ABI_SKIP_ONTOLOGY_LOADING" not in _captured_env(
        monkeypatch, dev._launch_api
    )


def test_start_service_gives_dagster_the_bootstrap_without_an_api(
    monkeypatch, tmp_path
) -> None:
    """`abi dev up --service dagster` must not leave the schema unloaded."""
    captured: dict = {}
    monkeypatch.setattr(dev, "_read_pid", lambda spec: None)
    monkeypatch.setattr(dev, "_find_free_port", lambda service, preferred: preferred)
    monkeypatch.setattr(
        dev,
        "_launch_dagster",
        lambda spec, ports, log_level=None, skip_ontology_loading=True: captured.update(
            skip=skip_ontology_loading
        )
        or 1234,
    )
    monkeypatch.setattr(dev, "_pid_path", lambda spec: tmp_path / f"{spec.name}.pid")

    dev._start_service("dagster", dict(PORTS), None, ["dagster"])
    assert captured["skip"] is False

    dev._start_service("dagster", dict(PORTS), None, ["api", "dagster"])
    assert captured["skip"] is True

    # No explicit selection == the default `abi dev up`, which starts the api.
    dev._start_service("dagster", dict(PORTS), None, None)
    assert captured["skip"] is True


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
# nats — opt-in service (docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md)
#
# Unlike oxigraph (embedded via pyoxigraph), nats-server is a real external
# binary this shells out to, and it must never start unless explicitly
# selected — config.yaml's bus_adapter still defaults to "python_queue".
# =============================================================================

def test_nats_is_available_but_not_default() -> None:
    assert "nats" not in dev.ALL_SERVICES
    assert "nats" in dev.OPTIONAL_SERVICES
    assert "nats" in dev.KNOWN_SERVICES


def test_validate_services_default_excludes_nats() -> None:
    assert "nats" not in dev._validate_services(())


def test_validate_services_accepts_nats_when_explicit() -> None:
    # NATS before the api: in NATS mode the engine connects to it while booting.
    assert dev._validate_services(("api", "nats")) == ["nats", "api"]


def test_nats_monitor_port_is_derived_from_the_client_port() -> None:
    assert dev._nats_monitor_port(13000) == 13000 + dev.NATS_MONITOR_PORT_OFFSET


def test_ready_probe_port_targets_the_monitor_port_for_nats() -> None:
    assert dev._ready_probe_port("nats", 13000) == dev._nats_monitor_port(13000)


def test_ready_probe_port_is_a_no_op_for_every_other_service() -> None:
    for name in dev.ALL_SERVICES:
        assert dev._ready_probe_port(name, 9999) == 9999


def test_nats_binds_the_ipv4_literal_and_both_ports(monkeypatch, tmp_path) -> None:
    """Server-to-server hop: no DNS, no ::1 ambiguity — same discipline as oxigraph."""
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(cmd=cmd) or 1234,
    )
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/nats-server")
    # The launcher writes storage/nats/nats.conf and the passwords in .env.
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)

    client_port = 13380
    dev._launch_nats(_spec("nats", client_port))

    cmd = captured["cmd"]
    assert cmd[cmd.index("-a") + 1] == "127.0.0.1"
    assert cmd[cmd.index("-p") + 1] == str(client_port)
    assert cmd[cmd.index("-m") + 1] == str(dev._nats_monitor_port(client_port))
    assert "-js" in cmd


def test_nats_is_started_with_a_config_file_raising_max_payload_to_8mb(
    monkeypatch, tmp_path
) -> None:
    """nats-server's 1 MB default refuses any single RPC reply bigger than
    that (a 2 MB get_object, a whole-store triple_store.get). There is no CLI
    flag for it, only the config-file key, so the launcher must write one and
    pass it with -c. 8 MB is the ceiling NATS recommends; anything bigger
    should stream or hand back a storage reference, not grow this."""
    captured: dict = {}
    monkeypatch.setattr(
        dev,
        "_spawn",
        lambda spec, cmd, cwd, env: captured.update(cmd=cmd) or 1234,
    )
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/nats-server")
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)

    dev._launch_nats(_spec("nats", 13380))

    cmd = captured["cmd"]
    config_path = Path(cmd[cmd.index("-c") + 1])
    assert config_path == tmp_path / "storage" / "nats" / "nats.conf"
    assert f"max_payload: {dev.NATS_MAX_PAYLOAD}" in config_path.read_text()
    assert dev.NATS_MAX_PAYLOAD == "8MB"
    # Config + flags coexist: flags still carry ports/bind/JetStream.
    assert "-js" in cmd and "-p" in cmd and "-m" in cmd


def test_nats_config_file_is_rewritten_on_every_launch(monkeypatch, tmp_path) -> None:
    """A stale hand-edited file must not silently pin an old limit."""
    monkeypatch.setattr(dev, "_spawn", lambda spec, cmd, cwd, env: 1234)
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/nats-server")
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    config_path = tmp_path / "storage" / "nats" / "nats.conf"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("max_payload: 1MB\n")

    dev._launch_nats(_spec("nats", 13380))

    assert "max_payload: 8MB" in config_path.read_text()
    assert "1MB" not in config_path.read_text()


def _env_value(path: Path, key: str) -> str:
    (value,) = [
        line.split("=", 1)[1]
        for line in path.read_text().splitlines()
        if line.startswith(f"{key}=")
    ]
    return value


def test_the_dev_broker_has_a_user_for_the_engine_and_one_for_modules(
    monkeypatch, tmp_path
) -> None:
    """Only clients with a password get in, as in the Docker stack."""
    captured: dict = {}
    monkeypatch.setattr(
        dev, "_spawn", lambda spec, cmd, cwd, env: captured.update(cmd=cmd) or 1234
    )
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/nats-server")
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)

    dev._launch_nats(_spec("nats", 13380))

    config_path = Path(captured["cmd"][captured["cmd"].index("-c") + 1])
    config = config_path.read_text()
    for user, key in (("abi", "NATS_ABI_PASSWORD"), ("module", "NATS_MODULE_PASSWORD")):
        password = _env_value(tmp_path / ".env", key)
        assert len(password) >= 32
        assert f'{{ user: "{user}", password: "{password}" }}' in config
    assert config_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)
def test_the_dev_broker_refuses_a_client_without_a_password(tmp_path) -> None:
    import asyncio
    import socket
    import subprocess
    import time

    import nats
    from nats.errors import Error as NATSError

    passwords = {"NATS_ABI_PASSWORD": "nats-abi-pw", "NATS_MODULE_PASSWORD": "nats-module-pw"}
    config = tmp_path / "nats.conf"
    config.write_text(dev._nats_server_config(passwords))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [str(shutil.which("nats-server")), "-c", str(config), "-a", "127.0.0.1", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    async def connect(login: str):
        return await nats.connect(
            f"nats://{login}127.0.0.1:{port}", allow_reconnect=False, connect_timeout=2
        )

    async def scenario() -> None:
        for login in ("", "abi:wrong@", "module:nats-abi-pw@"):
            with pytest.raises(NATSError, match="Authorization Violation"):
                await connect(login)
        for login in ("abi:nats-abi-pw@", "module:nats-module-pw@"):
            await (await connect(login)).close()

    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                break
            except OSError:
                assert server.poll() is None, "nats-server refused the dev nats.conf"
                assert time.monotonic() < deadline
                time.sleep(0.05)
        asyncio.run(scenario())
    finally:
        server.terminate()
        server.wait(timeout=5)


def test_nats_raises_a_helpful_error_when_the_binary_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(dev.shutil, "which", lambda name: None)

    with pytest.raises(dev.click.ClickException, match="nats-server.*PATH"):
        dev._launch_nats(_spec("nats", 13380))


# =============================================================================
# `abi dev up --with-nats`: the engine runs in NATS mode against the dev broker
# =============================================================================

def test_with_nats_starts_nats_and_leaves_dagster_out() -> None:
    assert dev._services_for((), with_nats=True) == ["oxigraph", "nats", "api", "nexus-web"]
    assert dev._services_for((), with_nats=False) == list(dev.ALL_SERVICES)


def test_with_nats_adds_nats_to_an_explicit_selection() -> None:
    assert dev._services_for(("api",), with_nats=True) == ["nats", "api"]
    assert dev._services_for(("api", "dagster"), with_nats=True) == ["nats", "api", "dagster"]


def test_the_nats_overlay_points_the_engine_at_the_dev_broker(monkeypatch, tmp_path) -> None:
    import yaml

    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path / "my project.v2")
    monkeypatch.setattr(dev, "_dev_dir", lambda: tmp_path / "dev")

    path = dev._write_dev_overlay(
        {"nats": 13042}, nats_secret="s" * 48, nats_password="nats-engine-pw"
    )

    nats = yaml.safe_load(path.read_text())["nats"]
    # The engine logs in as the broker user `abi`.
    assert nats["nats_url"] == "nats://abi:nats-engine-pw@127.0.0.1:13042"
    assert nats["jwt_secret"] == "s" * 48
    assert nats["monitoring_url"] == f"http://127.0.0.1:{dev._nats_monitor_port(13042)}"
    assert nats["discovery"] == {"project": "my-project-v2"}
    bus = yaml.safe_load(path.read_text())["services"]["bus"]["bus_adapter"]
    assert bus == {
        "adapter": "nats_jetstream",
        "config": {"nats_url": "nats://abi:nats-engine-pw@127.0.0.1:13042"},
    }
    assert path.stat().st_mode & 0o777 == 0o600


def test_the_api_reads_the_overlay_only_in_nats_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ABI_CONFIG_OVERLAY", raising=False)
    monkeypatch.setenv("ABI_API_KEY", "test-key")  # never touch a real .env
    overlay = tmp_path / "nats.overlay.yaml"

    with_overlay = _captured_env(monkeypatch, dev._launch_api, config_overlay=overlay)
    without = _captured_env(monkeypatch, dev._launch_api)

    assert with_overlay["ABI_CONFIG_OVERLAY"] == str(overlay)
    assert "ABI_CONFIG_OVERLAY" not in without


def test_dev_down_stops_nats_too_by_default() -> None:
    assert dev._services_to_stop(()) == ["nexus-web", "dagster", "api", "jaeger", "nats", "oxigraph"]
    assert dev._services_to_stop(("api",)) == ["api"]


# =============================================================================
# Stopping waits for the port: a restart must find its port free, not drift
# =============================================================================

def _stoppable(monkeypatch, tmp_path, *, alive, busy):
    signals: list = []
    monkeypatch.setattr(dev, "_read_pid", lambda spec: 4242)
    monkeypatch.setattr(dev, "_pid_path", lambda spec: tmp_path / f"{spec.name}.pid")
    monkeypatch.setattr(dev.os, "getpgid", lambda pid: 4242)
    monkeypatch.setattr(dev.os, "killpg", lambda pgid, sig: signals.append(sig))
    monkeypatch.setattr(dev.time, "sleep", lambda s: None)
    monkeypatch.setattr(dev, "_pid_alive", lambda pid: next(alive))
    monkeypatch.setattr(dev, "_port_in_use", lambda port: next(busy))
    return signals


def test_stop_waits_until_the_port_is_released(monkeypatch, tmp_path) -> None:
    import itertools

    # The parent exits at once; a child keeps the port for two more polls.
    signals = _stoppable(
        monkeypatch,
        tmp_path,
        alive=itertools.chain([True], itertools.repeat(False)),
        busy=itertools.chain([True, True], itertools.repeat(False)),
    )

    dev._stop_service("api", 10014)

    assert signals == [dev.signal.SIGTERM]


def test_stop_kills_the_group_when_a_child_keeps_the_port(monkeypatch, tmp_path) -> None:
    import itertools

    clock = itertools.count(0, 1.0)
    monkeypatch.setattr(dev.time, "monotonic", lambda: next(clock))
    # The leader exits on SIGTERM; a child holds the port past the deadline.
    signals = _stoppable(
        monkeypatch,
        tmp_path,
        alive=itertools.chain([True], itertools.repeat(False)),
        busy=itertools.repeat(True),
    )

    dev._stop_service("api", 10014)

    assert signals == [dev.signal.SIGTERM, dev.signal.SIGKILL]


def test_a_port_still_being_released_is_waited_for_not_abandoned(monkeypatch) -> None:
    import itertools

    busy = itertools.chain([True, True], itertools.repeat(False))
    monkeypatch.setattr(dev, "_port_in_use", lambda port: next(busy))
    monkeypatch.setattr(dev.time, "sleep", lambda s: None)

    assert dev._find_free_port("api", 10015) == 10015


def test_a_port_that_stays_busy_moves_the_service(monkeypatch) -> None:
    import itertools

    clock = itertools.count(0, 1.0)
    monkeypatch.setattr(dev.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(dev.time, "sleep", lambda s: None)
    monkeypatch.setattr(dev, "_port_in_use", lambda port: port == 10015)

    assert dev._find_free_port("api", 10015) == 10016


def test_a_port_with_only_closed_connections_left_is_free() -> None:
    """Connections the old server closed linger in TIME_WAIT on its port; servers
    bind with SO_REUSEADDR and can take it, so the probe must not call it busy."""
    import socket

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]
    assert dev._port_in_use(port) is True  # really listening

    client = socket.create_connection(("127.0.0.1", port))
    accepted, _ = server.accept()
    accepted.close()  # the server side closes first: TIME_WAIT on `port`
    client.close()
    server.close()

    assert dev._port_in_use(port) is False



# =============================================================================
# `abi dev up --with-tracing`: a native Jaeger and the engine exporting to it
# =============================================================================

def test_tracing_starts_jaeger_before_the_api() -> None:
    assert dev._services_for((), with_nats=True, with_tracing=True) == [
        "oxigraph", "nats", "jaeger", "api", "nexus-web",
    ]
    assert dev._services_for((), with_nats=False, with_tracing=True) == [
        "oxigraph", "jaeger", "api", "dagster", "nexus-web",
    ]
    assert "jaeger" not in dev._services_for((), with_nats=True)
    assert "jaeger" in dev.OPTIONAL_SERVICES


def test_jaeger_ports_are_derived_from_its_query_port() -> None:
    assert dev._jaeger_ports(15042) == {"query": 15042, "otlp": 16042, "grpc": 17042}


def test_jaeger_runs_from_a_generated_config_on_its_dev_ports(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/jaeger")
    monkeypatch.setattr(
        dev, "_spawn", lambda spec, cmd, cwd, env: captured.update(cmd=cmd, env=env) or 1234
    )

    dev._launch_jaeger(_spec("jaeger", 15042))

    cmd = captured["cmd"]
    config = Path(cmd[cmd.index("--config") + 1]).read_text()
    assert "endpoint: 127.0.0.1:15042" in config  # query API + UI
    assert "endpoint: 127.0.0.1:16042" in config  # OTLP/HTTP in
    assert "endpoint: 127.0.0.1:17042" in config  # query gRPC
    assert captured["env"]["OTEL_TRACES_EXPORTER"] == "none"  # no self-tracing


def test_jaeger_raises_a_helpful_error_when_the_binary_is_missing(monkeypatch) -> None:
    import click

    monkeypatch.setattr(dev.shutil, "which", lambda name: None)
    with pytest.raises(click.ClickException, match="github.com/jaegertracing/jaeger/releases"):
        dev._launch_jaeger(_spec("jaeger", 15042))


def test_the_overlay_turns_tracing_on_when_asked(monkeypatch, tmp_path) -> None:
    import yaml

    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path / "zen")
    monkeypatch.setattr(dev, "_dev_dir", lambda: tmp_path / "dev")

    path = dev._write_dev_overlay(
        {"nats": 13042, "jaeger": 15042}, nats_secret="s" * 48, nats_password="pw", tracing=True
    )

    overlay = yaml.safe_load(path.read_text())
    assert overlay["telemetry"] == {
        "enabled": True,
        "otlp_endpoint": "http://127.0.0.1:16042",
        "service_name": "zen-engine",
        "ui_url": "http://localhost:15042",
        "query_url": "http://127.0.0.1:15042",
    }
    assert overlay["nats"]["nats_url"] == "nats://abi:pw@127.0.0.1:13042"
    assert path.name == "dev.overlay.yaml"


def test_tracing_without_nats_has_no_nats_block(monkeypatch, tmp_path) -> None:
    import yaml

    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path / "zen")
    monkeypatch.setattr(dev, "_dev_dir", lambda: tmp_path / "dev")

    overlay = yaml.safe_load(
        dev._write_dev_overlay({"jaeger": 15042}, nats_secret=None, tracing=True).read_text()
    )

    assert set(overlay) == {"telemetry"}


# =============================================================================
# dev.modules: SDK modules `abi dev up --with-nats` runs next to the engine
# =============================================================================

def _modules(*names: str) -> dict:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
        DevModuleConfiguration,
    )

    return {
        name: DevModuleConfiguration(name=name, module="probe", args=[name])
        for name in names
    }


@pytest.fixture
def stack(monkeypatch, tmp_path):
    """`abi dev up/down` over fakes, recording what starts and stops in order."""
    calls: list[tuple[str, str]] = []
    ports = dict(dev.SERVICE_PORT_BASES)
    (tmp_path / "instance.json").write_text("{}")
    monkeypatch.setattr(dev, "_dev_modules", lambda strict=True: _modules("researcher", "orchestrator"))
    monkeypatch.setattr(dev, "_load_or_create_instance", lambda: {"ports": ports})
    monkeypatch.setattr(dev, "_instance_path", lambda: tmp_path / "instance.json")
    monkeypatch.setattr(dev, "_dev_dir", lambda: tmp_path)
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(dev, "_ensure_storage_layout", lambda: None)
    monkeypatch.setattr(dev, "_ensure_default_admin_env", lambda: ("admin@example.com", "pw"))
    monkeypatch.setattr(dev, "_ensure_default_api_key_env", lambda: "key")
    monkeypatch.setattr(dev, "ensure_nats_secret", lambda path: "s" * 48)
    monkeypatch.setattr(dev, "_wait_until_ready", lambda *a, **k: True)

    def start_service(name, ports, log_level=None, selected=None, config_overlay=None):
        calls.append(("start", name))
        return dev._service_spec(name, ports[name])

    def start_module(module, overlay):
        assert overlay["nats"]["jwt_secret"] == "s" * 48
        calls.append(("start", module.name))
        return dev._module_spec(module.name)

    monkeypatch.setattr(dev, "_start_service", start_service)
    monkeypatch.setattr(dev, "_start_module", start_module)
    monkeypatch.setattr(dev, "_stop_service", lambda name, port, force=False: calls.append(("stop", name)))
    monkeypatch.setattr(dev, "_stop_module", lambda name, force=False: calls.append(("stop", name)))
    return calls


def _abi(*args: str):
    from click.testing import CliRunner

    return CliRunner().invoke(dev.dev, list(args))


def test_with_nats_starts_the_dev_modules_after_the_stack(stack) -> None:
    result = _abi("up", "--with-nats", "-d")

    assert result.exit_code == 0, result.output
    assert [name for _, name in stack] == [
        "oxigraph", "nats", "api", "nexus-web", "researcher", "orchestrator",
    ]


def test_dev_modules_need_nats(stack) -> None:
    assert _abi("up", "-d").exit_code == 0
    assert ("start", "researcher") not in stack


def test_selecting_services_leaves_the_modules_alone(stack) -> None:
    assert _abi("up", "--with-nats", "--service", "api", "-d").exit_code == 0
    assert [name for _, name in stack] == ["nats", "api"]


def test_a_module_can_be_started_on_its_own(stack, tmp_path) -> None:
    dev._write_dev_overlay({"nats": 13042}, nats_secret="s" * 48, nats_password="pw")

    result = _abi("up", "--service", "orchestrator", "-d")

    assert result.exit_code == 0, result.output
    assert stack == [("start", "orchestrator")]


def test_a_module_without_the_nats_stack_is_refused(stack) -> None:
    result = _abi("up", "--service", "orchestrator", "-d")

    assert result.exit_code != 0
    assert "--with-nats" in result.output
    assert stack == []


def test_unknown_names_list_the_modules_too(stack) -> None:
    result = _abi("up", "--service", "nope", "-d")

    assert result.exit_code != 0
    assert "researcher" in result.output and "api" in result.output


def test_down_stops_the_modules_before_the_stack(stack) -> None:
    assert _abi("down").exit_code == 0
    assert [name for _, name in stack] == [
        "orchestrator", "researcher",
        "nexus-web", "dagster", "api", "jaeger", "nats", "oxigraph",
    ]


def test_down_can_target_a_module_or_a_service(stack) -> None:
    assert _abi("down", "--service", "researcher").exit_code == 0
    assert _abi("down", "--service", "api").exit_code == 0
    assert stack == [("stop", "researcher"), ("stop", "api")]


def test_a_module_named_like_a_stack_service_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(dev, "load_dev_modules", lambda: _modules("api"))

    with pytest.raises(dev.click.ClickException, match="api"):
        dev._dev_modules()


def test_an_invalid_dev_block_does_not_block_down(monkeypatch) -> None:
    def broken():
        raise ValueError("dev.modules: bad")

    monkeypatch.setattr(dev, "load_dev_modules", broken)

    with pytest.raises(dev.click.ClickException):
        dev._dev_modules()
    assert dev._dev_modules(strict=False) == {}


def test_a_module_runs_supervised_with_the_dev_broker(monkeypatch, tmp_path) -> None:
    spawned: dict = {}
    monkeypatch.setattr(dev, "_dev_dir", lambda: tmp_path)
    monkeypatch.setattr(dev, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(dev, "_read_pid", lambda spec: None)
    monkeypatch.setattr(
        dev, "_spawn", lambda spec, cmd, cwd, env: spawned.update(spec=spec, cmd=cmd, env=env) or 4242
    )
    overlay = {"nats": {"nats_url": "nats://abi:engine-pw@127.0.0.1:13042", "jwt_secret": "s" * 48, "discovery": {"project": "zen"}}}

    spec = dev._start_module(_modules("researcher")["researcher"], overlay)

    assert spawned["cmd"][2] == "naas_abi_cli.cli.dev_supervisor"
    # Modules log in as `module`, with the project's generated password.
    password = _env_value(tmp_path / ".env", "NATS_MODULE_PASSWORD")
    assert spawned["env"]["ABI_NATS_URL"] == f"nats://module:{password}@127.0.0.1:13042"
    assert spec.log_relpath == "logs/researcher.log"
    assert (tmp_path / "researcher.pid").read_text() == "4242\n"


def test_stopping_a_module_signals_its_group_and_waits(monkeypatch, tmp_path) -> None:
    import itertools

    signals: list = []
    monkeypatch.setattr(dev, "_read_pid", lambda spec: 4242)
    monkeypatch.setattr(dev, "_pid_path", lambda spec: tmp_path / f"{spec.name}.pid")
    monkeypatch.setattr(dev.os, "getpgid", lambda pid: 4242)
    monkeypatch.setattr(dev.os, "killpg", lambda pgid, sig: signals.append(sig))
    monkeypatch.setattr(dev.time, "sleep", lambda s: None)
    clock = itertools.count(0, 1.0)
    monkeypatch.setattr(dev.time, "monotonic", lambda: next(clock))

    # Drains in time: one SIGTERM.
    alive = itertools.chain([True, True, True], itertools.repeat(False))
    monkeypatch.setattr(dev, "_pid_alive", lambda pid: next(alive))
    dev._stop_module("researcher")
    assert signals == [dev.signal.SIGTERM]

    # Never exits: SIGKILL after the grace period.
    signals.clear()
    monkeypatch.setattr(dev, "_pid_alive", lambda pid: True)
    dev._stop_module("researcher")
    assert signals == [dev.signal.SIGTERM, dev.signal.SIGKILL]


def test_a_module_is_ready_when_alive_and_has_no_url() -> None:
    started = [dev._service_spec("api", 9879), dev._module_spec("researcher")]
    table = dev._build_status_panel(
        started,
        {"api": 9879, "researcher": 0},
        "all",
        {
            "api": {"pid": 1, "alive": True, "ready": True},
            "researcher": {"pid": 2, "alive": True, "ready": True},
        },
    )

    assert table.row_count == 2
    assert dev._display_url(started[1]) == "dev module"
    assert dev._open_letter_map(started) == {"a": "api"}
