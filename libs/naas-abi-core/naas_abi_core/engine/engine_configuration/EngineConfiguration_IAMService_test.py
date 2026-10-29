import re
from pathlib import Path

import pytest
import yaml
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_IAMService import (
    IAMServiceConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.services.iam.IAMService import IAMService
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[5]


def _configuration(iam_block: str) -> EngineConfiguration:
    return EngineConfiguration.from_yaml_content(f"""
api: {{}}
global_config:
  ai_mode: local
modules: []
services:
  secret:
    secret_adapters: []
{iam_block}
""")


def test_defaults_enforce_policies_on_sqlite():
    configuration = IAMServiceConfiguration()
    assert configuration.authorizer == "policy"
    assert configuration.store.adapter == "sqlite"
    assert configuration.store.path == "storage/iam/iam.sqlite"
    assert configuration.local_storage() == "SQLite at storage/iam/iam.sqlite"
    assert _configuration("").services.iam.authorizer == "policy"


def test_the_engine_loads_a_bootstrapped_iam_first(tmp_path):
    configuration = _configuration(f"""
  iam:
    store:
      adapter: sqlite
      path: {tmp_path / "iam.sqlite"}
""")
    services = EngineServiceLoader(configuration).load_services({})
    assert services.iam_available()
    iam = services.iam
    assert isinstance(iam, IAMService)
    assert iam.authorizer.name == "policy"
    assert iam.store.find_service_account("engine") is not None
    with as_service_account("engine"):
        # The engine holds the kernel services, not whatever a policy could name.
        assert iam.authorize(
            "triple_store:DropGraph", "abi:triple_store:graph/g"
        ).allowed
        assert not iam.authorize("anything:Goes", "abi:any:thing/x").allowed
    with as_service_account("someone-else-unknown"):
        assert not iam.authorize("iam:CreatePolicy", "abi:iam:policy/p").allowed
    assert (tmp_path / "iam.sqlite").exists()


def test_allow_all_is_an_explicit_opt_out_that_warns():
    from naas_abi_core import logger

    configuration = _configuration("""
  iam:
    store:
      adapter: memory
    authorizer: allow_all
""")
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        iam = configuration.services.iam.load()
    finally:
        logger.remove(sink)
    assert iam.authorizer.name == "allow_all"
    assert any("allow_all" in m for m in messages)


@pytest.mark.parametrize(
    "block",
    [
        "authorizer: none",
        "authorizer: allow-all",
        "store: {adapter: postgres}",
        "store: {adapter: mongodb}",
        "tokens: {access_ttl_seconds: 601}",
        "cache_ttl_seconds: 120",
        "unknown: true",
    ],
)
def test_invalid_blocks_are_refused(block):
    with pytest.raises(ValidationError):
        IAMServiceConfiguration.model_validate(yaml.safe_load(block))


def test_postgres_takes_a_dsn_and_a_schema():
    configuration = IAMServiceConfiguration.model_validate(
        {
            "store": {
                "adapter": "postgres",
                "dsn": "postgresql://u:p@db:5432/abi",
                "schema": "abi_iam",
            }
        }
    )
    assert configuration.store.schema_name == "abi_iam"
    assert configuration.local_storage() is None


@pytest.mark.parametrize(
    "path, adapter",
    [
        ("config.yaml", "sqlite"),
        ("config.local.yaml", "postgres"),
        ("config.remote.yaml", "postgres"),
        (
            "libs/naas-abi-cli/naas_abi_cli/cli/new/templates/project/config.yaml",
            "sqlite",
        ),
        (
            "libs/naas-abi-cli/naas_abi_cli/cli/new/templates/project/config.local.yaml",
            "postgres",
        ),
        (
            "libs/naas-abi-cli/naas_abi_cli/cli/new/templates/project/config.remote.yaml",
            "postgres",
        ),
    ],
)
def test_shipped_configurations_choose_the_store_and_enforce(path, adapter):
    # Project templates are Jinja themselves: their {% raw %} sections hold
    # the configuration's own {{ secret.X }} placeholders.
    text = re.sub(r"{%-? *(end)?raw *-?%}", "", (ROOT / path).read_text())
    services = EngineConfiguration.render_without_secrets(text, base_dir=str(ROOT)).get(
        "services", {}
    )
    block = IAMServiceConfiguration.model_validate(
        {
            **services["iam"],
            "store": {**services["iam"]["store"], "dsn": "postgresql://x"},
        }
        if adapter == "postgres"
        else services["iam"]
    )
    assert block.store.adapter == adapter
    assert block.authorizer == "policy"
