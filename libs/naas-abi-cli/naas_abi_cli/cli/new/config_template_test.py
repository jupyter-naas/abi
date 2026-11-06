"""Render checks for the generated project config templates.

The ``code`` feature flag (in-app coding workspaces) must only be enabled when a
project is generated with the coding stack (``--with-coding`` → ``include_coding``),
and only for workspace admins (owner + admin) — never for members/viewers.

The AI defaults are pinned here too: every generated config must boot on the
OpenRouter gateway with Gemma 4 for chat and text-embedding-3-small for
embeddings. The engine validates ``model_registry`` defaults against the loaded
modules after boot, so a default naming a model no provider registers is a
fail-fast crash in every new project.
"""

from __future__ import annotations

import os

import jinja2
import pytest
import yaml

import naas_abi_cli

_TEMPLATES_DIR = os.path.join(
    os.path.dirname(naas_abi_cli.__file__), "cli/new/templates/project"
)
_TEMPLATE = os.path.join(_TEMPLATES_DIR, "config.local.yaml")

# Every generated config points at these; the openrouter module registers both.
_DEFAULT_CHAT_MODEL = "gemma-4-26b-a4b-it"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_ALL_CONFIGS = ("config.yaml", "config.local.yaml", "config.remote.yaml")
# config.remote.yaml seeds no users — it expects them to be created by an
# operator, so only these two carry the bootstrap admin.
_CONFIGS_SEEDING_USERS = ("config.yaml", "config.local.yaml")

_BASE_VALUES = {
    "project_name": "Demo",
    "project_name_snake": "demo",
    "project_name_pascal": "Demo",
    "base_domain": "localhost",
    "public_web_host": "localhost",
    "public_api_host": "api.localhost",
}


def _render(filename: str, *, include_coding: bool = False, nats: bool = True) -> dict:
    src = open(os.path.join(_TEMPLATES_DIR, filename), encoding="utf-8").read()
    rendered = jinja2.Template(src).render(
        {**_BASE_VALUES, "include_coding": include_coding, "nats": nats}
    )
    return yaml.safe_load(rendered)  # also asserts the render is valid YAML


def _render_feature_flags(*, include_coding: bool) -> dict:
    doc = _render("config.local.yaml", include_coding=include_coding)
    return doc["modules"][0]["config"]["nexus_config"]["feature_flags"]


def _enabled_modules(doc: dict) -> set[str]:
    return {m["module"] for m in doc["modules"] if m.get("enabled")}


def test_code_enabled_when_coding_included() -> None:
    ff = _render_feature_flags(include_coding=True)

    assert "code" in ff["enabled_features"]
    # No role brings a feature: a policy does.
    assert set(ff) == {"enabled_features"}


def test_code_absent_when_coding_not_included() -> None:
    ff = _render_feature_flags(include_coding=False)

    assert "code" not in ff["enabled_features"]
    assert set(ff) == {"enabled_features"}


@pytest.mark.parametrize("filename", _ALL_CONFIGS)
def test_openrouter_is_the_only_ai_provider_enabled(filename: str) -> None:
    doc = _render(filename)
    enabled = _enabled_modules(doc)

    assert "naas_abi_marketplace.ai.openrouter" in enabled
    # Ollama and the other providers ship commented out — enabling two AI
    # modules would make the registry defaults ambiguous.
    assert "naas_abi_marketplace.ai.ollama" not in enabled
    assert "naas_abi_marketplace.ai.chatgpt" not in enabled
    assert doc["global_config"]["ai_mode"] == "cloud"


@pytest.mark.parametrize("filename", _ALL_CONFIGS)
def test_model_registry_defaults_are_the_cheap_openrouter_pair(filename: str) -> None:
    registry = _render(filename)["services"]["model_registry"]

    assert registry["default_chat_model"] == _DEFAULT_CHAT_MODEL
    assert registry["default_embedding_model"] == _DEFAULT_EMBEDDING_MODEL


@pytest.mark.parametrize("filename", _CONFIGS_SEEDING_USERS)
def test_seeded_admin_is_a_superadmin(filename: str) -> None:
    """The bootstrap admin owns the seeded org and workspace, but org/workspace
    ownership does not grant platform-wide admin (admin console, live event
    stream) — that is the separate ``is_superadmin`` flag, and without it a new
    project has no account that can reach those screens."""
    nexus_config = next(
        m for m in _render(filename)["modules"] if m["module"] == "naas_abi"
    )["config"]["nexus_config"]
    users = nexus_config["users"]

    assert users, f"{filename} seeds no users"
    assert all(u["is_superadmin"] for u in users)
    # The seeded admin is also the org/workspace owner; the two must not drift.
    org = nexus_config["organizations"][0]
    assert org["owner_email"] in {u["email"] for u in users}


@pytest.mark.parametrize("filename", _ALL_CONFIGS)
def test_tool_binding_agents_are_pinned_to_the_default_chat_model(
    filename: str,
) -> None:
    """AbiAgent and OntologyEngineerAgent default to claude-sonnet-5 upstream,
    which the openrouter module does not register — leaving them unpinned
    crashes a generated project at boot."""
    naas_abi = next(
        m for m in _render(filename)["modules"] if m["module"] == "naas_abi"
    )["config"]

    assert naas_abi["abi_agent_model"] == _DEFAULT_CHAT_MODEL
    assert naas_abi["ontology_engineer_model"] == _DEFAULT_CHAT_MODEL


def test_default_config_uses_sqlite_ducklake() -> None:
    dataset = _render("config.yaml")["services"]["dataset"]["dataset_adapter"]

    assert dataset == {
        "adapter": "ducklake",
        "config": {
            "catalog": "sqlite:storage/datasets.sqlite",
            "data_path": "storage/datasets/",
        },
    }


def test_local_config_uses_dedicated_postgres_ducklake_catalog() -> None:
    dataset = _render("config.local.yaml")["services"]["dataset"]["dataset_adapter"]

    assert dataset["adapter"] == "ducklake"
    assert dataset["config"]["catalog"].endswith("@postgres:5432/ducklake")
    assert dataset["config"]["data_path"] == "storage/datasets/"


def test_document_config_uses_sqlite_locally_and_existing_postgres_database_in_stack() -> (
    None
):
    document = _render("config.yaml")["services"]["document"]["document_adapter"]
    assert document == {
        "adapter": "sqlite",
        "config": {"path": "storage/documents.sqlite"},
    }
    document = _render("config.local.yaml")["services"]["document"]["document_adapter"]
    assert document["adapter"] == "postgresql"
    assert document["config"]["dsn"].endswith("@postgres:5432/{{ secret.POSTGRES_DB }}")


# =============================================================================
# NATS mode (the default) and the classic project (--without-nats).
# =============================================================================

# Where each config's engine finds the broker, logged in as the user `abi`.
_NATS_HOSTS = {
    "config.yaml": "@127.0.0.1:4222",  # abi dev up overlays its own port
    "config.local.yaml": "@nats:4222",  # the Compose service
}


@pytest.mark.parametrize("filename", _ALL_CONFIGS)
def test_nats_configs_pass_the_engine_validation(filename: str) -> None:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        NATSConfiguration,
    )

    nats = NATSConfiguration.model_validate(_render(filename)["nats"])

    # Exactly one engine hosts discovery: the project's, under its own name.
    assert nats.discovery is not None
    assert nats.discovery.project == "demo"
    # Outlives an engine restart, so remote modules renew instead of dropping out.
    assert nats.discovery.lease_seconds == 180
    # No signing secret: the engine answers the broker's auth callout.
    assert nats.auth_callout is not None
    assert nats.auth_callout.issuer_seed == "{{ secret.NATS_AUTH_CALLOUT_SEED }}"


@pytest.mark.parametrize("filename", sorted(_NATS_HOSTS))
def test_nats_engines_log_in_as_the_engine_and_auth_users(filename: str) -> None:
    nats = _render(filename)["nats"]

    assert nats["nats_url"] == (
        "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}" + _NATS_HOSTS[filename]
    )
    assert nats["auth_callout"]["nats_url"] == (
        "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}" + _NATS_HOSTS[filename]
    )
    assert nats["monitoring_url"].endswith(":8222")


def test_the_remote_config_reads_the_broker_url_from_a_secret() -> None:
    nats = _render("config.remote.yaml")["nats"]
    assert nats["nats_url"] == "{{ secret.NATS_URL }}"
    assert nats["auth_callout"]["nats_url"] == "{{ secret.NATS_AUTH_URL }}"


@pytest.mark.parametrize("filename", _ALL_CONFIGS)
def test_nats_configs_leave_the_bus_to_jetstream(filename: str) -> None:
    """In NATS mode the engine refuses any bus adapter but nats_jetstream."""
    services = _render(filename)["services"]

    assert "bus" not in services
    # Cache tiers must not mix local and nats_rpc; the templates declare none.
    assert "cache" not in services


@pytest.mark.parametrize("filename", _ALL_CONFIGS)
def test_classic_configs_keep_their_bus_and_no_nats(filename: str) -> None:
    doc = _render(filename, nats=False)

    assert "nats" not in doc
    assert doc["services"]["bus"]["bus_adapter"]["adapter"] in {
        "python_queue",
        "rabbitmq",
    }


def test_docker_configs_make_the_builtin_idp_the_default_provider() -> None:
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_Identity import (
        IdentityConfiguration,
    )

    for filename in ("config.local.yaml", "config.remote.yaml"):
        block = _render(filename)["identity"]
        # The two secrets the config names are in .env (the deploy generates them).
        block["providers"][0]["issuer"] = block["providers"][0]["issuer"].replace(
            "{{ secret.NEXUS_API_URL }}", "https://api.localhost"
        )
        block["providers"][0]["client_secret"] = "s" * 32
        config = IdentityConfiguration.model_validate(block)
        provider = config.providers[0]
        assert config.default_provider == provider.name == "builtin", filename
        assert provider.provisioning == "builtin" and provider.issuer.endswith("/idp")
        assert "groups" in provider.scopes and "offline_access" in provider.scopes
        assert "identity" not in _render(filename, nats=False), filename


def test_the_dev_config_names_no_provider_so_abi_dev_up_adds_the_builtin_one() -> None:
    # Active YAML would need ABI_IDP_ISSUER, which only `abi dev up` sets; the
    # block is a comment, and the dev overlay supplies it.
    assert "identity" not in _render("config.yaml")
    assert (
        "identity:"
        in open(os.path.join(_TEMPLATES_DIR, "config.yaml"), encoding="utf-8").read()
    )
