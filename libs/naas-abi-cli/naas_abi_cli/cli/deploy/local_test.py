import asyncio
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from naas_abi_cli.cli.deploy.local import (
    _build_nexus_api_url,
    project_uses_nats,
    setup_local_deploy,
)


def _services(compose: Path) -> dict:
    return yaml.safe_load(compose.read_text(encoding="utf-8"))["services"]


def _assert_nats_is_opt_in(services: dict) -> None:
    assert services["nats"]["profiles"] == ["nats"]
    for name, service in services.items():
        if name != "nats" and not service.get("profiles"):
            assert "nats" not in service.get("depends_on", {})


def test_nats_stays_opt_in_in_the_repository_compose() -> None:
    """The ABI repository's own stack is not a generated project."""
    repo_root = Path(__file__).resolve().parents[5]
    _assert_nats_is_opt_in(_services(repo_root / "docker-compose.yml"))


def test_a_generated_stack_runs_on_nats_by_default(tmp_path: Path) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost", nats=True)
    services = _services(tmp_path / "docker-compose.yml")

    assert "profiles" not in services["nats"]
    assert services["abi"]["depends_on"]["nats"] == {"condition": "service_healthy"}
    assert "rabbitmq" not in services["abi"]["depends_on"]
    # Nothing uses RabbitMQ in NATS mode; it stays available on request.
    assert services["rabbitmq"]["profiles"] == ["rabbitmq"]
    # One engine per project: Dagster would be a second one (and a second
    # discovery owner); module jobs replace its schedules.
    assert "dagster" not in services
    assert (
        "dagster_home"
        not in (
            yaml.safe_load((tmp_path / "docker-compose.yml").read_text())["volumes"]
        )
    )
    for name, service in services.items():
        if name != "nats" and not service.get("profiles"):
            assert service.get("image") or service.get("build"), name
    assert len(_env_values(tmp_path / ".env")["NATS_JWT_SECRET"]) >= 32


def test_a_classic_stack_keeps_nats_opt_in(tmp_path: Path) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost", nats=False)
    services = _services(tmp_path / "docker-compose.yml")

    _assert_nats_is_opt_in(services)
    assert "dagster" in services
    assert "profiles" not in services["rabbitmq"]
    assert services["abi"]["depends_on"]["rabbitmq"] == {"condition": "service_healthy"}
    assert "NATS_JWT_SECRET" not in _env_values(tmp_path / ".env")


def _write_config(project: Path, *, nats: bool) -> None:
    block = 'nats:\n  nats_url: "nats://nats:4222"\n' if nats else ""
    (project / "config.local.yaml").write_text(
        "api:\n  title: demo\n" + block, encoding="utf-8"
    )


def test_regenerating_an_older_project_does_not_switch_it_to_nats(
    tmp_path: Path, capsys
) -> None:
    _write_config(tmp_path, nats=False)
    setup_local_deploy(str(tmp_path), base_domain="localhost")
    capsys.readouterr()

    setup_local_deploy(str(tmp_path), base_domain="localhost", regenerate=True)

    _assert_nats_is_opt_in(_services(tmp_path / "docker-compose.yml"))
    assert "docs/migrate-to-nats.md" in capsys.readouterr().out


def test_regenerating_a_nats_project_keeps_it_on_nats(tmp_path: Path, capsys) -> None:
    _write_config(tmp_path, nats=True)
    setup_local_deploy(str(tmp_path), base_domain="localhost", regenerate=True)

    assert "profiles" not in _services(tmp_path / "docker-compose.yml")["nats"]
    assert "migrate-to-nats" not in capsys.readouterr().out


def test_project_mode_is_read_from_the_compose_config_first(tmp_path: Path) -> None:
    assert project_uses_nats(str(tmp_path)) is None
    (tmp_path / "config.yaml").write_text("nats:\n  jwt_secret: x\n")
    assert project_uses_nats(str(tmp_path)) is True
    # docker-compose runs config.local.yaml, so it decides.
    _write_config(tmp_path, nats=False)
    assert project_uses_nats(str(tmp_path)) is False


def test_a_commented_nats_block_is_not_nats_mode(tmp_path: Path) -> None:
    (tmp_path / "config.local.yaml").write_text("# nats:\n#   nats_url: x\n")
    assert project_uses_nats(str(tmp_path)) is False


def test_build_nexus_api_url_uses_abi_port_for_localhost() -> None:
    assert _build_nexus_api_url("localhost") == "http://localhost:9879"


def test_build_nexus_api_url_uses_abi_port_for_ip_address() -> None:
    assert _build_nexus_api_url("127.0.0.1") == "http://127.0.0.1:9879"


def test_build_nexus_api_url_keeps_explicit_port() -> None:
    assert _build_nexus_api_url("localhost:8080") == "http://localhost:8080"


def test_build_nexus_api_url_keeps_domain_without_port() -> None:
    assert _build_nexus_api_url("api.localhost") == "https://api.localhost"


def test_build_nexus_api_url_allows_scheme_override() -> None:
    assert _build_nexus_api_url("api.localhost", public_api_scheme="http") == (
        "http://api.localhost"
    )


def test_setup_local_deploy_does_not_include_headscale_by_default(
    tmp_path: Path,
) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    compose_path = tmp_path / "docker-compose.yml"
    env_path = tmp_path / ".env"

    compose_content = compose_path.read_text(encoding="utf-8")
    env_content = env_path.read_text(encoding="utf-8")

    assert "  headscale:" not in compose_content
    assert "HEADSCALE_SERVER_PORT=" not in env_content


def test_setup_local_deploy_can_include_headscale(tmp_path: Path) -> None:
    setup_local_deploy(
        str(tmp_path),
        include_headscale=True,
        base_domain="localhost",
    )

    compose_path = tmp_path / "docker-compose.yml"
    env_path = tmp_path / ".env"
    headscale_config_path = tmp_path / ".deploy/docker/headscale/config.yaml"
    headscale_extra_records_path = (
        tmp_path / ".deploy/docker/headscale/extra-records.json"
    )

    compose_content = compose_path.read_text(encoding="utf-8")
    env_content = env_path.read_text(encoding="utf-8")
    headscale_config_content = headscale_config_path.read_text(encoding="utf-8")

    assert "  headscale:" in compose_content
    assert "headscale_data:" in compose_content
    assert "HEADSCALE_SERVER_PORT=" in env_content
    assert "# The URL clients will connect to." in headscale_config_content
    assert "server_url: https://headscale.localhost:443" in headscale_config_content
    assert headscale_config_path.exists()
    assert headscale_extra_records_path.exists()


def test_setup_local_deploy_does_not_include_coding_by_default(
    tmp_path: Path,
) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    compose_content = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    caddy_content = (tmp_path / ".deploy/docker/Caddyfile").read_text(encoding="utf-8")
    initdb = tmp_path / ".deploy/docker/postgres/initdb"

    assert "\n  coder:" not in compose_content
    assert "\n  forgejo:" not in compose_content
    assert "\n  act-runner:" not in compose_content
    assert "forgejo:3000" not in caddy_content
    assert not (initdb / "003-create-coder-db.sql").exists()
    ducklake_init = initdb / "005-create-ducklake-db.sql"
    assert ducklake_init.exists()
    ducklake_sql = ducklake_init.read_text(encoding="utf-8")
    assert "CREATE DATABASE ducklake" in ducklake_sql
    assert "\\connect ducklake" in ducklake_sql
    assert "CREATE SCHEMA IF NOT EXISTS public" in ducklake_sql
    assert 'GRANT ALL PRIVILEGES ON DATABASE ducklake TO "abi"' in ducklake_sql
    assert 'GRANT ALL PRIVILEGES ON SCHEMA public TO "abi"' in ducklake_sql
    assert not (tmp_path / ".deploy/docker/act-runner-config.yaml").exists()


def test_setup_local_deploy_can_include_coding(tmp_path: Path) -> None:
    setup_local_deploy(
        str(tmp_path),
        include_coding=True,
        base_domain="localhost",
    )

    compose_content = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    caddy_content = (tmp_path / ".deploy/docker/Caddyfile").read_text(encoding="utf-8")
    env_content = (tmp_path / ".env").read_text(encoding="utf-8")
    initdb = tmp_path / ".deploy/docker/postgres/initdb"
    runner_cfg = tmp_path / ".deploy/docker/act-runner-config.yaml"

    # services + volumes are injected
    assert "\n  coder:" in compose_content
    assert "\n  forgejo:" in compose_content
    assert "\n  act-runner:" in compose_content
    assert "coder_data:" in compose_content
    assert "forgejo_data:" in compose_content
    assert "act_runner_data:" in compose_content
    # no unrendered jinja leaks into the generated files
    assert "{%" not in compose_content
    assert "{%" not in caddy_content
    # caddy routes
    assert "coder:7080" in caddy_content
    assert "forgejo:3000" in caddy_content
    # coding-only files copied from the sibling template tree
    assert (initdb / "003-create-coder-db.sql").exists()
    assert (initdb / "004-create-forgejo-db.sql").exists()
    assert runner_cfg.exists()
    runner_content = runner_cfg.read_text(encoding="utf-8")
    assert "{{" not in runner_content
    assert "_abi-network" in runner_content
    # one-shot bootstrap wiring: coding-init service + script, abi/act-runner wait
    assert "\n  coding-init:" in compose_content
    assert compose_content.count("condition: service_completed_successfully") >= 2
    assert (tmp_path / ".deploy/docker/bootstrap-coding.sh").exists()
    boot = (tmp_path / ".deploy/docker/bootstrap-coding.sh").read_text(encoding="utf-8")
    assert "forgejo-cli actions register --secret" in boot
    assert "{%" not in boot and "{{" not in boot  # rendered verbatim

    # .env scaffolding
    assert "CODER_ACCESS_URL=" in env_content
    assert "CODING_WORKSPACE_DOCKER_NETWORK=" in env_content
    assert "_abi-network" in env_content
    # admin passwords generated (complexity-safe); runner secret is 40-hex;
    # the two admin *tokens* start blank (minted by coding-init on first up)
    assert re.search(r"^CODER_ADMIN_PASSWORD=Abi1!\S+", env_content, re.MULTILINE)
    assert re.search(r"^FORGEJO_ADMIN_PASSWORD=Abi1!\S+", env_content, re.MULTILINE)
    assert re.search(
        r"^FORGEJO_RUNNER_REGISTRATION_TOKEN=[0-9a-f]{40}$", env_content, re.MULTILINE
    )
    assert re.search(r"^CODER_ADMIN_TOKEN=$", env_content, re.MULTILINE)
    assert re.search(r"^FORGEJO_ADMIN_TOKEN=$", env_content, re.MULTILINE)


def test_setup_local_deploy_uses_selected_hosts_for_generated_env(
    tmp_path: Path,
) -> None:
    setup_local_deploy(
        str(tmp_path),
        base_domain="example.com",
    )

    env_content = (tmp_path / ".env").read_text(encoding="utf-8")

    assert "PUBLIC_WEB_HOST=nexus.example.com" in env_content
    assert "PUBLIC_API_HOST=api.example.com" in env_content
    assert "NEXUS_API_URL=https://api.example.com" in env_content


def test_setup_local_deploy_generates_headscale_and_vpn_domains(tmp_path: Path) -> None:
    setup_local_deploy(
        str(tmp_path),
        include_headscale=True,
        base_domain="example.com",
    )

    env_content = (tmp_path / ".env").read_text(encoding="utf-8")

    assert "HEADSCALE_SERVER_URL=headscale.example.com" in env_content
    assert "HEADSCALE_INTERNAL_DOMAIN=vpn.example.com" in env_content


def test_setup_local_deploy_regenerate_creates_backup_and_refreshes_compose(
    tmp_path: Path,
) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    compose_path = tmp_path / "docker-compose.yml"
    env_path = tmp_path / ".env"
    compose_path.write_text("custom compose content\n", encoding="utf-8")
    env_path.write_text(
        "PUBLIC_WEB_HOST=custom.local\nCUSTOM_VAR=kept\n",
        encoding="utf-8",
    )

    setup_local_deploy(
        str(tmp_path),
        base_domain="localhost",
        regenerate=True,
    )

    backup_base = tmp_path / ".abi-backups/deploy-local"
    backup_dirs = list(backup_base.iterdir())

    assert len(backup_dirs) == 1
    assert (backup_dirs[0] / "docker-compose.yml").read_text(encoding="utf-8") == (
        "custom compose content\n"
    )
    assert "services:" in compose_path.read_text(encoding="utf-8")

    refreshed_env_content = env_path.read_text(encoding="utf-8")
    assert "PUBLIC_WEB_HOST=custom.local" in refreshed_env_content
    assert "CUSTOM_VAR=kept" in refreshed_env_content


def test_setup_local_deploy_regenerate_without_backup(tmp_path: Path) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    setup_local_deploy(
        str(tmp_path),
        base_domain="localhost",
        regenerate=True,
        backup=False,
    )

    assert not (tmp_path / ".abi-backups").exists()


def _service_block(compose_text: str, service: str, next_service: str) -> str:
    start = compose_text.index(f"\n  {service}:")
    end = compose_text.index(f"\n  {next_service}:", start)
    return compose_text[start:end]


def test_setup_local_deploy_hardens_fuseki_for_reliability(tmp_path: Path) -> None:
    # Guards that `abi deploy local` (and therefore `--regenerate`, which re-renders
    # this same template) carries the Fuseki reliability hardening into a
    # deployment's compose, so existing deployments can be patched by regenerating.
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    compose_text = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    fuseki = _service_block(compose_text, "fuseki", "fuseki-compact")
    lines = [line.strip() for line in fuseki.splitlines()]

    # Image intentionally unchanged for now (staying on the community image;
    # migrating off it is a separate backup + dump-and-reload job).
    assert [line for line in lines if line.startswith("image:")] == [
        "image: stain/jena-fuseki:latest"
    ]

    # Heap + memory caps so an OOM can't Docker-kill the JVM mid-write (the
    # unclean kill that corrupts TDB2).
    assert "mem_limit: 4g" in fuseki
    assert "JVM_ARGS=-Xmx2g" in fuseki

    # Healthcheck probes the dataset, not just the web root, so a broken TDB2
    # dataset marks the container unhealthy instead of falsely reporting ready.
    assert "/ds/query?query=ASK" in fuseki
    assert "start_period: 20s" in fuseki

    # pull_policy: always removed (the explanatory comment mentions it, so assert
    # on real directive lines rather than a naive substring check).
    assert not any(line.startswith("pull_policy") for line in lines)

    # The TDB2 backup/compaction helper ships into the deployment's .deploy/.
    backup_script = tmp_path / ".deploy" / "docker" / "fuseki" / "backup.sh"
    assert backup_script.exists()
    assert "--compact" in backup_script.read_text(encoding="utf-8")


def test_setup_local_deploy_ships_a_nats_config_raising_max_payload_to_8mb(
    tmp_path: Path,
) -> None:
    """nats-server's 1 MB default is the ceiling for one RPC reply; there is
    no CLI flag for it, so the compose service must mount a nats.conf and
    pass it with -c. Anything above 8 MB should stream or return a storage
    reference rather than grow this limit."""
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    compose_content = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    nats_conf = tmp_path / ".deploy/docker/nats/nats.conf"

    assert nats_conf.exists()
    assert "max_payload: 8MB" in nats_conf.read_text(encoding="utf-8")
    nats_block = compose_content.split("\n  nats:", 1)[1].split("\n  redis:", 1)[0]
    assert "exec nats-server -c /etc/nats/nats.conf" in nats_block
    assert "./.deploy/docker/nats/nats.conf:/etc/nats/nats.conf:ro" in nats_block


def _env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_setup_local_deploy_generates_a_per_project_admin_password(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    setup_local_deploy(str(first), base_domain="localhost")
    setup_local_deploy(str(second), base_domain="localhost")

    a = _env_values(first / ".env")["NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD"]
    b = _env_values(second / ".env")["NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD"]

    assert a != b
    assert len(a) >= 24
    for content in (
        (first / ".env").read_text(),
        (first / "docker-compose.yml").read_text(),
    ):
        assert "Admin1234!" not in content
        assert "ABI_API_KEY=abi\n" not in content
    assert "NEXUS_USER_ADMIN_PASSWORD" not in _env_values(first / ".env")


def test_setup_local_deploy_replaces_a_shipped_default_admin_password(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "NEXUS_USER_ADMIN_PASSWORD=Admin1234!\n"
        "NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD=Admin1234!\n",
        encoding="utf-8",
    )

    setup_local_deploy(
        str(tmp_path), base_domain="localhost", regenerate=True, backup=False
    )

    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "Admin1234!" not in content
    assert (
        len(_env_values(tmp_path / ".env")["NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD"])
        >= 24
    )


NATS_USERS = {"abi": "NATS_ABI_PASSWORD", "module": "NATS_MODULE_PASSWORD"}


def _nats_service(compose: Path) -> dict:
    return yaml.safe_load(compose.read_text(encoding="utf-8"))["services"]["nats"]


def _nats_guard(service: dict) -> str:
    entrypoint, flag, script = service["command"]
    assert (entrypoint, flag) == ("sh", "-c")
    # Compose turns $$ into $ before the shell sees it.
    return script.replace("$$", "$")


def test_setup_local_deploy_generates_the_broker_passwords(tmp_path: Path) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost")

    env = _env_values(tmp_path / ".env")

    for key in NATS_USERS.values():
        assert len(env[key]) >= 32


def test_the_broker_requires_a_password_and_listens_on_localhost(
    tmp_path: Path,
) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost")
    repo_root = Path(__file__).resolve().parents[5]

    for root in (repo_root, tmp_path):
        service = _nats_service(root / "docker-compose.yml")
        conf = (root / ".deploy/docker/nats/nats.conf").read_text(encoding="utf-8")
        assert "{ user: abi, password: $NATS_ABI_PASSWORD }" in conf
        assert (
            "{ user: module, password: $NATS_MODULE_PASSWORD, "
            "permissions: $MODULE_PERMISSIONS }" in conf
        )
        for key in NATS_USERS.values():
            assert f"{key}=${{{key}:-}}" in service["environment"]
        assert all(port.startswith("127.0.0.1:") for port in service["ports"])
        assert (
            _nats_guard(service)
            .rstrip()
            .endswith("exec nats-server -c /etc/nats/nats.conf -js -sd /data -m 8222")
        )


def test_the_docker_broker_gives_modules_the_engines_module_permissions(
    tmp_path: Path,
) -> None:
    """The nats.conf lists are the ones nats_permissions defines (and abi dev uses)."""
    from naas_abi_core.engine.nats_permissions import MODULE_PERMISSIONS

    setup_local_deploy(str(tmp_path), base_domain="localhost")
    repo_root = Path(__file__).resolve().parents[5]

    for root in (repo_root, tmp_path):
        conf = (root / ".deploy/docker/nats/nats.conf").read_text(encoding="utf-8")
        block = conf[conf.index("MODULE_PERMISSIONS = {") : conf.index("authorization {")]
        publish = block[block.index("publish:") : block.index("subscribe:")]
        subscribe = block[block.index("subscribe:") :]
        assert re.findall(r'"([^"]+)"', publish) == MODULE_PERMISSIONS["publish"]["deny"]
        assert (
            re.findall(r'"([^"]+)"', subscribe) == MODULE_PERMISSIONS["subscribe"]["deny"]
        )


@pytest.mark.parametrize("missing", list(NATS_USERS.values()))
def test_the_broker_does_not_start_without_a_password(tmp_path: Path, missing) -> None:
    """nats-server takes an empty $VAR as an empty password: anyone could log in."""
    setup_local_deploy(str(tmp_path), base_domain="localhost")
    env = {key: "p" * 32 for key in NATS_USERS.values()} | {missing: ""}

    result = subprocess.run(
        ["sh", "-c", _nats_guard(_nats_service(tmp_path / "docker-compose.yml"))],
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert missing in result.stderr


@pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)
def test_the_generated_broker_admits_only_its_users(tmp_path: Path) -> None:
    import nats
    from nats.errors import Error as NATSError

    setup_local_deploy(str(tmp_path), base_domain="localhost")
    env = _env_values(tmp_path / ".env")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [
            str(shutil.which("nats-server")),
            "-c",
            str(tmp_path / ".deploy/docker/nats/nats.conf"),
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-js",
            "-sd",
            str(tmp_path / "jetstream"),
        ],
        env={**os.environ, **{key: env[key] for key in NATS_USERS.values()}},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    async def connect(credentials: str):
        return await nats.connect(
            f"nats://{credentials}127.0.0.1:{port}",
            allow_reconnect=False,
            connect_timeout=2,
        )

    async def scenario() -> None:
        for credentials in ("", "abi:wrong@", f"intruder:{env['NATS_ABI_PASSWORD']}@"):
            with pytest.raises(NATSError, match="Authorization Violation"):
                await connect(credentials)
        for user, key in NATS_USERS.items():
            nc = await connect(f"{user}:{env[key]}@")
            # Both users share the default account, so its JetStream too.
            await nc.jetstream().account_info()
            await nc.close()

    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                break
            except OSError:
                assert server.poll() is None, (
                    "nats-server refused the generated nats.conf"
                )
                assert time.monotonic() < deadline
                time.sleep(0.05)
        asyncio.run(scenario())
    finally:
        server.terminate()
        server.wait(timeout=5)
