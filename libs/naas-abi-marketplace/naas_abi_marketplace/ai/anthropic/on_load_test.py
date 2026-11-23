"""Tests that the anthropic module registers its models + provider factory
against the ModelRegistry during on_load."""

from __future__ import annotations

import os
from typing import cast

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.models.Model import CanonicalModelId, ChatModel, ModelProvider
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def _make_module(api_key: str = "test-key-not-used"):
    from naas_abi_marketplace.ai.anthropic import ABIModule

    registry = ModelRegistryService(default_chat_model="claude-sonnet-4.5")
    services = IEngine.Services(model_registry=registry)
    engine = _DummyEngine(services=services)
    proxy = EngineProxy(
        engine=cast(IEngine, engine),
        module_name="naas_abi_marketplace.ai.anthropic",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        anthropic_api_key=api_key,
    )
    module = ABIModule(proxy, config)
    return module, registry


# Canonical ids that ship a concrete file under models/.
_SHIPPED = {
    CanonicalModelId.CLAUDE_FABLE_5_1,
    CanonicalModelId.CLAUDE_OPUS_5_5,
    CanonicalModelId.CLAUDE_SONNET_5_5,
    CanonicalModelId.CLAUDE_HAIKU_5_5,
    CanonicalModelId.CLAUDE_FABLE_5,
    CanonicalModelId.CLAUDE_OPUS_4_8,
    CanonicalModelId.CLAUDE_SONNET_5,
    CanonicalModelId.CLAUDE_SONNET_4_5,
    CanonicalModelId.CLAUDE_SONNET_4,
    CanonicalModelId.CLAUDE_HAIKU_4_5,
}

# Claude 5.5 generation: (canonical id, API model id, effort, $/token in, out).
_CLAUDE_5_5_GENERATION = [
    (
        CanonicalModelId.CLAUDE_OPUS_5_5,
        "claude-opus-5-5",
        "high",
        "0.000004",
        "0.00002",
    ),
    (
        CanonicalModelId.CLAUDE_SONNET_5_5,
        "claude-sonnet-5-5",
        "high",
        "0.000002",
        "0.00001",
    ),
    (
        CanonicalModelId.CLAUDE_HAIKU_5_5,
        "claude-haiku-5-5",
        "medium",
        "0.0000001",
        "0.0000005",
    ),
    (
        CanonicalModelId.CLAUDE_FABLE_5_1,
        "claude-fable-5-1",
        "high",
        "0.00001",
        "0.00005",
    ),
]


def test_on_load_registers_shipped_claude_models() -> None:
    module, registry = _make_module()
    module.on_load()

    registered = set(registry.list_canonical_ids())
    assert {str(c) for c in _SHIPPED} <= registered


@pytest.mark.parametrize(
    "canonical_id,model_id,effort,prompt_price,completion_price",
    _CLAUDE_5_5_GENERATION,
)
def test_claude_5_5_generation_catalog_entry(
    canonical_id: CanonicalModelId,
    model_id: str,
    effort: str,
    prompt_price: str,
    completion_price: str,
) -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_chat_model(canonical_id)
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.ANTHROPIC
    assert got.model_id == model_id
    assert got.context_window == 1_000_000
    assert got.pricing is not None
    assert got.pricing["prompt"] == prompt_price
    assert got.pricing["completion"] == completion_price
    assert got.top_provider is not None
    assert got.top_provider["max_completion_tokens"] == 128_000


@pytest.mark.parametrize(
    "canonical_id,model_id,effort,prompt_price,completion_price",
    _CLAUDE_5_5_GENERATION,
)
def test_claude_5_5_generation_request_payload_respects_api_constraints(
    canonical_id: CanonicalModelId,
    model_id: str,
    effort: str,
    prompt_price: str,
    completion_price: str,
) -> None:
    module, registry = _make_module()
    module.on_load()

    chat = registry.get_chat_model(canonical_id).model
    payload = chat._get_request_payload("hello")  # type: ignore[attr-defined]

    assert payload["model"] == model_id
    # Sampling parameters and budget_tokens are a 400 on these models.
    for key in ("temperature", "top_p", "top_k"):
        assert key not in payload
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"] == {"effort": effort}
    # langchain's 1024 default would let thinking eat the visible answer.
    assert payload["max_tokens"] == 16000


def test_off_catalog_factory_sends_no_sampling_parameters() -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_chat_model(
        "claude-future-model", provider=ModelProvider.ANTHROPIC
    )
    payload = got.model._get_request_payload("hello")  # type: ignore[attr-defined]
    for key in ("temperature", "top_p", "top_k"):
        assert key not in payload
    assert payload["max_tokens"] == 8192


def test_on_load_makes_get_chat_model_work_for_default() -> None:
    module, registry = _make_module()
    module.on_load()

    # validate_defaults should pass since the default is now registered.
    registry.validate_defaults()

    got = registry.get_default_chat_model()
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.ANTHROPIC


def test_on_load_registers_anthropic_chat_provider_for_off_catalog() -> None:
    module, registry = _make_module()
    module.on_load()

    # A canonical id not registered should still resolve via the anthropic
    # chat factory when caller pins the provider.
    got = registry.get_chat_model(
        "claude-future-model", provider=ModelProvider.ANTHROPIC
    )
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.ANTHROPIC
    assert got.model_id == "claude-future-model"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Live smoke test: set ANTHROPIC_API_KEY to run it.",
)
def test_live_opus_5_5_tool_call_then_second_turn() -> None:
    """One tool round trip plus a second user turn on Opus 5.5, without a 400.

    The second request replays the first turn's thinking blocks unchanged,
    which is what preserved thinking requires.
    """
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.tools import tool

    @tool
    def get_invoice_total(invoice_id: str) -> str:
        """Return the total amount of an invoice, in euros."""
        return "1234.50"

    module, registry = _make_module(api_key=os.environ["ANTHROPIC_API_KEY"])
    module.on_load()
    chat = registry.get_chat_model(CanonicalModelId.CLAUDE_OPUS_5_5).model
    llm = chat.bind_tools([get_invoice_total])

    messages: list = [
        HumanMessage(content="What is the total of invoice INV-42? Use the tool.")
    ]
    first = llm.invoke(messages)
    assert first.tool_calls, first
    messages.append(first)
    for call in first.tool_calls:
        messages.append(
            ToolMessage(
                content=get_invoice_total.invoke(call["args"]),
                tool_call_id=call["id"],
            )
        )
    answer = llm.invoke(messages)
    assert answer.response_metadata.get("stop_reason") != "refusal"
    messages.append(answer)

    messages.append(HumanMessage(content="And in cents?"))
    second = llm.invoke(messages)
    assert second.response_metadata.get("stop_reason") in {"end_turn", "tool_use"}
