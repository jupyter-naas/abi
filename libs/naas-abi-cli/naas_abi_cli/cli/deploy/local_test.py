import re
from pathlib import Path

from naas_abi_cli.cli.deploy.local import _build_nexus_api_url, setup_local_deploy


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
    assert re.search(r"^CODER_ADMIN_PASSWORD=Abi1!\S+", env_content, re.M)
    assert re.search(r"^FORGEJO_ADMIN_PASSWORD=Abi1!\S+", env_content, re.M)
    assert re.search(r"^FORGEJO_RUNNER_REGISTRATION_TOKEN=[0-9a-f]{40}$", env_content, re.M)
    assert re.search(r"^CODER_ADMIN_TOKEN=$", env_content, re.M)
    assert re.search(r"^FORGEJO_ADMIN_TOKEN=$", env_content, re.M)


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
    fuseki = _service_block(compose_text, "fuseki", "yasgui")
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
