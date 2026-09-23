from langchain_core.messages import AIMessage

from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.tests.scripted_chat_model import ScriptedChatModel
from naas_abi_core.services.agent_composer.AgentComposerFactory import (
    AgentComposerFactory,
)
from naas_abi_core.services.agent_composer.AgentComposerPort import AgentSpec
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)


def _models() -> ModelRegistryService:
    registry = ModelRegistryService(default_chat_model="default")
    registry.register(
        "default",
        ChatModel(
            model_id="default",
            provider="test",
            model=ScriptedChatModel.from_script([AIMessage(content="hi")]),
        ),
    )
    return registry


def test_in_memory_composer_resolves_seeded_records():
    composer = AgentComposerFactory.InMemory(
        ToolRegistryService(), _models(), specs=[AgentSpec(name="a", prompt="A.")]
    )
    assert composer.compose("a").name == "a"


def test_file_system_composer_reads_a_directory(tmp_path):
    (tmp_path / "a.yaml").write_text("name: a\nprompt: A.\n")
    composer = AgentComposerFactory.FileSystem(
        ToolRegistryService(), _models(), tmp_path
    )
    assert composer.compose("a").invoke("hello") == "hi"


class _Engine:
    def __init__(self, services):
        self.services = services


class _SecretAdapter:
    def get(self, key, default=None):
        return {"TOKEN": "t"}.get(key, default)

    def set(self, key, value): ...
    def remove(self, key): ...
    def list(self):
        return {"TOKEN": "t"}


def test_from_engine_uses_the_engine_registries_and_secrets(tmp_path):
    (tmp_path / "a.yaml").write_text("name: a\nprompt: A.\n")
    tools = ToolRegistryService()
    engine = _Engine(
        IEngine.Services(
            model_registry=_models(),
            tool_registry=tools,
            secret=Secret([_SecretAdapter()]),
        )
    )
    composer = AgentComposerFactory.FromEngine(engine, records_directory=tmp_path)
    assert composer.compose("a").name == "a"
    assert composer._secrets.resolve("TOKEN") == "t"


def test_from_engine_without_a_secret_service():
    engine = _Engine(
        IEngine.Services(model_registry=_models(), tool_registry=ToolRegistryService())
    )
    composer = AgentComposerFactory.FromEngine(engine)
    assert composer._secrets is None
    assert composer.spec_repository is None
