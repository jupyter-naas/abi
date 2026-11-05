"""Fakes of the engine services for the modules' offline tests (no broker)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class EchoModel(BaseChatModel):
    """Answers ``reply`` and records the tools bound to it."""

    reply: str = "ok"
    tools: list = []

    @property
    def _llm_type(self) -> str:
        return "echo"

    def bind_tools(self, tools, **kwargs):
        self.tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(self.reply))])


class FakeEmbeddings:
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeRegistry:
    def __init__(self, reply: str = "ok") -> None:
        self.model = EchoModel(reply=reply)
        self.asked: list[str] = []

    async def get_default_chat_model(self):
        self.asked.append("")
        return SimpleNamespace(model=self.model)

    async def get_chat_model(self, name: str):
        self.asked.append(name)
        return SimpleNamespace(model=self.model)

    async def get_default_embedding_model(self):
        return SimpleNamespace(model=FakeEmbeddings())


class FakeDocuments:
    async def ensure_collection(self, request) -> None:
        return None


class FakeSecrets:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = dict(values)

    async def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[(prefix, key)] = content


def fake_engine(secrets: dict[str, str] | None = None, reply: str = "ok") -> Any:
    return SimpleNamespace(
        services=SimpleNamespace(
            model_registry=FakeRegistry(reply),
            document=FakeDocuments(),
            secret=FakeSecrets(secrets or {}),
            object_storage=MemoryStorage(),
        )
    )


def bound_tool_names(engine: Any) -> set[str]:
    """Names of the tools the agent bound to the engine's (fake) chat model."""
    return {tool.name for tool in engine.services.model_registry.model.tools}


def no_core_import(*modules: str) -> str | None:
    """Import ``modules`` in a fresh interpreter; the first core/marketplace
    module imported, or None. A remote module reaches the engine over NATS."""
    import os
    import subprocess
    import sys

    code = (
        f"import importlib, sys; [importlib.import_module(m) for m in {list(modules)!r}]; "
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('naas_abi_core', 'naas_abi', 'naas_abi_marketplace')]; "
        "print(bad[0] if bad else '')"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() or None


class FakeTripleStore:
    """In-memory named graphs (rdflib Dataset) behind the SDK facade's
    ``insert`` / ``query``: SPARQL runs for real, ``FROM <graph>`` included."""

    def __init__(self) -> None:
        from rdflib import Dataset

        self.dataset = Dataset()
        self.inserts: list[tuple[str, int]] = []

    async def insert(self, triples: Any, graph_name: Any) -> None:
        from rdflib import URIRef

        graph = self.dataset.graph(URIRef(str(graph_name)))
        for triple in triples:
            graph.add(triple)
        self.inserts.append((str(graph_name), len(triples)))

    async def query(self, query: str) -> Any:
        return self.dataset.query(query)
