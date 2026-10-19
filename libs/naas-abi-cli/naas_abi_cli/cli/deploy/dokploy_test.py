import os
import re
import shutil
import subprocess
from pathlib import Path

import jinja2
import pytest
import yaml
from click.testing import CliRunner
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
    SecretServiceConfiguration,
)

from naas_abi_cli.cli.deploy.deploy import deploy
from naas_abi_cli.cli.deploy.dokploy import (
    CODING_SECRETS_FILE,
    COMPOSE_FILE,
    CONFIG_FILE,
    ENV_FILE,
    SECRETS_FILE,
    DokployDeployError,
    setup_dokploy_deploy,
)
from naas_abi_cli.cli.deploy.local import setup_local_deploy

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


def _project(
    tmp_path: Path, *, nats: bool, name: str = "Demo Project", config: str = _CONFIG
) -> Path:
    project = tmp_path / name
    project.mkdir()
    (project / "config.local.yaml").write_text(
        config.replace("{nats}", _NATS_BLOCK if nats else ""), encoding="utf-8"
    )
    (project / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
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


def _secret_adapters(project: Path) -> list:
    """The engine's view of config.dokploy.yaml, with every secret empty."""
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    config = EngineConfiguration.render_without_secrets(text, base_dir=str(project))
    return config["services"]["secret"]["secret_adapters"]


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


def _dir(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    return folder


@pytest.mark.parametrize("nats", [True, False])
def test_the_stack_runs_the_images_of_the_local_stack(
    tmp_path: Path, nats: bool
) -> None:
    # The two templates are kept by hand: an image one moves to (MinIO's public
    # images are gone) must not stay behind in the other, where it fails to pull
    # on the server.
    dokploy = _deploy(_project(_dir(tmp_path, "a"), nats=nats))["services"]
    local_project = _dir(tmp_path, "b")
    setup_local_deploy(str(local_project), base_domain="localhost", nats=nats)
    local = yaml.safe_load((local_project / "docker-compose.yml").read_text())[
        "services"
    ]

    shared = {
        name
        for name in dokploy.keys() & local.keys()
        if "image" in dokploy[name] and "image" in local[name]
    }
    assert {"minio", "minio-init", "postgres"} <= shared
    assert {name: dokploy[name]["image"] for name in shared} == {
        name: local[name]["image"] for name in shared
    }
    # What a sidecar runs is a shell script no one reads twice: it must not be
    # the older copy either (fuseki-compact's `||` on a line of its own is a
    # shell syntax error that restarts the container forever).
    # nats: the local stack refuses an empty broker password in a shell wrapper,
    # this one at interpolation (`${NATS_ABI_PASSWORD:?...}`).
    scripts = sorted(shared - {"nats"})
    for key in ("entrypoint", "command"):
        assert {name: dokploy[name].get(key) for name in scripts} == {
            name: local[name].get(key) for name in scripts
        }, key


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
        apps = r"HostRegexp(`^[a-z0-9-]+\.coder\.${PUBLIC_WEB_HOST}$$`)"
        wildcard = [
            rule
            for service, rule in rules.values()
            if service == "coder" and rule.startswith("HostRegexp")
        ]
        assert wildcard == [apps]
        # Plain HTTP on a workspace app host is redirected too.
        redirect = next(
            value
            for key, value in nexus.items()
            if key.endswith(".rule")
            and nexus[key.replace(".rule", ".entrypoints")] == "web"
        )
        assert apps in redirect
        assert "Host(`git.${PUBLIC_WEB_HOST}`)" in redirect


@pytest.mark.parametrize("nats", [True, False])
def test_the_wildcard_certificate_is_requested_only_from_a_dns_resolver(
    tmp_path: Path, nats: bool
) -> None:
    project = _project(tmp_path, nats=nats)
    coder = _labels(_deploy(project, include_coding=True)["services"]["coder"])
    # Let's Encrypt refuses a wildcard over HTTP-01: ask for none.
    assert not any("tls.domains" in key for key in coder)
    assert "*.coder.${PUBLIC_WEB_HOST}" not in coder.values()
    apps = "traefik.http.routers.${ABI_STACK_NAME}-coder-apps"
    assert coder[f"{apps}.tls"] == "true"
    assert f"{apps}.tls.certresolver" not in coder
    assert "CODER_WILDCARD_CERT_RESOLVER" not in _env(project)

    coder = _labels(
        _deploy(project, include_coding=True, wildcard_cert_resolver="cloudflare")[
            "services"
        ]["coder"]
    )
    assert coder[f"{apps}.tls.domains[0].sans"] == "*.coder.${PUBLIC_WEB_HOST}"
    assert coder[f"{apps}.tls.certresolver"].startswith(
        "${CODER_WILDCARD_CERT_RESOLVER:?"
    )
    assert _env(project)["CODER_WILDCARD_CERT_RESOLVER"] == "cloudflare"

    # Kept on a rerun without the option, and on a regenerated env.
    for kwargs in ({"domain": None}, {"regenerate": True}):
        coder = _labels(
            _deploy(project, include_coding=True, **kwargs)["services"]["coder"]
        )
        assert f"{apps}.tls.domains[0].sans" in coder, kwargs
        assert _env(project)["CODER_WILDCARD_CERT_RESOLVER"] == "cloudflare"

    _deploy(project, include_coding=True, wildcard_cert_resolver="route53")
    assert _env(project)["CODER_WILDCARD_CERT_RESOLVER"] == "route53"

    # A run without --coding keeps it for the next --coding run.
    _deploy(project, domain=None)
    text = (project / ENV_FILE).read_text(encoding="utf-8")
    assert text.count("CODER_WILDCARD_CERT_RESOLVER=") == 1
    assert _env(project)["CODER_WILDCARD_CERT_RESOLVER"] == "route53"
    coder = _labels(_deploy(project, include_coding=True)["services"]["coder"])
    assert coder[f"{apps}.tls.domains[0].sans"] == "*.coder.${PUBLIC_WEB_HOST}"


def test_a_wildcard_resolver_without_coding_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DokployDeployError, match="--coding"):
        _deploy(_project(tmp_path, nats=True), wildcard_cert_resolver="cloudflare")


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
    # Every secret the config reads is listed, commented out until filled in:
    # an empty variable would still win over the engine's secrets file.
    lines = (project / ENV_FILE).read_text(encoding="utf-8").splitlines()
    assert "# OPENROUTER_API_KEY=" in lines
    assert "OPENROUTER_API_KEY" not in env
    # A commented-out module is not a requirement.
    assert not any("OPENAI_API_KEY" in line for line in lines)
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
        (project / ENV_FILE).read_text(encoding="utf-8") + "MY_KEY=kept\nMY_EMPTY=\n",
        encoding="utf-8",
    )

    _deploy(project, include_coding=True, domain=None)
    second = _env(project)
    assert {k: v for k, v in second.items() if k != "MY_KEY"} == first
    assert second["MY_KEY"] == "kept"
    # An empty value would win over the engine's secrets file: commented out.
    assert (
        "# MY_EMPTY=" in (project / ENV_FILE).read_text(encoding="utf-8").splitlines()
    )

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


_PERSISTENT = {
    "adapter": "dotenv",
    "config": {"path": SECRETS_FILE, "environment_first": True},
}
_MINTED = {
    "adapter": "dotenv",
    "config": {"path": CODING_SECRETS_FILE, "read_only": True},
}
_PROJECT_DOTENV = {"adapter": "dotenv", "config": {}}


@pytest.mark.parametrize("nats, coding", MODES)
def test_the_dokploy_config_keeps_secrets_on_volumes(
    tmp_path: Path, nats: bool, coding: bool
) -> None:
    project = _project(tmp_path, nats=nats)
    compose = _deploy(project, include_coding=coding)
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    services = compose["services"]

    assert _secret_adapters(project) == (
        [_PERSISTENT, _PROJECT_DOTENV] + ([_MINTED] if coding else [])
    )
    # Every service that reads the config has the writable secrets volume.
    readers = ["abi"] + ([] if nats else ["dagster"])
    for name in readers:
        assert "abi_secrets:/var/lib/abi-secrets" in services[name]["volumes"], name
        command = services[name]["command"][-1]
        assert command.startswith("touch /var/lib/abi-secrets/.env .env && ")
        # The config's own secrets are added empty to the volume file; never
        # the stack's (set in the Environment tab) or the minted tokens.
        assert "for k in OPENROUTER_API_KEY; do" in command
        if coding:
            assert "coding_secrets:/run/abi-secrets:ro" in services[name]["volumes"]
    assert "abi_secrets" in compose["volumes"]
    if coding:
        init = services["coding-init"]
        assert "coding_secrets:/run/abi-secrets" in init["volumes"]
        assert init["environment"]["CODING_SECRETS_FILE"] == CODING_SECRETS_FILE
        assert init["environment"]["CODING_INIT_STRICT"] == "1"
        assert services["abi"]["depends_on"]["coding-init"] == {
            "condition": "service_completed_successfully"
        }
    # The rest of config.local.yaml is carried over as is, comments included.
    assert "openrouter_api_key" in text
    assert "kv_adapter" in text
    assert "#     openai_api_key:" in text


_OWN_ADAPTERS = """\
modules:
  - module: demo
    config:
      # Not the engine's list: left alone.
      secret_adapters:
        - adapter: "dotenv"
services:
  secret:
    secret_adapters:
      # The Naas vault comes first.
      - adapter: "naas"
        config:
          naas_api_key: "{{ secret.NAAS_API_KEY }}"
          naas_api_url: 'https://api.naas.ai'
      # Local overrides.
      - adapter: "dotenv"
        config: {}
      # - adapter: "dotenv"
      #   config: {path: "spare.env"}
      - adapter: "base64"
        config:
          base64_secret_key: "{{ secret.B64 }}"
          secret_adapter:
            adapter: "dotenv"
            config: {}
  kv:
    kv_adapter:
      adapter: redis"""

_NAAS = {
    "adapter": "naas",
    "config": {"naas_api_key": "", "naas_api_url": "https://api.naas.ai"},
}
_BASE64 = {
    "adapter": "base64",
    "config": {"base64_secret_key": "", "secret_adapter": _PROJECT_DOTENV},
}


@pytest.mark.parametrize("trailing_newline", [True, False])
def test_the_projects_own_secret_adapters_are_kept_line_for_line(
    tmp_path: Path, trailing_newline: bool
) -> None:
    config = _OWN_ADAPTERS + ("\n" if trailing_newline else "")
    project = _project(tmp_path, nats=False, config=config)
    _deploy(project, include_coding=True)

    # The volume dotenv takes the place of the project's `.env` one: the
    # project's first adapter stays first.
    assert _secret_adapters(project) == [
        _NAAS,
        _PERSISTENT,
        _PROJECT_DOTENV,
        _BASE64,
        _MINTED,
    ]
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    # The project's lines, quoting and comments are unchanged.
    for part in (
        config.split("\n    secret_adapters:\n", 1)[1]
        .split("  kv:")[0]
        .split("      # Local overrides.\n")
    ):
        assert part in text
    assert text.index("Added by `abi deploy dokploy`: secrets") < text.index(
        "# Local overrides."
    )
    assert '      secret_adapters:\n        - adapter: "dotenv"\nservices:' in text
    assert "NAAS_API_KEY" in (project / ENV_FILE).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "items, expected",
    [
        # No `.env` dotenv: after the project's first adapter.
        ([_NAAS, _BASE64], [_NAAS, _PERSISTENT, _BASE64]),
        ([_NAAS], [_NAAS, _PERSISTENT]),
        ([_PROJECT_DOTENV, _NAAS], [_PERSISTENT, _PROJECT_DOTENV, _NAAS]),
    ],
)
def test_the_volume_dotenv_never_goes_ahead_of_the_projects_first_adapter(
    tmp_path: Path, items: list, expected: list
) -> None:
    lines = ["services:", "  secret:", "    secret_adapters:"]
    for item in items:
        dumped = yaml.safe_dump([item], sort_keys=False).splitlines()
        lines += [f"      {line}" for line in dumped]
    project = _project(tmp_path, nats=True, config="\n".join(lines) + "\n")
    _deploy(project)

    assert _secret_adapters(project) == expected


def test_jinja_outside_the_list_is_kept(tmp_path: Path) -> None:
    config = _CONFIG.replace(
        "api:\n  title: demo\n",
        "api:\n  title: demo\n{% if true %}\n  extra: 1\n{% endif %}\n"
        "{% include 'api.yaml' %}\n",
    )
    project = _project(tmp_path, nats=True, config=config)
    (project / "api.yaml").write_text("  version: 2\n", encoding="utf-8")
    _deploy(project, include_coding=True)

    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    assert "{% if true %}\n  extra: 1\n{% endif %}\n{% include 'api.yaml' %}" in text
    assert _secret_adapters(project) == [_PERSISTENT, _PROJECT_DOTENV, _MINTED]


@pytest.mark.parametrize(
    "items",
    [
        '{% if true %}\n      - adapter: "dotenv"\n        config: {}\n{% endif %}\n',
        (
            '{% for name in ["dotenv"] %}\n      - adapter: "{{ name }}"\n'
            "        config: {}\n{% endfor %}\n"
        ),
        "{% include 'adapters.yaml' %}\n",
        (
            '      - adapter: "dotenv"\n        config: {}\n'
            "{% if secret.EXTRA %}\n      - adapter: naas\n{% endif %}\n"
        ),
    ],
)
def test_jinja_inside_the_list_is_refused(tmp_path: Path, items: str) -> None:
    config = _CONFIG.replace('      - adapter: "dotenv"\n        config: {}\n', items)
    project = _project(tmp_path, nats=True, config=config)
    (project / "adapters.yaml").write_text(
        '      - adapter: "dotenv"\n        config: {}\n', encoding="utf-8"
    )

    with pytest.raises(DokployDeployError, match="outside the list"):
        _deploy(project, include_coding=True)


def test_crlf_line_endings_are_read_and_kept(tmp_path: Path) -> None:
    config = (
        _CONFIG.replace("{nats}", "")
        .replace("\n", "\r\n")
        .replace("  secret:\r\n", "  secret:\r\n\r\n")
        .replace("    secret_adapters:\r\n", "    secret_adapters:\r\n\r\n")
    )
    project = _project(tmp_path, nats=True)
    (project / "config.local.yaml").write_bytes(config.encode("utf-8"))
    _deploy(project, include_coding=True)

    raw = (project / CONFIG_FILE).read_bytes().decode("utf-8")
    assert raw.count("\n") == raw.count("\r\n")
    assert _secret_adapters(project) == [_PERSISTENT, _PROJECT_DOTENV, _MINTED]


@pytest.mark.parametrize("path", [".env.prod", "config/.env", "/run/secrets/abi.env"])
def test_a_dotenv_other_than_dot_env_is_refused(tmp_path: Path, path: str) -> None:
    config = _CONFIG.replace("config: {}", f'config:\n          path: "{path}"')
    project = _project(tmp_path, nats=True, config=config)
    if not path.startswith("/"):
        # Present locally, as a gitignored file would be: still refused.
        (project / path).parent.mkdir(parents=True, exist_ok=True)
        (project / path).touch()

    with pytest.raises(DokployDeployError, match="Environment tab"):
        _deploy(project)


def test_a_config_without_a_secret_section_says_so(tmp_path: Path) -> None:
    project = _project(tmp_path, nats=True, config="services:\n  kv: {}\n")

    with pytest.raises(DokployDeployError, match="no services.secret.secret_adapters"):
        _deploy(project)


def test_a_failed_render_writes_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path, nats=True, config="services:\n  kv: {}\n")

    with pytest.raises(DokployDeployError, match="secret_adapters"):
        setup_dokploy_deploy(str(project), domain="example.com")

    assert sorted(path.name for path in project.iterdir()) == [
        "Dockerfile",
        "config.local.yaml",
    ]


def _internal_hosts(value: str) -> set[str]:
    """Host names in the URLs of ``value``."""
    return set(
        re.findall(r"[a-z]+://(?:[^@/\s]*@)?([A-Za-z0-9_.${}-]+?)(?::\d+|/|$)", value)
    )


def test_two_stacks_on_one_server_never_call_each_other(tmp_path: Path) -> None:
    """Internal calls never use a name another stack has on dokploy-network.

    Service names are on dokploy-network for every stack (Compose adds them on
    each network), so a container on both networks reaches this stack only
    through aliases that exist on its own network alone.
    """
    stacks = {}
    for name in ("one", "two"):
        project = _project(tmp_path, nats=True, name=name)
        _deploy(project, include_coding=True)
        text = (project / COMPOSE_FILE).read_text(encoding="utf-8")
        text = re.sub(r"\$\{ABI_STACK_NAME(:\?[^}]*)?\}", name, text)
        stacks[name] = (yaml.safe_load(text), (project / CONFIG_FILE).read_text())

    shared: set[str] = set()  # every name any stack has on dokploy-network
    own: dict[str, set[str]] = {}
    for name, (compose, _) in stacks.items():
        own[name] = set()
        for service_name, service in compose["services"].items():
            networks = service.get("networks", [])
            if "dokploy-network" in networks:
                shared.add(service_name)
                shared.update((networks["dokploy-network"] or {}).get("aliases", []))
            if isinstance(networks, dict):
                own[name].update((networks.get("abi-network") or {}).get("aliases", []))
    assert own["one"].isdisjoint(own["two"])
    assert own["one"].isdisjoint(shared)

    for name, (compose, config) in stacks.items():
        for service_name, service in compose["services"].items():
            if "dokploy-network" not in service.get("networks", []):
                continue
            # The calls a container on both networks makes: its environment,
            # and for abi and dagster the engine config.
            values = list(service.get("environment") or [])
            if isinstance(service.get("environment"), dict):
                values = list(service["environment"].values())
            if service_name == "abi":
                values.append(re.sub(r"\{\{.*?\}\}", "x", config))
            for value in values:
                for host in _internal_hosts(str(value)):
                    if "." in host or "$" in host:
                        continue  # public hosts
                    assert host not in shared, (name, service_name, host)
    # nexus-web reaches this stack's abi.
    nexus = stacks["one"][0]["services"]["nexus-web"]["environment"]
    assert "NEXUS_INTERNAL_API_URL=http://one-abi:9879" in nexus


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


def test_the_engine_reads_minted_tokens_and_writes_to_its_volume(
    tmp_path: Path, monkeypatch
) -> None:
    from dotenv import dotenv_values

    project = _project(tmp_path, nats=True)
    _deploy(project, include_coding=True)
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")
    # The abi container: /app with an empty .env, both volumes mounted,
    # coding_secrets read-only.
    app, secrets_volume, coding_volume = (
        tmp_path / "app",
        tmp_path / "abi-secrets",
        tmp_path / "coding",
    )
    for directory in (app, secrets_volume, coding_volume):
        directory.mkdir()
    (app / ".env").touch()  # the container command touches both
    (secrets_volume / ".env").write_text(
        "SAVED_KEY=saved\nTAB_KEY=stale\n", encoding="utf-8"
    )
    minted = coding_volume / "coding.env"
    minted.write_text("CODER_ADMIN_TOKEN=minted\n", encoding="utf-8")
    minted.chmod(0o444)
    text = text.replace("/var/lib/abi-secrets", str(secrets_volume))
    text = text.replace("/run/abi-secrets", str(coding_volume))
    monkeypatch.chdir(app)
    for key in ("CODER_ADMIN_TOKEN", "SAVED_KEY", "NEXUS_USER_DEMO_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TAB_KEY", "from-the-tab")  # set in the Environment tab

    config = EngineConfiguration.render_without_secrets(text, base_dir=str(app))
    secret = SecretServiceConfiguration(**config["services"]["secret"]).load()

    assert secret.get("CODER_ADMIN_TOKEN") == "minted"
    assert secret.get("SAVED_KEY") == "saved"
    # The Environment tab wins over the file, as when the config is rendered.
    assert secret.get("TAB_KEY") == "from-the-tab"
    # A secret stored at runtime (a generated user password) lands on the
    # writable volume; the read-only file is left alone.
    secret.set("NEXUS_USER_DEMO_PASSWORD", "generated")
    assert dotenv_values(secrets_volume / ".env")["NEXUS_USER_DEMO_PASSWORD"] == (
        "generated"
    )
    secret.remove("NEXUS_USER_DEMO_PASSWORD")
    assert minted.read_text(encoding="utf-8") == "CODER_ADMIN_TOKEN=minted\n"


def test_coding_init_mints_under_fresh_names_and_fails_loudly_on_dokploy(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, nats=True)
    _deploy(project, include_coding=True)
    script = (project / ".deploy/docker/bootstrap-coding.sh").read_text()

    # A token name already taken (secrets volume lost) must not block a mint.
    assert '"token_name":"nexus-admin-%s"' in script
    assert '--token-name "nexus-$TOKEN_SUFFIX"' in script
    assert '[ "${CODING_INIT_STRICT:-0}" = "1" ]' in script
    assert "exit 1" in script


@pytest.mark.parametrize("nats", [True, False])
def test_a_fresh_project_boots_with_an_empty_secrets_volume(
    tmp_path: Path, monkeypatch, nats: bool
) -> None:
    """The generated config, .env.dokploy and container command, on a first
    deploy: nothing saved yet, OPENROUTER_API_KEY not filled in."""
    import naas_abi_cli

    template = (
        Path(naas_abi_cli.__file__).parent
        / "cli/new/templates/project/config.local.yaml"
    )
    config = jinja2.Template(
        template.read_text(encoding="utf-8"), keep_trailing_newline=True
    ).render(
        nats=nats,
        include_coding=True,
        project_name_snake="demo",
        project_name_pascal="Demo",
    )
    project = _project(tmp_path, nats=nats, config=config)
    compose = _deploy(project, include_coding=True)
    text = (project / CONFIG_FILE).read_text(encoding="utf-8")

    # The container: the Environment tab as its environment, an empty /app,
    # empty volumes.
    for key in list(os.environ):
        if key.startswith(("NEXUS_", "POSTGRES_", "OPENROUTER", "NATS_", "CODER_")):
            monkeypatch.delenv(key)
    for key, value in _env(project).items():
        monkeypatch.setenv(key, value)
    assert "OPENROUTER_API_KEY" not in os.environ
    app, volume, coding = tmp_path / "app", tmp_path / "secrets", tmp_path / "coding"
    for directory in (app, volume, coding):
        directory.mkdir()
    (coding / "coding.env").touch()
    text = text.replace("/var/lib/abi-secrets", str(volume))
    text = text.replace("/run/abi-secrets", str(coding))
    monkeypatch.chdir(app)

    # Without the setup step, the first boot stops on the missing key.
    (volume / ".env").touch()
    (app / ".env").touch()
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        EngineConfiguration.from_yaml_content(text, base_dir=str(app))

    command = compose["services"]["abi"]["command"][-1]
    setup = command.split(" && exec ")[0].replace("$$", "$")
    setup = setup.replace("/var/lib/abi-secrets", str(volume))
    subprocess.run(["sh", "-c", setup], cwd=app, check=True)
    subprocess.run(["sh", "-c", setup], cwd=app, check=True)  # every restart

    configuration = EngineConfiguration.from_yaml_content(text, base_dir=str(app))

    assert configuration is not None
    assert (volume / ".env").read_text(encoding="utf-8").count(
        "OPENROUTER_API_KEY="
    ) == 1
    # A value saved later is kept by the next restart.
    (volume / ".env").write_text("OPENROUTER_API_KEY=saved\n", encoding="utf-8")
    subprocess.run(["sh", "-c", setup], cwd=app, check=True)
    assert (
        "OPENROUTER_API_KEY=saved\n"
        == (volume / ".env").read_text(encoding="utf-8").split("\n", 1)[0] + "\n"
    )
