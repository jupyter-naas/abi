import inspect
from types import SimpleNamespace

from naas_abi.agents import AppsAgent as apps_agent_module
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.AppsAgent import APPS_CODE_MAP, AppsAgent
from naas_abi.agents.feature import (
    DEFAULT_FEATURE_MODEL,
    FEATURE_GROUNDING_GUIDELINES,
)
from naas_abi.agents.tools.nexus_source_tools import PACKAGE_ROOT


def test_apps_agent_is_a_named_office_agent() -> None:
    assert AppsAgent.__name__ == "AppsAgent"
    assert AppsAgent.name == "Apps"
    assert "model_id" in inspect.signature(AppsAgent.New).parameters
    assert "not Abi" in AppsAgent.system_prompt


def test_apps_agent_is_the_only_agent_class_the_loader_sees() -> None:
    """ModuleAgentLoader registers every naas_abi Expose class in the module.

    The shared builder must stay a function, or it loads as a second agent.
    """
    from naas_abi_core.utils.Expose import Expose

    exposed = [
        value
        for value in vars(apps_agent_module).values()
        if isinstance(value, type)
        and issubclass(value, Expose)
        and value.__module__.split(".")[0] == "naas_abi"
    ]
    assert exposed == [AppsAgent]
    assert not hasattr(apps_agent_module, "create_agent")


def test_apps_agent_owns_apps_and_source_tools() -> None:
    names = {tool.name for tool in AppsAgent.get_tools()}
    assert {"list_workspace_apps", "get_app", "set_app_enabled"} <= names
    assert {"list_nexus_source", "read_nexus_source", "search_nexus_source"} <= names
    source = inspect.getsource(AppsAgent.get_tools)
    assert "nexus_admin_tools" not in source
    assert "slides_tools" not in source


def test_apps_prompt_is_grounded_in_code() -> None:
    prompt = AppsAgent.system_prompt
    assert FEATURE_GROUNDING_GUIDELINES in prompt
    assert "read_nexus_source" in prompt
    assert "<code_map>" in prompt
    assert "open_app_id" in prompt
    assert "Preserve the language" in prompt


def test_apps_code_map_paths_exist() -> None:
    """Every file the prompt tells the agent to read is real."""
    paths = [
        token.rstrip(":,")
        for line in APPS_CODE_MAP.splitlines()
        for token in line.replace("- ", " ").split()
        if token.startswith("naas_abi/") and not token.endswith("/")
    ]
    assert paths
    web_root = PACKAGE_ROOT / "apps/nexus/apps/web"
    for path in paths:
        target = PACKAGE_ROOT / path.removeprefix("naas_abi/")
        if not web_root.is_dir() and "/apps/web/" in path:
            continue
        assert target.exists(), path


def test_apps_default_model_follows_abi() -> None:
    assert AppsAgent.get_chat_model_id() == DEFAULT_FEATURE_MODEL
    assert AppsAgent.get_chat_model_ids() == [DEFAULT_FEATURE_MODEL]


def test_new_builds_with_apps_tools(monkeypatch) -> None:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class _DummyChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "dummy-apps-model"

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager=None,
            **kwargs,
        ) -> ChatResult:
            del messages, stop, run_manager, kwargs
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="ok"))]
            )

    requested: list[tuple[str, object]] = []

    class _Registry:
        def get_chat_model(self, model_id, provider=None):
            requested.append((model_id, provider))
            return _DummyChatModel()

    module = SimpleNamespace(
        engine=SimpleNamespace(services=SimpleNamespace(model_registry=_Registry())),
        configuration=SimpleNamespace(
            abi_agent_model="abi-model", abi_agent_provider=None
        ),
    )
    monkeypatch.setattr("naas_abi.ABIModule.get_instance", lambda: module)

    agent = AppsAgent.New()
    names = {tool.name for tool in agent.tools}

    assert isinstance(agent, AppsAgent)
    assert agent.name == "Apps"
    assert requested == [("abi-model", None)]
    assert "set_app_enabled" in names
    assert "read_nexus_source" in names
    assert "[TOOLS]" not in agent.configuration.system_prompt
    assert agent._markdown_pretty_display is False
    # The API runs a per-request duplicate: it must keep the step budget.
    assert agent.recursion_limit == 60
    assert agent.duplicate().recursion_limit == 60


def test_abi_hands_apps_requests_to_apps() -> None:
    apps = SimpleNamespace(
        name=AppsAgent.name,
        description=AppsAgent.description,
        intents=AppsAgent.handoff_intents(),
    )
    intents = AbiAgent.get_intents(agents=[apps])
    values = " ".join(
        i.intent_value.lower() for i in intents if i.intent_target == "Apps"
    )

    assert "enable an app" in values
    assert "active une app" in values
    assert "Apps for workspace apps" in AbiAgent.system_prompt


def test_abi_does_not_own_apps_tools() -> None:
    source = inspect.getsource(AbiAgent.get_tools)
    assert "apps_tools" not in source
    assert "nexus_source_tools" not in source
