"""The ABI repository's own setup runs on NATS, like a generated project.

Its `config.yaml` (`abi dev up`) and `config.local.yaml` (`abi stack start`)
have a `nats:` block, and its docker-compose.yml keeps Dagster and RabbitMQ
behind the `legacy` profile.
"""

import importlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)

from naas_abi_cli.cli.deploy.local import project_uses_nats

# The modules, not the click groups naas_abi_cli.cli exports under these names.
dev = importlib.import_module("naas_abi_cli.cli.dev")
stack = importlib.import_module("naas_abi_cli.cli.stack")

REPO_ROOT = Path(__file__).resolve().parents[4]
LEGACY_SERVICES = {"dagster", "rabbitmq"}
NATS_SECRETS = {
    "NATS_ABI_PASSWORD": "nats-abi-password-for-the-test",
    "NATS_JWT_SECRET": "j" * 48,
}


def _render(config: Path, monkeypatch, tmp_path: Path) -> EngineConfiguration:
    """The config as the engine loads it, every secret it names set."""
    text = config.read_text(encoding="utf-8")
    names = set(re.findall(r"secret\.([A-Za-z_][A-Za-z0-9_]*)", text))
    for name in names:
        monkeypatch.setenv(name, NATS_SECRETS.get(name, "x"))
    # The dotenv adapter reads .env from the working directory: an empty one.
    (tmp_path / ".env").write_text("")
    monkeypatch.chdir(tmp_path)
    return EngineConfiguration.from_yaml(str(config))


@pytest.mark.parametrize(
    ("name", "host"), [("config.yaml", "127.0.0.1"), ("config.local.yaml", "nats")]
)
def test_the_repository_config_runs_on_nats(
    name: str, host: str, monkeypatch, tmp_path: Path
) -> None:
    config = _render(REPO_ROOT / name, monkeypatch, tmp_path)

    assert config.nats is not None
    assert config.nats.nats_url == (
        f"nats://abi:{NATS_SECRETS['NATS_ABI_PASSWORD']}@{host}:4222"
    )
    assert config.nats.jwt_secret == NATS_SECRETS["NATS_JWT_SECRET"]
    assert config.nats.discovery is not None
    assert config.nats.discovery.project == "abi"
    # The bus is JetStream: an explicit bus block would have to name it.
    assert "bus" not in config.services.model_fields_set


def test_the_repository_names_its_nats_secrets_in_env_example() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    for key in ("NATS_ABI_PASSWORD", "NATS_MODULE_PASSWORD", "NATS_JWT_SECRET"):
        assert re.search(rf"^#? ?{key}=", example, re.MULTILINE), key


def test_abi_dev_up_runs_the_repository_on_nats(monkeypatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.delenv("ENV", raising=False)

    assert dev._project_declares_nats()
    assert dev._services_for((), with_nats=True) == [
        "oxigraph",
        "nats",
        "api",
        "nexus-web",
    ]


def test_abi_stack_start_seeds_the_repository_nats_secrets() -> None:
    assert project_uses_nats(str(REPO_ROOT)) is True


def _services(profiles: tuple[str, ...] = ()) -> dict:
    """The repository's compose services that run with these profiles on."""
    services = yaml.safe_load(
        (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )["services"]
    return {
        name: service
        for name, service in services.items()
        if not service.get("profiles")
        or set(service["profiles"]) & set(profiles)
    }


def test_the_repository_stack_runs_on_nats() -> None:
    services = _services()

    assert "nats" in services
    assert services["abi"]["depends_on"]["nats"] == {"condition": "service_healthy"}
    assert not LEGACY_SERVICES & set(services)
    for name, service in services.items():
        assert not LEGACY_SERVICES & set(service.get("depends_on", {})), name


def test_dagster_and_rabbitmq_are_behind_the_legacy_profile() -> None:
    assert LEGACY_SERVICES <= set(_services(("legacy",)))
    for name in LEGACY_SERVICES:
        assert _services(("legacy",))[name]["profiles"] == ["legacy"]
    # Next to an engine on NATS, Dagster's engine never serves.
    assert "ABI_ENGINE_ROLE=client" in _services(("legacy",))["dagster"]["environment"]


def test_the_legacy_overlay_reaches_the_engines() -> None:
    """`abi stack start --legacy` hands its overlay to abi and dagster."""
    passed = f"ABI_CONFIG_OVERLAY=${{{stack.STACK_OVERLAY_ENV}:-}}"
    services = _services(("legacy",))

    for name in ("abi", "dagster"):
        assert passed in services[name]["environment"], name


def _compose_services(tmp_path: Path, *profiles: str) -> set[str]:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    variables = sorted(set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", text)))
    env_file = tmp_path / "compose.env"
    # Placeholder values (ports included): only the service list is read.
    env_file.write_text("".join(f"{name}=1\n" for name in variables))
    command = ["docker", "compose", "--env-file", str(env_file)]
    for profile in profiles:
        command += ["--profile", profile]
    result = subprocess.run(
        [*command, "config", "--services"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


@pytest.mark.skipif(
    shutil.which("docker") is None
    or subprocess.run(
        ["docker", "compose", "version"], capture_output=True, check=False
    ).returncode
    != 0,
    reason="needs docker compose",
)
def test_docker_compose_reads_the_legacy_profile(tmp_path: Path) -> None:
    default = _compose_services(tmp_path)
    legacy = _compose_services(tmp_path, "legacy")

    assert "nats" in default
    assert not LEGACY_SERVICES & default
    assert legacy - default == LEGACY_SERVICES
