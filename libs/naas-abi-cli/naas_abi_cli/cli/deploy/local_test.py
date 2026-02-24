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
    setup_local_deploy(
        str(tmp_path),
        public_web_host="localhost",
        public_api_host="api.localhost",
    )

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
        public_web_host="localhost",
        public_api_host="api.localhost",
    )

    compose_path = tmp_path / "docker-compose.yml"
    env_path = tmp_path / ".env"
    headscale_config_path = tmp_path / ".deploy/docker/headscale/config.yaml"
    headscale_extra_records_path = (
        tmp_path / ".deploy/docker/headscale/extra-records.json"
    )

    compose_content = compose_path.read_text(encoding="utf-8")
    env_content = env_path.read_text(encoding="utf-8")

    assert "  headscale:" in compose_content
    assert "headscale_data:" in compose_content
    assert "HEADSCALE_SERVER_PORT=" in env_content
    assert headscale_config_path.exists()
    assert headscale_extra_records_path.exists()


def test_setup_local_deploy_uses_selected_hosts_for_generated_env(
    tmp_path: Path,
) -> None:
    setup_local_deploy(
        str(tmp_path),
        public_web_host="nexus.example.com",
        public_api_host="api.example.com",
    )

    env_content = (tmp_path / ".env").read_text(encoding="utf-8")

    assert "PUBLIC_WEB_HOST=nexus.example.com" in env_content
    assert "PUBLIC_API_HOST=api.example.com" in env_content
    assert "NEXUS_API_URL=https://api.example.com" in env_content
