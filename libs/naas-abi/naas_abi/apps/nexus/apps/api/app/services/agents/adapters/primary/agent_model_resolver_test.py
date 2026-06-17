from __future__ import annotations

import ast

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
    agent_model_resolver as resolver,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
    ModelCatalogEntry,
)


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def _entry(canonical_id: str, model_id: str, module_path: str) -> ModelCatalogEntry:
    return ModelCatalogEntry(
        canonical_id=canonical_id,
        model_id=model_id,
        provider="anthropic",
        module_path="naas_abi_marketplace.ai.anthropic",
        provider_id="anthropic",
        file=f"/x/{module_path.replace('.', '/')}.py",
        name=None,
        description=None,
        image=None,
        context_window=None,
    )


def test_module_level_model_constant() -> None:
    tree = _parse('MODEL = "gpt-4o"\n')
    assert resolver._module_level_model(tree) == "gpt-4o"


def test_module_level_model_id_constant() -> None:
    tree = _parse('MODEL_ID = "gpt-4.1-mini"\n')
    assert resolver._module_level_model(tree) == "gpt-4.1-mini"


def test_module_level_model_absent() -> None:
    assert resolver._module_level_model(_parse("X = 1\n")) is None


def test_imported_model_resolves_via_catalog(monkeypatch) -> None:
    module_path = "naas_abi_marketplace.ai.anthropic.models.claude_sonnet_3_7"
    entry = _entry("claude-sonnet-3.7", "claude-3-7-sonnet-20250219", module_path)

    def fake_lookup(path: str) -> ModelCatalogEntry | None:
        return entry if path == module_path else None

    monkeypatch.setattr(resolver, "find_catalog_model_by_module_path", fake_lookup)

    tree = _parse(f"from {module_path} import model\n")
    assert resolver._imported_model(tree) == "claude-sonnet-3.7"


def test_imported_model_ignores_non_model_imports(monkeypatch) -> None:
    monkeypatch.setattr(
        resolver, "find_catalog_model_by_module_path", lambda _p: None
    )
    tree = _parse("from naas_abi_marketplace.ai.anthropic.models.x import something\n")
    assert resolver._imported_model(tree) is None


def test_config_model_reads_engine_config(monkeypatch) -> None:
    monkeypatch.setattr(
        resolver,
        "_config_value",
        lambda name: "claude-sonnet-4.6" if name == "abi_agent_model" else None,
    )
    tree = _parse("x = abi_module.configuration.abi_agent_model\n")
    assert resolver._config_model(tree) == "claude-sonnet-4.6"


def test_config_model_skips_provider_attribute(monkeypatch) -> None:
    monkeypatch.setattr(resolver, "_config_value", lambda name: "should-not-be-used")
    tree = _parse("x = abi_module.configuration.abi_agent_provider\n")
    assert resolver._config_model(tree) is None


def test_resolve_canonicalizes_raw_id(monkeypatch) -> None:
    entry = _entry("claude-sonnet-3.7", "claude-3-7-sonnet-20250219", "x")
    monkeypatch.setattr(resolver, "_raw_model_id", lambda _c: "claude-3-7-sonnet-20250219")
    monkeypatch.setattr(
        resolver,
        "find_catalog_model",
        lambda raw: entry if raw == "claude-3-7-sonnet-20250219" else None,
    )

    class FakeAgent:
        pass

    assert resolver.resolve_agent_model_id(FakeAgent) == "claude-sonnet-3.7"


def test_resolve_returns_raw_when_not_in_catalog(monkeypatch) -> None:
    monkeypatch.setattr(resolver, "_raw_model_id", lambda _c: "mystery-model")
    monkeypatch.setattr(resolver, "find_catalog_model", lambda _raw: None)

    class FakeAgent:
        pass

    assert resolver.resolve_agent_model_id(FakeAgent) == "mystery-model"


def test_resolve_returns_none_when_no_candidate(monkeypatch) -> None:
    monkeypatch.setattr(resolver, "_raw_model_id", lambda _c: None)

    class FakeAgent:
        pass

    assert resolver.resolve_agent_model_id(FakeAgent) is None


def test_class_attr_model_prefers_string() -> None:
    class WithModel:
        model = "gpt-5.3-codex"

    class WithoutModel:
        pass

    assert resolver._class_attr_model(WithModel) == "gpt-5.3-codex"
    assert resolver._class_attr_model(WithoutModel) is None
