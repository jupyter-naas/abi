"""Smoke test: semantic tool search with a real embedding model.

Runs against a local Ollama ``nomic-embed-text`` (the local-first default
embedding model) and skips when it is not reachable. Real models are fuzzy,
so it asserts a top-3 hit on paraphrases that avoid the tools' names.
"""

from __future__ import annotations

import os

import pytest
from langchain_core.tools import StructuredTool

from naas_abi_core.models.Model import EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    ToolPublisher,
)
from naas_abi_core.services.tool_registry.ToolRegistryFactory import ToolRegistryFactory

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("ABI_SMOKE_EMBEDDING_MODEL", "nomic-embed-text")

CATALOG = {
    "acme.github": [
        ("github_create_issue", "Create an issue in a GitHub repository."),
        ("github_list_pull_requests", "List the open pull requests of a repository."),
        ("github_get_repository_contributors", "Get the contributors of a repository."),
    ],
    "acme.mail": [
        ("gmail_send_email", "Send an email to one or more recipients."),
        ("gmail_search_inbox", "Search the messages in the user's inbox."),
    ],
    "acme.calendar": [
        ("calendar_create_event", "Create an event in the user's calendar."),
    ],
    "acme.weather": [
        ("weather_get_forecast", "Get the weather forecast for a city."),
    ],
    "acme.finance": [
        ("stripe_list_invoices", "List the invoices issued to a customer."),
        ("stripe_refund_payment", "Refund a customer payment."),
    ],
    "acme.storage": [
        ("drive_upload_file", "Upload a file to cloud storage."),
    ],
}


def _ollama_available() -> bool:
    try:
        import httpx

        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        names = {m["name"].split(":")[0] for m in response.json().get("models", [])}
        return EMBEDDING_MODEL.split(":")[0] in names
    except Exception:  # noqa: BLE001 - any failure means "not available"
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _ollama_available(),
        reason=f"Ollama with '{EMBEDDING_MODEL}' is not reachable at {OLLAMA_URL}",
    ),
]


@pytest.fixture(scope="module")
def registry():
    langchain_ollama = pytest.importorskip("langchain_ollama")

    models = ModelRegistryService(default_embedding_model="smoke-embeddings")
    models.register(
        "smoke-embeddings",
        EmbeddingModel(
            model_id=EMBEDDING_MODEL,
            provider="ollama",
            model=langchain_ollama.OllamaEmbeddings(
                model=EMBEDDING_MODEL, base_url=OLLAMA_URL
            ),
        ),
    )
    registry = ToolRegistryFactory.InMemory(models)
    for module, tools in CATALOG.items():
        publisher = ToolPublisher(module)
        for name, description in tools:
            publisher.add_tool(
                StructuredTool.from_function(
                    func=lambda **_: "ok", name=name, description=description
                )
            )
        publisher.publish_to(registry)
    return registry


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("open a ticket about a crash in our codebase", "github_create_issue"),
        ("will it rain in Paris tomorrow", "weather_get_forecast"),
        ("give a customer their money back", "stripe_refund_payment"),
        ("book a meeting with the team on Friday", "calendar_create_event"),
        ("write a message to my manager", "gmail_send_email"),
    ],
)
def test_paraphrased_requests_find_the_right_tool(registry, request_text, expected):
    names = [r.name for r in registry.search_tools(request_text, limit=3)]
    assert expected in names, f"{request_text!r} -> {names}"


def test_results_respect_the_limit(registry):
    assert len(registry.search_tools("anything about files", limit=2)) == 2
