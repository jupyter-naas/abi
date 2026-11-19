"""What the coding stack keeps apart: workspaces and CI jobs run on networks of
their own, with no data service on them, CI jobs get no Docker socket, Coder has
an owner before anything reaches it, and the workspace template keeps the
editor on the container's loopback and the system's trust store as it is."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import jinja2
import pytest
import yaml

from naas_abi_cli.cli.deploy.local import setup_local_deploy

REPO = Path(__file__).resolve().parents[5]
TEMPLATES = Path(__file__).resolve().parent / "templates"
CODER_TEMPLATES = [
    REPO / ".deploy/docker/coder_prototype/template/main.tf",
    REPO / ".deploy/docker/coder_prototype/slides_template/main.tf",
]
DATA_SERVICES = {
    "postgres",
    "fuseki",
    "qdrant",
    "redis",
    "minio",
    "nats",
    "mcp-server",
    "rabbitmq",
    "dagster",
}


def _members(services: dict, network: str) -> set[str]:
    return {
        name
        for name, service in services.items()
        if network in (service.get("networks") or [])
    }


@pytest.fixture
def local(tmp_path: Path) -> dict:
    project = tmp_path / "acme"
    project.mkdir()
    setup_local_deploy(
        str(project), base_domain="localhost", include_coding=True, nats=True
    )
    env = dict(
        line.split("=", 1)
        for line in (project / ".env").read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )
    return {
        "project": project,
        "env": env,
        "services": yaml.safe_load((project / "docker-compose.yml").read_text())[
            "services"
        ],
        "runner": yaml.safe_load(
            (project / ".deploy/docker/act-runner-config.yaml").read_text()
        ),
    }


def _dokploy() -> dict:
    text = (TEMPLATES / "dokploy/docker-compose.dokploy.yml").read_text(
        encoding="utf-8"
    )
    return yaml.safe_load(
        jinja2.Template(text).render(
            NATS=True,
            INCLUDE_CODING=True,
            CODER_WILDCARD_CERT=False,
            DISCOVERY_PROJECT="p",
            SECRETS_DIR="/s",
            SECRETS_SETUP="true",
            CODING_SECRETS_DIR="/c",
            CODING_SECRETS_FILE="/c/coding.env",
        )
    )


def test_coding_workspaces_keep_off_the_data_services_network(local: dict) -> None:
    assert local["env"]["CODING_WORKSPACE_DOCKER_NETWORK"] == "acme_coding"
    services = local["services"]
    assert (
        "CODING_WORKSPACE_DOCKER_NETWORK=${CODING_WORKSPACE_DOCKER_NETWORK}"
        in services["abi"]["environment"]
    )
    # Forgejo, coderd, and the API (which calls each workspace's sidecar).
    assert _members(services, "coding") == {"abi", "coder", "forgejo"}


def test_ci_jobs_keep_to_forgejo_without_the_docker_socket(local: dict) -> None:
    container = local["runner"]["container"]
    assert container["network"] == "acme_ci"
    assert container["docker_host"] == "-"
    assert container["valid_volumes"] == []
    assert container["privileged"] is False
    assert _members(local["services"], "ci") == {"act-runner", "forgejo"}


def test_coder_keeps_its_owner_before_anyone_reaches_it(local: dict) -> None:
    services = local["services"]
    coder = services["coder"]
    assert coder["depends_on"]["coder-owner"] == {
        "condition": "service_completed_successfully"
    }
    script = services["coder-owner"]["entrypoint"][2].replace("$$", "$")
    assert "--http-address 127.0.0.1:7080" in script
    assert "/api/v2/users/first" in script
    assert all(
        port.startswith("127.0.0.1:")
        for port in services["coder-owner"].get("ports") or []
    )
    # The bootstrap that runs once Coder is up never makes an owner.
    bootstrap = (local["project"] / ".deploy/docker/bootstrap-coding.sh").read_text(
        encoding="utf-8"
    )
    assert "users/first" not in bootstrap

    assert services["coder-owner"]["environment"]["CODER_PROVISIONER_DAEMONS"] == "0"
    assert "coder_data:/home/coder" in services["coder-owner"]["volumes"]


def test_coder_owner_keeps_to_its_first_run(tmp_path: Path, local: dict) -> None:
    """The one-shot runs coderd once: with the marker in Coder's volume, it
    only hands the volume to Coder's user and exits; without credentials it
    refuses."""
    script = local["services"]["coder-owner"]["entrypoint"][2].replace("$$", "$")
    home = tmp_path / "home"
    home.mkdir()
    runnable = script.replace("/home/coder", str(home)).replace("chown", "true")
    # Stop before coderd: what runs up to it is the marker check and the guard.
    guard = runnable.split("\n/opt/coder server", 1)[0] + "\nexit 7\n"
    env = {"PATH": os.environ["PATH"]}
    for email, password, code in (("", "p", 1), ("a@b.c", "", 1), ("a@b.c", "p", 7)):
        result = subprocess.run(
            ["sh", "-c", guard],
            env={**env, "CODER_ADMIN_EMAIL": email, "CODER_ADMIN_PASSWORD": password},
            capture_output=True,
            check=False,
        )
        assert result.returncode == code
    (home / ".abi-coder-owner").touch()
    marked = subprocess.run(
        ["sh", "-c", guard], env=env, capture_output=True, text=True, check=False
    )
    assert marked.returncode == 0
    assert "Coder owner exists" in marked.stdout


def test_bootstrap_keeps_the_workspace_template_current(local: dict) -> None:
    bootstrap = (local["project"] / ".deploy/docker/bootstrap-coding.sh").read_text(
        encoding="utf-8"
    )
    # A template whose content changed is pushed again, as a new version.
    assert "sha256sum" in bootstrap
    assert (
        'if [ "${TPL_COUNT:-0}" != "0" ] && [ "$TPL_PUSHED" = "$TPL_HASH" ]; then'
        in bootstrap
    )
    assert 'replace_env CODER_TEMPLATE_SHA256 "$TPL_HASH"' in bootstrap


def test_upgrade_keeps_an_older_coding_stack_until_it_regenerates(
    tmp_path: Path,
) -> None:
    import click

    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  coder:\n    image: ghcr.io/coder/coder:v2.34.1\n    user: root\n"
    )
    (tmp_path / ".deploy").mkdir()
    with pytest.raises(click.ClickException, match="--regenerate"):
        setup_local_deploy(
            str(tmp_path), base_domain="localhost", include_coding=True, nats=True
        )


@pytest.mark.parametrize("stack", ["local", "dokploy"])
def test_coder_keeps_its_docker_access_narrow(local: dict, stack: str) -> None:
    services = local["services"] if stack == "local" else _dokploy()["services"]
    coder = services["coder"]
    assert "user" not in coder
    assert not any(
        "docker.sock" in str(volume) for volume in coder.get("volumes") or []
    )
    env = coder["environment"]
    assert env["DOCKER_HOST"] == "tcp://coder-docker:2375"
    proxy = services["coder-docker"]
    assert proxy["environment"]["EXEC"] == "0"
    assert proxy["volumes"] == ["/var/run/docker.sock:/var/run/docker.sock:ro"]
    assert "@sha256:" in proxy["image"]
    assert _members(services, "coder-docker") == {"coder", "coder-docker"}
    assert not proxy.get("ports")


def test_dokploy_coding_stack_keeps_its_own_networks() -> None:
    doc = _dokploy()
    services = doc["services"]
    assert (
        "CODING_WORKSPACE_DOCKER_NETWORK=${ABI_STACK_NAME}-coding"
        in services["abi"]["environment"]
    )
    assert _members(services, "coding") == {"abi", "coder", "forgejo"}
    assert _members(services, "ci") == {"act-runner", "forgejo"}
    assert doc["networks"]["coder-docker"]["internal"] is True
    runner = yaml.safe_load(doc["configs"]["act_runner_config"]["content"])
    assert runner["container"]["network"] == "${ABI_STACK_NAME}-ci"
    assert runner["container"]["docker_host"] == "-"
    assert services["coder"]["depends_on"]["coder-owner"] == {
        "condition": "service_completed_successfully"
    }
    assert not (_members(services, "coding") | _members(services, "ci")) & DATA_SERVICES


def test_older_project_keeps_its_workspaces_off_the_stack_network(
    tmp_path: Path,
) -> None:
    project = tmp_path / "acme"
    project.mkdir()
    (project / ".env").write_text(
        "CODING_WORKSPACE_DOCKER_NETWORK=acme_abi-network\nCODER_ACCESS_URL=http://host.docker.internal:7080\n",
        encoding="utf-8",
    )
    setup_local_deploy(
        str(project), base_domain="localhost", include_coding=True, nats=True
    )
    env = (project / ".env").read_text(encoding="utf-8")
    assert "CODING_WORKSPACE_DOCKER_NETWORK=acme_coding\n" in env
    assert "CODER_ACCESS_URL=http://coder:7080\n" in env
    assert "acme_abi-network" not in env


@pytest.mark.parametrize("template", CODER_TEMPLATES, ids=["code-server", "slides"])
def test_workspace_template_keeps_the_editor_on_loopback(template: Path) -> None:
    text = template.read_text(encoding="utf-8")
    hosts = re.findall(r"code-server [^\n]*--host (\S+)", text)
    assert hosts == ["127.0.0.1"]


@pytest.mark.parametrize("template", CODER_TEMPLATES, ids=["code-server", "slides"])
def test_workspace_template_keeps_the_system_trust_store(template: Path) -> None:
    text = template.read_text(encoding="utf-8")
    assert "BEGIN CERTIFICATE" not in text
    assert "update-ca-certificates" not in text
    assert "ca-certificates/" not in text
    # No route to the host's own ports either.
    assert "host-gateway" not in text


@pytest.mark.parametrize("template", CODER_TEMPLATES, ids=["code-server", "slides"])
def test_workspace_template_keeps_its_network_fixed(template: Path) -> None:
    text = template.read_text(encoding="utf-8")
    block = re.search(
        r'data "coder_parameter" "docker_network" \{(.*?)\n\}', text, re.DOTALL
    )
    assert block is not None
    assert re.search(r"mutable\s*=\s*false", block.group(1))
