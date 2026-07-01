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
    # .env scaffolding (tokens left blank for the operator to fill post-boot)
    assert "CODER_ACCESS_URL=" in env_content
    assert "CODING_WORKSPACE_DOCKER_NETWORK=" in env_content
    assert "_abi-network" in env_content
    assert "CODER_ADMIN_TOKEN=" in env_content
    assert "FORGEJO_RUNNER_REGISTRATION_TOKEN=" in env_content


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
