import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from naas_abi_cli.cli.deploy.deploy import deploy
from naas_abi_cli.cli.deploy.dokploy import (
    COMPOSE_FILE,
    CONFIG_FILE,
    ENV_FILE,
    DokployDeployError,
    setup_dokploy_deploy,
)

# The secret block `abi new project` writes into config.local.yaml.
_CONFIG = """\
api:
  title: demo
  cors_origins:
    - "https://{{ secret.PUBLIC_WEB_HOST }}"
{nats}
modules:
  - module: naas_abi_marketplace.ai.openrouter
    enabled: true
    config:
      openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
  # - module: naas_abi_marketplace.ai.chatgpt
  #   config:
  #     openai_api_key: "{{ secret.OPENAI_API_KEY }}"

services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config: {}
  kv:
    kv_adapter:
      adapter: "redis"
"""
_NATS_BLOCK = """\
nats:
  nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222"
  jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
"""

# Off the Dokploy stack: Caddy is replaced by Traefik, the rest is dropped.
_DROPPED = ("caddy", "yasgui", "redis-commander", "service-portal", "graph-explorer")


def _project(tmp_path: Path, *, nats: bool) -> Path:
    project = tmp_path / "Demo Project"
    project.mkdir()
    (project / "config.local.yaml").write_text(
        _CONFIG.replace("{nats}", _NATS_BLOCK if nats else ""), encoding="utf-8"
    )
    (project / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")
    return project


def _deploy(project: Path, **kwargs) -> dict:
    kwargs.setdefault("domain", "example.com")
    setup_dokploy_deploy(str(project), **kwargs)
    return yaml.safe_load((project / COMPOSE_FILE).read_text(encoding="utf-8"))


def _env(project: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (project / ENV_FILE).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value
    return values


def _labels(service: dict) -> dict[str, str]:
    return dict(label.split("=", 1) for label in service.get("labels", []))


def _rules(services: dict) -> dict[str, tuple[str, str]]:
    """Router name -> (service name, rule), on the HTTPS entrypoint."""
    rules: dict[str, tuple[str, str]] = {}
    for name, service in services.items():
        labels = _labels(service)
        for key, value in labels.items():
            match = re.fullmatch(r"traefik\.http\.routers\.([^.]+)\.rule", key)
            if not match:
                continue
            router = match.group(1)
            entrypoints = labels[f"traefik.http.routers.{router}.entrypoints"]
            if entrypoints == "websecure":
                rules[router] = (name, value)
    return rules


MODES = [
    pytest.param(True, False, id="nats"),
    pytest.param(False, False, id="classic"),
    pytest.param(True, True, id="nats-coding"),
    pytest.param(False, True, id="classic-coding"),
]


@pytest.mark.parametrize("nats, coding", MODES)
def test_the_stack_has_no_edge_of_its_own_and_publishes_no_port(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    compose = _deploy(_project(tmp_path, nats=nats), include_coding=coding)
    services = compose["services"]

    for name in _DROPPED:
        assert name not in services
    for name, service in services.items():
        assert "ports" not in service, name
    assert compose["networks"]["dokploy-network"] == {"external": True}
    assert ("nats" in services) is nats
    assert ("dagster" in services) is not nats
    assert ("rabbitmq" in services) is not nats
    for name in ("coder", "forgejo", "act-runner", "coding-init"):
        assert (name in services) is coding


@pytest.mark.parametrize("nats, coding", MODES)
def test_traefik_routes_each_host_to_its_service(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    services = _deploy(_project(tmp_path, nats=nats), include_coding=coding)["services"]
    rules = _rules(services)
    web, api = "Host(`${PUBLIC_WEB_HOST}`)", "Host(`${PUBLIC_API_HOST}`)"

    targets = {rule: service for service, rule in rules.values()}
    assert targets[web] == "nexus-web"
    assert targets[f"{web} && PathPrefix(`/app-html/`)"] == "abi"
    assert targets[api] == "abi"

    abi, nexus = _labels(services["abi"]), _labels(services["nexus-web"])
    app_html = next(r for r, (_, rule) in rules.items() if "app-html" in rule)
    nexus_web = next(r for r, (_, rule) in rules.items() if rule == web)
    assert int(abi[f"traefik.http.routers.{app_html}.priority"]) > int(
        nexus[f"traefik.http.routers.{nexus_web}.priority"]
    )
    for name in ("abi", "nexus-web"):
        assert "dokploy-network" in services[name]["networks"]
        assert _labels(services[name])["traefik.docker.network"] == "dokploy-network"

    if coding:
        assert targets["Host(`coder.${PUBLIC_WEB_HOST}`)"] == "coder"
        assert targets["Host(`git.${PUBLIC_WEB_HOST}`)"] == "forgejo"
        wildcard = [
            rule
            for service, rule in rules.values()
            if service == "coder" and rule.startswith("HostRegexp")
        ]
        assert wildcard == [r"HostRegexp(`^[a-z0-9-]+\.coder\.${PUBLIC_WEB_HOST}$$`)"]
        coder = _labels(services["coder"])
        assert "*.coder.${PUBLIC_WEB_HOST}" in coder.values()


@pytest.mark.parametrize("nats, coding", MODES)
def test_abi_is_built_from_the_project_dockerfile_without_a_source_mount(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    services = _deploy(_project(tmp_path, nats=nats), include_coding=coding)["services"]
    built = [name for name, service in services.items() if "build" in service]

    assert "abi" in built
    for name in built:
        service = services[name]
        assert service["build"] == {"context": ".", "dockerfile": "Dockerfile"}
        for volume in service.get("volumes", []):
            assert not volume.startswith(".:"), (name, volume)
            assert ".venv" not in volume, (name, volume)
    assert "ENV=dokploy" in services["abi"]["environment"]


@pytest.mark.parametrize("nats, coding", MODES)
def test_the_env_holds_every_variable_the_compose_needs(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    project = _project(tmp_path, nats=nats)
    _deploy(project, include_coding=coding)
    text = (project / COMPOSE_FILE).read_text(encoding="utf-8")
    env = _env(project)

    # ${VAR}, ${VAR:?msg}; ${VAR:-default} has a fallback.
    needed = set(re.findall(r"\$\{([A-Z0-9_]+)(?:\}|:\?)", text))
    assert needed, "the compose interpolates nothing?"
    assert sorted(needed - env.keys()) == []
    for key in needed:
        assert env[key] != "", key

    assert env["PUBLIC_WEB_HOST"] == "nexus.example.com"
    assert env["PUBLIC_API_HOST"] == "api.example.com"
    assert env["NEXUS_API_URL"] == "https://api.example.com"
    assert env["ABI_STACK_NAME"] == "demoproject"
    assert len(env["NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD"]) >= 16
    assert ("NATS_JWT_SECRET" in env) is nats
    assert ("NATS_ABI_PASSWORD" in env) is nats
    assert ("RABBITMQ_PASSWORD" in env) is not nats
    # Every secret the config reads is present, so the engine never prompts.
    assert "OPENROUTER_API_KEY" in env
    # A commented-out module is not a requirement.
    assert "OPENAI_API_KEY" not in env
    # The minted tokens live on the coding_secrets volume: an empty value here
    # would shadow them (environment variables win over dotenv files).
    assert "CODER_ADMIN_TOKEN" not in env
    assert "FORGEJO_ADMIN_TOKEN" not in env
    if coding:
        assert re.fullmatch(r"[0-9a-f]{40}", env["FORGEJO_RUNNER_REGISTRATION_TOKEN"])


def test_the_env_is_stable_across_reruns_unless_regenerated(tmp_path: Path) -> None:
    project = _project(tmp_path, nats=True)
    _deploy(project, include_coding=True)
    first = _env(project)
    (project / ENV_FILE).write_text(
        (project / ENV_FILE).read_text(encoding="utf-8") + "MY_KEY=kept\n",
        encoding="utf-8",
    )

    _deploy(project, include_coding=True, domain=None)
    second = _env(project)
    assert {k: v for k, v in second.items() if k != "MY_KEY"} == first
    assert second["MY_KEY"] == "kept"

    _deploy(project, include_coding=True, regenerate=True)
    third = _env(project)
    for key in ("POSTGRES_PASSWORD", "NATS_ABI_PASSWORD", "CODER_ADMIN_PASSWORD"):
        assert third[key] != first[key], key
    assert third["PUBLIC_WEB_HOST"] == first["PUBLIC_WEB_HOST"]
    backups = list((project / ".abi-backups" / "deploy-dokploy").glob("*/.env.dokploy"))
    assert len(backups) == 1


def test_a_new_domain_moves_the_hosts_and_keeps_the_secrets(tmp_path: Path) -> None:
    project = _project(tmp_path, nats=True)
    _deploy(project)
    before = _env(project)

    _deploy(project, domain="Other.org")
    after = _env(project)

    assert after["PUBLIC_WEB_HOST"] == "nexus.other.org"
    assert after["NEXUS_API_URL"] == "https://api.other.org"
    assert after["POSTGRES_PASSWORD"] == before["POSTGRES_PASSWORD"]


def test_the_env_and_the_build_context_keep_secrets_out_of_git_and_images(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, nats=True)
    (project / ".gitignore").write_text(".venv\n.env\n", encoding="utf-8")
    _deploy(project)
    _deploy(project, domain=None)

    gitignore = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gitignore.count(ENV_FILE) == 1
    dockerignore = (project / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in dockerignore and ".env.*" in dockerignore
    assert dockerignore.count(".env") == 1


@pytest.mark.parametrize("nats, coding", MODES)
def test_the_deploy_files_the_compose_mounts_are_rendered(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    project = _project(tmp_path, nats=nats)
    compose = _deploy(project, include_coding=coding)

    for name, service in compose["services"].items():
        for volume in service.get("volumes", []):
            source = volume.split(":", 1)[0]
            if source.startswith("./"):
                assert (project / source).exists(), (name, source)
    initdb = project / ".deploy/docker/postgres/initdb"
    assert (initdb / "003-create-coder-db.sql").exists() is coding
    # The script writes the tokens where CODING_SECRETS_FILE points.
    if coding:
        script = (project / ".deploy/docker/bootstrap-coding.sh").read_text()
        assert 'ENV_FILE="${CODING_SECRETS_FILE:-/host/.env}"' in script


@pytest.mark.parametrize("coding", [False, True])
def test_the_dokploy_config_reads_the_coding_tokens_as_a_second_dotenv(
    tmp_path: Path, coding: bool
) -> None:
    project = _project(tmp_path, nats=True)
    compose = _deploy(project, include_coding=coding)
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    adapters = yaml.safe_load(re.sub(r"\{\{.*?\}\}", "x", text))["services"]["secret"][
        "secret_adapters"
    ]

    if coding:
        assert adapters == [
            {"adapter": "dotenv", "config": {}},
            {"adapter": "dotenv", "config": {"path": "/run/abi-secrets/coding.env"}},
        ]
        mounts = compose["services"]["abi"]["volumes"]
        assert "coding_secrets:/run/abi-secrets:ro" in mounts
        init = compose["services"]["coding-init"]
        assert "coding_secrets:/run/abi-secrets" in init["volumes"]
        assert init["environment"]["CODING_SECRETS_FILE"] == (
            "/run/abi-secrets/coding.env"
        )
        assert compose["services"]["abi"]["depends_on"]["coding-init"] == {
            "condition": "service_completed_successfully"
        }
    else:
        assert adapters == [{"adapter": "dotenv", "config": {}}]
    # The rest of config.local.yaml is carried over as is.
    assert "openrouter_api_key" in text
    assert "kv_adapter" in text


def test_workspaces_and_ci_jobs_join_the_fixed_name_network(tmp_path: Path) -> None:
    compose = _deploy(_project(tmp_path, nats=True), include_coding=True)
    network = "${ABI_STACK_NAME}-abi-network"

    assert compose["networks"]["abi-network"]["name"] == (
        "${ABI_STACK_NAME:?set ABI_STACK_NAME}-abi-network"
    )
    abi_env = compose["services"]["abi"]["environment"]
    assert f"CODING_WORKSPACE_DOCKER_NETWORK={network}" in abi_env
    runner = yaml.safe_load(compose["configs"]["act_runner_config"]["content"])
    assert runner["container"]["network"] == network
    coder = compose["services"]["coder"]
    assert (
        coder["environment"]["CODER_ACCESS_URL"] == "https://coder.${PUBLIC_WEB_HOST}"
    )
    assert "extra_hosts" not in coder


def test_a_project_without_config_local_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DokployDeployError, match="config.local.yaml"):
        setup_dokploy_deploy(str(tmp_path), domain="example.com")


def test_headscale_is_refused(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, nats=True)
    monkeypatch.chdir(project)

    result = CliRunner().invoke(
        deploy, ["dokploy", "--domain", "example.com", "--headscale"]
    )

    assert result.exit_code != 0
    assert "not supported on Dokploy yet" in result.output
    assert not (project / COMPOSE_FILE).exists()


def test_the_command_renders_the_stack(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, nats=True)
    monkeypatch.chdir(project)

    result = CliRunner().invoke(deploy, ["dokploy", "--domain", "example.com"])

    assert result.exit_code == 0, result.output
    assert (project / COMPOSE_FILE).exists()
    assert "docker-compose.dokploy.yml" in result.output
    assert "Environment" in result.output


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@pytest.mark.parametrize("nats, coding", MODES)
def test_docker_compose_accepts_the_rendered_file(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    project = _project(tmp_path, nats=nats)
    _deploy(project, include_coding=coding)

    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "--env-file",
            ENV_FILE,
            "config",
            "--quiet",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    if "is not a docker command" in result.stderr:
        pytest.skip("docker compose plugin not installed")

    assert result.returncode == 0, result.stderr


def test_the_engine_reads_a_minted_token_from_the_coding_secrets_file(
    tmp_path: Path, monkeypatch
) -> None:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
        SecretServiceConfiguration,
    )

    project = _project(tmp_path, nats=True)
    _deploy(project, include_coding=True)
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    # Where the abi container runs: /app with the volume mounted.
    app, volume = tmp_path / "app", tmp_path / "run-abi-secrets"
    app.mkdir()
    volume.mkdir()
    (app / ".env").touch()  # the container command touches it
    (volume / "coding.env").write_text("CODER_ADMIN_TOKEN=minted\n", encoding="utf-8")
    text = text.replace("/run/abi-secrets", str(volume))
    block = yaml.safe_load(re.sub(r"\{\{.*?\}\}", "x", text))["services"]["secret"]
    monkeypatch.chdir(app)
    monkeypatch.delenv("CODER_ADMIN_TOKEN", raising=False)

    secret = SecretServiceConfiguration(**block).load()

    assert secret.get("CODER_ADMIN_TOKEN") == "minted"
