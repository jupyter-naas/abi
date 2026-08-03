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

_BASE_VALUES = {
    "project_name": "Demo",
    "project_name_snake": "demo",
    "project_name_pascal": "Demo",
    "base_domain": "localhost",
    "public_web_host": "localhost",
    "public_api_host": "api.localhost",
}


def _render(filename: str, *, include_coding: bool = False) -> dict:
    src = open(os.path.join(_TEMPLATES_DIR, filename), encoding="utf-8").read()
    rendered = jinja2.Template(src).render(
        {**_BASE_VALUES, "include_coding": include_coding}
    )
    return yaml.safe_load(rendered)  # also asserts the render is valid YAML


def _render_feature_flags(*, include_coding: bool) -> dict:
    doc = _render("config.local.yaml", include_coding=include_coding)
    return doc["modules"][0]["config"]["nexus_config"]["feature_flags"]


def _enabled_modules(doc: dict) -> set[str]:
    return {m["module"] for m in doc["modules"] if m.get("enabled")}


def test_code_enabled_for_admins_when_coding_included() -> None:
    ff = _render_feature_flags(include_coding=True)

    assert "code" in ff["enabled_features"]
    assert "code" in ff["role_baseline"]["owner"]
    assert "code" in ff["role_baseline"]["admin"]
    # Members and viewers never get the coding section by default.
    assert "code" not in ff["role_baseline"]["member"]
    assert "code" not in ff["role_baseline"]["viewer"]


def test_code_absent_when_coding_not_included() -> None:
    ff = _render_feature_flags(include_coding=False)

    assert "code" not in ff["enabled_features"]
    for role in ("owner", "admin", "member", "viewer"):
        assert "code" not in ff["role_baseline"][role]


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
