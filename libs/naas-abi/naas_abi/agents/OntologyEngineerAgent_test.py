from types import SimpleNamespace

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from naas_abi_core.models.Model import ChatModel

from naas_abi.agents.OntologyEngineerAgent import OntologyEngineerAgent, create_agent


class _DummyChatModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "dummy-chat-model"

    @property
    def _identifying_params(self) -> dict:
        return {}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


def _fake_chat_model(*_args, **_kwargs) -> ChatModel:
    return ChatModel(model_id="dummy", provider="dummy", model=_DummyChatModel())


def _fake_abimodule() -> type:
    return type(
        "_FakeABIModule",
        (),
        {
            "get_instance": classmethod(
                lambda cls: SimpleNamespace(
                    engine=SimpleNamespace(
                        modules={
                            "naas_abi_marketplace.ai.chatgpt": SimpleNamespace(
                                configuration=SimpleNamespace(openai_api_key="test-key")
                            )
                        }
                    )
                )
            )
        },
    )


def test_get_bfo_7_buckets_ontology_is_loaded_from_source_file():
    ontology = OntologyEngineerAgent.get_bfo_7_buckets_ontology()

    assert "bfo:BFO_0000015 a owl:Class" in ontology
    assert "bfo:BFO_0000040 a owl:Class" in ontology
    assert "bfo:BFO_0000057 a owl:ObjectProperty" in ontology


def test_new_builds_grounded_prompt_and_disables_default_intents(monkeypatch):
    monkeypatch.setattr("naas_abi.ABIModule", _fake_abimodule(), raising=False)
    monkeypatch.setattr(OntologyEngineerAgent, "get_model", staticmethod(_fake_chat_model))

    agent = OntologyEngineerAgent.New()
    prompt = agent.configuration.get_system_prompt([])

    assert isinstance(agent, OntologyEngineerAgent)
    assert "[BFO_7_BUCKETS_ONTOLOGY]" not in prompt
    assert "BFO 7 Buckets framework" in prompt
    assert "skos:definition" in prompt
    assert "skos:example" in prompt
    assert "rdfs:domain" in prompt
    assert "rdfs:range" in prompt
    assert len(agent.intents) == 0


def test_create_agent_uses_class_new(monkeypatch):
    monkeypatch.setattr("naas_abi.ABIModule", _fake_abimodule(), raising=False)
    monkeypatch.setattr(OntologyEngineerAgent, "get_model", staticmethod(_fake_chat_model))

    agent = create_agent()

    assert isinstance(agent, OntologyEngineerAgent)
