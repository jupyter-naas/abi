"""Hermetic fixtures for X agent tests (no initialized X ABIModule required)."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.tools import StructuredTool
from naas_abi_core.modules.templatablesparqlquery import (
    ABIModule as TemplatableSparqlQueryABIModule,
)
from unittest.mock import MagicMock


def _mock_sparql_tool(name: str) -> StructuredTool:
    return StructuredTool.from_function(
        func=lambda **kwargs: [],
        name=name,
        description=f"mock {name}",
    )


class _StubTemplatableSparqlModule(TemplatableSparqlQueryABIModule):
    def get_tools(self, tool_names: list[str]) -> list[StructuredTool]:
        return [_mock_sparql_tool(name) for name in tool_names]


@pytest.fixture(autouse=True)
def _mock_x_abi_module(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_templatable = _StubTemplatableSparqlModule.__new__(_StubTemplatableSparqlModule)

    mock_engine = MagicMock()
    mock_engine.modules = {
        "naas_abi_core.modules.templatablesparqlquery": mock_templatable,
    }
    mock_engine.services.model_registry.get_default_chat_model.return_value = (
        FakeListChatModel(responses=["ok"])
    )

    mock_module = MagicMock()
    mock_module.engine = mock_engine

    monkeypatch.setattr(
        "naas_abi_marketplace.applications.x.ABIModule.get_instance",
        lambda: mock_module,
    )
