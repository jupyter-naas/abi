"""What the Compose stacks keep private: their data services take a credential,
and only Caddy (or Traefik, on Dokploy) faces the network.

Covers every Compose file of the repository: the CLI's local template in the
variants `abi new project` and `abi deploy local` render, the Dokploy template,
the repository's own stack, the Nexus development stack and the Coder
prototype.
"""

from __future__ import annotations

import configparser
import os
import re
import subprocess
from pathlib import Path

import jinja2
import pytest
import yaml

from naas_abi_cli.cli.admin_credentials import (
    DATA_SERVICE_SECRETS,
    ensure_data_service_secrets,
)
from naas_abi_cli.cli.deploy.local import (
    setup_local_deploy,
    upgrade_data_service_config,
)

REPO = Path(__file__).resolve().parents[5]
TEMPLATES = Path(__file__).resolve().parent / "templates"
LOCAL = TEMPLATES / "local" / "docker-compose.yml"
DOKPLOY = TEMPLATES / "dokploy" / "docker-compose.dokploy.yml"
PROJECT_TEMPLATES = (
    Path(__file__).resolve().parents[1] / "new" / "templates" / "project"
)

LOCAL_VARIANTS = {
    "default": {"NATS": True, "INCLUDE_CODING": False, "INCLUDE_HEADSCALE": False},
    "coding-headscale": {
        "NATS": True,
        "INCLUDE_CODING": True,
        "INCLUDE_HEADSCALE": True,
    },
    "classic": {"NATS": False, "INCLUDE_CODING": False, "INCLUDE_HEADSCALE": False},
}


def _render(path: Path, **values) -> dict:
    text = path.read_text(encoding="utf-8")
    if "{%" in text or "{{" in text:
        text = jinja2.Template(text).render(DISCOVERY_PROJECT="p", **values)
    return yaml.safe_load(text)


def _dokploy(nats: bool, coding: bool) -> dict:
    return _render(
        DOKPLOY,
        NATS=nats,
        INCLUDE_CODING=coding,
        CODER_WILDCARD_CERT=False,
        SECRETS_DIR="/s",
        SECRETS_SETUP="true",
        CODING_SECRETS_DIR="/c",
        CODING_SECRETS_FILE="/c/coding.env",
    )


def _stacks() -> dict[str, dict]:
    stacks = {
        f"local:{name}": _render(LOCAL, **values)
        for name, values in LOCAL_VARIANTS.items()
    }
    stacks["root"] = _render(REPO / "docker-compose.yml")
    for nats in (True, False):
        for coding in (True, False):
            stacks[f"dokploy:nats={nats}:coding={coding}"] = _dokploy(nats, coding)
    return stacks


STACKS = _stacks()
DATA_STACKS = {name: doc for name, doc in STACKS.items() if "fuseki" in doc["services"]}


def _script(service: dict) -> str:
    command = service["command"]
    assert command[:2] in (["bash", "-c"], ["sh", "-c"]), command
    # Compose turns `$$` into `$` before the shell runs the script.
    return command[2].replace("$$", "$")


def _host_address(spec: object) -> str:
    """The host address a published port binds ("" means every interface)."""
    if isinstance(spec, dict):
        return str(spec.get("host_ip") or "")
    text = str(spec).strip("\"'")
    if text.startswith("["):
        return text[: text.index("]") + 1]
    parts = text.split(":")
    return parts[0] if len(parts) == 3 else ""


# -- Fuseki ------------------------------------------------------------------


def _run_fuseki_script(
    service: dict, tmp_path: Path, env: dict[str, str]
) -> subprocess.CompletedProcess:
    """The service's start script, with /fuseki under ``tmp_path`` and the
    server's exec replaced by a no-op."""
    script = (
        _script(service)
        .replace("/fuseki/", f"{tmp_path}/fuseki/")
        .replace("/fuseki ", f"{tmp_path}/fuseki ")
        .replace("exec /jena-fuseki/fuseki-server", "exit 0")
    )
    return subprocess.run(
        ["bash", "-c", script],
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
        check=False,
    )


def _shiro_urls(path: Path) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
        elif section == "[urls]" and "=" in line:
            pattern, chain = (part.strip() for part in line.split("=", 1))
            rules.append((pattern, chain))
    return rules


@pytest.mark.parametrize("stack", sorted(DATA_STACKS))
def test_fuseki_keeps_every_endpoint_behind_a_password(
    stack: str, tmp_path: Path
) -> None:
    service = DATA_STACKS[stack]["services"]["fuseki"]
    # The image's own entrypoint keeps the first, open shiro.ini it wrote.
    assert service["entrypoint"] == ["/sbin/tini", "--"]

    result = _run_fuseki_script(
        service, tmp_path, {"ADMIN_PASSWORD": "a" * 32, "ENGINE_PASSWORD": "e" * 32}
    )
    assert result.returncode == 0, result.stderr
    shiro = tmp_path / "fuseki" / "shiro.ini"
    assert shiro.stat().st_mode & 0o077 == 0
    rules = _shiro_urls(shiro)
    # Shiro applies the first rule that matches: only the ping is anonymous,
    # and the last rule catches every path the others do not name.
    assert rules[0] == ("/$/ping", "anon")
    assert rules[-1] == ("/**", "authcBasic, roles[admin]")
    assert all(chain.startswith("authcBasic") for _, chain in rules[1:])
    assert ("/$/**", "authcBasic, roles[admin]") in rules
    assert ("/ds/**", "authcBasic, roles[engine]") in rules

    users = configparser.ConfigParser(delimiters=("=",), interpolation=None)
    users.optionxform = str  # type: ignore[assignment,method-assign]
    users.read_string(shiro.read_text(encoding="utf-8"))
    assert users["users"]["admin"] == f"{'a' * 32}, admin, engine"
    # The engine's user reaches the dataset, not the admin API.
    assert users["users"]["abi"] == f"{'e' * 32}, engine"


@pytest.mark.parametrize("stack", sorted(DATA_STACKS))
def test_fuseki_keeps_its_dataset_to_query_and_update_without_service(
    stack: str, tmp_path: Path
) -> None:
    service = DATA_STACKS[stack]["services"]["fuseki"]
    assert (
        _run_fuseki_script(service, tmp_path, {"ADMIN_PASSWORD": "a" * 32}).returncode
        == 0
    )
    dataset = (tmp_path / "fuseki" / "configuration" / "ds.ttl").read_text(
        encoding="utf-8"
    )

    operations = re.findall(r"fuseki:operation fuseki:([\w-]+)", dataset)
    assert sorted(operations) == ["query", "query", "update"]
    # SERVICE off on both query endpoints and on the dataset, which covers update.
    assert dataset.count('ja:cxtName "arq:httpServiceAllowed"') == 3
    assert re.search(
        r"tdb2:DatasetTDB2 ;\s+ja:context \[ ja:cxtName \"arq:httpServiceAllowed\" ;\s+ja:cxtValue false \]",
        dataset,
    )
    users = (tmp_path / "fuseki" / "shiro.ini").read_text(encoding="utf-8")
    assert "\nabi = " not in users  # no engine password, no engine user


@pytest.mark.parametrize("stack", sorted(DATA_STACKS))
def test_fuseki_keeps_from_starting_without_an_admin_password(
    stack: str, tmp_path: Path
) -> None:
    service = DATA_STACKS[stack]["services"]["fuseki"]
    result = _run_fuseki_script(service, tmp_path, {"ADMIN_PASSWORD": ""})
    assert result.returncode != 0
    assert "FUSEKI_ADMIN_PASSWORD is empty" in result.stderr
    assert not (tmp_path / "fuseki" / "shiro.ini").exists()


# -- Redis and Qdrant --------------------------------------------------------


def _guard(service: dict) -> str:
    """The script up to the server's exec, which is replaced by a no-op."""
    return re.sub(r"\nexec .*", "\nexit 0", _script(service))


@pytest.mark.parametrize("stack", sorted(DATA_STACKS))
def test_redis_keeps_every_client_behind_its_password(stack: str) -> None:
    services = DATA_STACKS[stack]["services"]
    redis = services["redis"]
    assert "REDIS_PASSWORD=${REDIS_PASSWORD:-}" in redis["environment"]
    assert 'redis-server --appendonly yes --requirepass "$REDIS_PASSWORD"' in _script(
        redis
    )
    for value, code in (("", 1), ("r" * 32, 0)):
        result = subprocess.run(
            ["sh", "-c", _guard(redis)],
            env={"PATH": os.environ["PATH"], "REDIS_PASSWORD": value},
            check=False,
            capture_output=True,
        )
        assert result.returncode == code
    # No web console that reads Redis for whoever reaches it.
    assert "redis-commander" not in services


@pytest.mark.parametrize("stack", sorted(DATA_STACKS))
def test_qdrant_keeps_every_request_behind_its_api_key(stack: str) -> None:
    qdrant = DATA_STACKS[stack]["services"]["qdrant"]
    assert "QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY:-}" in qdrant["environment"]
    for value, code in (("", 1), ("q" * 32, 0)):
        result = subprocess.run(
            ["bash", "-c", _guard(qdrant)],
            env={"PATH": os.environ["PATH"], "QDRANT__SERVICE__API_KEY": value},
            check=False,
            capture_output=True,
        )
        assert result.returncode == code


@pytest.mark.parametrize(
    "config",
    [REPO / "config.local.yaml", PROJECT_TEMPLATES / "config.local.yaml"],
    ids=["root", "project"],
)
def test_engine_config_keeps_the_data_services_credentials(config: Path) -> None:
    text = config.read_text(encoding="utf-8")
    assert (
        'jena_tdb2_url: "http://abi:{{ secret.FUSEKI_ENGINE_PASSWORD }}@fuseki:3030/ds"'
        in text
    )
    assert (
        text.count('redis_url: "redis://:{{ secret.REDIS_PASSWORD }}@redis:6379"') == 2
    )
    assert 'api_key: "{{ secret.QDRANT_API_KEY }}"' in text
    assert "redis://redis:" not in text
    assert upgrade_data_service_config(text) == text


def test_older_project_config_keeps_working_against_the_credentialed_stack() -> None:
    old = (
        "nats:\n"
        '  monitoring_url: "http://nats:8222"\n'
        "services:\n"
        "  triple_store:\n"
        "    triple_store_adapter:\n"
        "      config:\n"
        "        key_value_service:\n"
        "          kv_adapter:\n"
        "            config:\n"
        '              redis_url: "redis://redis:6379"\n'
        "  vector_store:\n"
        "    vector_store_adapter:\n"
        "      config:\n"
        '        host: "qdrant"\n'
        "        port: 6333\n"
        "  kv:\n"
        "    kv_adapter:\n"
        "      config:\n"
        '        redis_url: "redis://redis:6379"\n'
    )
    upgraded = yaml.safe_load(upgrade_data_service_config(old))
    services = upgraded["services"]
    assert upgraded["nats"]["monitoring_url"] == "http://nats-monitor:8222"
    assert (
        services["kv"]["kv_adapter"]["config"]["redis_url"]
        == "redis://:{{ secret.REDIS_PASSWORD }}@redis:6379"
    )
    assert services["vector_store"]["vector_store_adapter"]["config"] == {
        "host": "qdrant",
        "port": 6333,
        "api_key": "{{ secret.QDRANT_API_KEY }}",
    }
    upgraded_text = upgrade_data_service_config(old)
    assert upgrade_data_service_config(upgraded_text) == upgraded_text


def test_local_deploy_keeps_generated_data_service_credentials(tmp_path: Path) -> None:
    setup_local_deploy(str(tmp_path), base_domain="localhost", nats=True)
    env = dict(
        line.split("=", 1)
        for line in (tmp_path / ".env").read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )
    first = {key: env[key] for key in DATA_SERVICE_SECRETS}
    assert all(len(value) >= 16 for value in first.values())
    assert len(set(first.values())) == len(first)
    # Kept on the next run.
    setup_local_deploy(str(tmp_path), base_domain="localhost", nats=True)
    assert ensure_data_service_secrets(tmp_path / ".env") == first


# -- What faces the network --------------------------------------------------


EDGE = {"caddy"}


@pytest.mark.parametrize(
    "stack", sorted(name for name in STACKS if not name.startswith("dokploy"))
)
def test_compose_stack_keeps_every_port_but_caddys_on_loopback(stack: str) -> None:
    open_ports = [
        (name, spec)
        for name, service in STACKS[stack]["services"].items()
        for spec in service.get("ports") or []
        if name not in EDGE and _host_address(spec) != "127.0.0.1"
    ]
    assert open_ports == []


@pytest.mark.parametrize(
    "stack", sorted(name for name in STACKS if name.startswith("dokploy"))
)
def test_dokploy_stack_keeps_every_port_unpublished(stack: str) -> None:
    assert [
        name
        for name, service in STACKS[stack]["services"].items()
        if service.get("ports")
    ] == []


def test_nexus_development_stack_keeps_its_ports_on_loopback() -> None:
    services = _render(REPO / "libs/naas-abi/naas_abi/apps/nexus/docker-compose.yml")[
        "services"
    ]
    assert [
        (name, spec)
        for name, service in services.items()
        for spec in service.get("ports") or []
        if _host_address(spec) != "127.0.0.1"
    ] == []


def test_stacks_keep_no_graph_database_proxy() -> None:
    for name, stack in STACKS.items():
        assert "graph-explorer" not in stack["services"], name
        # Nor a SPARQL console that cannot pass the store's credentials.
        assert "yasgui" not in stack["services"], name
    caddyfiles = [
        REPO / ".deploy/docker/Caddyfile",
        REPO / "docker/Caddyfile",
        TEMPLATES / "local/docker/Caddyfile",
    ]
    for caddyfile in caddyfiles:
        text = caddyfile.read_text(encoding="utf-8")
        assert "graph-explorer" not in text, caddyfile
        assert "172.64.0.0/13" not in text, caddyfile


# -- The broker's monitoring port --------------------------------------------


NATS_STACKS = {
    name: doc
    for name, doc in STACKS.items()
    if "nats" in doc["services"] and doc["services"]["nats"].get("profiles") is None
}


@pytest.mark.parametrize(
    "conf",
    [REPO / ".deploy/docker/nats/nats.conf", TEMPLATES / "local/docker/nats/nats.conf"],
    ids=["root", "template"],
)
def test_nats_conf_keeps_monitoring_on_its_own_network(conf: Path) -> None:
    assert re.findall(r"^http:.*$", conf.read_text(encoding="utf-8"), re.MULTILINE) == [
        'http: "nats-monitor:8222"'
    ]


@pytest.mark.parametrize("stack", sorted(NATS_STACKS))
def test_nats_monitoring_keeps_off_the_shared_network(stack: str) -> None:
    doc = NATS_STACKS[stack]
    services = doc["services"]
    nats = services["nats"]
    command = (
        nats["command"]
        if isinstance(nats["command"], str)
        else " ".join(nats["command"])
    )
    # -m would listen on every interface of the container.
    assert " -m " not in command and "--http_port" not in command
    assert all("8222" not in str(port) for port in nats.get("ports") or [])
    assert nats["networks"]["nats-monitor"] == {"aliases": ["nats-monitor"]}
    assert doc["networks"]["nats-monitor"]["internal"] is True
    members = sorted(
        name
        for name, service in services.items()
        if "nats-monitor" in (service.get("networks") or [])
    )
    assert members == ["abi", "nats"]


# -- Upgrading a project ---------------------------------------------------


_OLD_COMPOSE = """services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
  nats:
    image: nats:2.14.7-alpine
    command: ["nats-server", "-js", "-m", "8222"]
"""
_OLD_CONFIG = (
    "nats:\n"
    '  monitoring_url: "http://nats:8222"\n'
    "services:\n"
    "  kv:\n"
    "    kv_adapter:\n"
    "      config:\n"
    '        redis_url: "redis://redis:6379"\n'
)


def _old_project(tmp_path: Path) -> Path:
    (tmp_path / "docker-compose.yml").write_text(_OLD_COMPOSE)
    (tmp_path / "config.local.yaml").write_text(_OLD_CONFIG)
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=kept-value\n")
    (tmp_path / ".deploy").mkdir()
    return tmp_path


def test_upgrade_keeps_the_project_unchanged_until_it_regenerates(
    tmp_path: Path,
) -> None:
    import click

    project = _old_project(tmp_path)
    before = {
        name: (project / name).read_text()
        for name in ("docker-compose.yml", "config.local.yaml", ".env")
    }
    with pytest.raises(click.ClickException, match="--regenerate"):
        setup_local_deploy(str(project), base_domain="localhost", nats=True)
    assert {name: (project / name).read_text() for name in before} == before


def test_upgrade_with_regenerate_keeps_compose_config_and_env_in_agreement(
    tmp_path: Path,
) -> None:
    project = _old_project(tmp_path)
    setup_local_deploy(
        str(project), base_domain="localhost", nats=True, regenerate=True
    )

    compose = (project / "docker-compose.yml").read_text()
    config = (project / "config.local.yaml").read_text()
    env = dict(
        line.split("=", 1)
        for line in (project / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    from naas_abi_cli.cli.deploy.local import outdated_stack

    assert outdated_stack(compose) == []
    assert "redis://:{{ secret.REDIS_PASSWORD }}@redis:6379" in config
    assert '"http://nats-monitor:8222"' in config
    assert env["POSTGRES_PASSWORD"] == "kept-value"
    assert all(len(env[key]) >= 16 for key in DATA_SERVICE_SECRETS)
    # The next run without --regenerate goes through.
    setup_local_deploy(str(project), base_domain="localhost", nats=True)


# -- The tailnet --------------------------------------------------------------


def test_headscale_keeps_a_default_deny_tailnet(tmp_path: Path) -> None:
    import json

    setup_local_deploy(
        str(tmp_path), base_domain="example.com", include_headscale=True, nats=True
    )
    headscale = tmp_path / ".deploy/docker/headscale"
    config = yaml.safe_load((headscale / "config.yaml").read_text())
    assert config["policy"] == {"mode": "file", "path": "/etc/headscale/acl.hujson"}
    policy_text = "\n".join(
        line
        for line in (headscale / "acl.hujson").read_text().splitlines()
        if not line.strip().startswith("//")
    )
    policy = json.loads(re.sub(r"\s//.*", "", policy_text))
    # One rule, between an address no node holds.
    assert policy["hosts"] == {"nowhere": "192.0.2.1/32"}
    assert policy["acls"] == [
        {"action": "accept", "src": ["nowhere"], "dst": ["nowhere:*"]}
    ]

    service = yaml.safe_load((tmp_path / "docker-compose.yml").read_text())["services"][
        "headscale"
    ]
    assert (
        "./.deploy/docker/headscale/acl.hujson:/etc/headscale/acl.hujson:ro"
        in service["volumes"]
    )


def test_headscale_keeps_metrics_and_grpc_inside_its_container(tmp_path: Path) -> None:
    setup_local_deploy(
        str(tmp_path), base_domain="example.com", include_headscale=True, nats=True
    )
    config = yaml.safe_load(
        (tmp_path / ".deploy/docker/headscale/config.yaml").read_text()
    )
    assert config["metrics_listen_addr"].startswith("127.0.0.1:")
    assert config["grpc_listen_addr"].startswith("127.0.0.1:")
    assert config["grpc_allow_insecure"] is False
    for compose in (tmp_path / "docker-compose.yml",):
        ports = yaml.safe_load(compose.read_text())["services"]["headscale"]["ports"]
        assert ports == ["127.0.0.1:${HEADSCALE_SERVER_PORT}:8080"]
    # The service an older compose gets added (abi deploy local --with-headscale).
    from naas_abi_cli.cli.deploy.local import HEADSCALE_DOCKER_COMPOSE_SNIPPET

    snippet = yaml.safe_load("services:" + HEADSCALE_DOCKER_COMPOSE_SNIPPET)[
        "services"
    ]["headscale"]
    assert snippet["ports"] == ["127.0.0.1:${HEADSCALE_SERVER_PORT}:8080"]


@pytest.mark.parametrize(
    "config",
    [REPO / "config.yaml", REPO / "config.local.yaml"],
    ids=["root", "root-local"],
)
def test_repository_config_keeps_its_administrator_out_of_the_file(
    config: Path,
) -> None:
    from naas_abi_cli.cli.admin_credentials import configured_superadmins

    text = config.read_text()
    assert "admin@example.com" not in text
    assert "{{ secret.NEXUS_USER_ADMIN_EMAIL }}" in text
    assert set(configured_superadmins(text)) <= {"secret:NEXUS_USER_ADMIN_EMAIL"}


def test_upgrade_keeps_an_older_headscale_until_it_regenerates(tmp_path: Path) -> None:
    import click

    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  headscale:\n    image: docker.io/headscale/headscale:stable\n"
    )
    (tmp_path / ".deploy").mkdir()
    with pytest.raises(click.ClickException, match="headscale has no ACL policy"):
        setup_local_deploy(
            str(tmp_path), base_domain="example.com", include_headscale=True, nats=True
        )
