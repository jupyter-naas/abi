import inspect
from types import SimpleNamespace

from naas_abi.agents import SkillsAgent as skills_agent_module
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.AgentCatalogAgent import AgentCatalogAgent
from naas_abi.agents.feature import (
    DEFAULT_FEATURE_MODEL,
    FEATURE_GROUNDING_GUIDELINES,
)
from naas_abi.agents.SkillsAgent import SKILLS_CODE_MAP, SkillsAgent
from naas_abi.agents.tools.nexus_source_tools import PACKAGE_ROOT


def test_skills_agent_is_a_named_office_agent() -> None:
    assert SkillsAgent.__name__ == "SkillsAgent"
    assert SkillsAgent.name == "Skills"
    assert "model_id" in inspect.signature(SkillsAgent.New).parameters
    assert "not Abi" in SkillsAgent.system_prompt


def test_skills_agent_is_the_only_agent_class_the_loader_sees() -> None:
    from naas_abi_core.utils.Expose import Expose

    exposed = [
        value
        for value in vars(skills_agent_module).values()
        if isinstance(value, type)
        and issubclass(value, Expose)
        and value.__module__.split(".")[0] == "naas_abi"
    ]
    assert exposed == [SkillsAgent]
    assert not hasattr(skills_agent_module, "create_agent")


def test_skills_agent_owns_the_skill_write_tools() -> None:
    names = {tool.name for tool in SkillsAgent.get_tools()}
    assert {
        "list_workspace_skills",
        "get_workspace_skill",
        "create_skill",
        "update_skill",
        "delete_skill",
    } <= names
    assert {"list_nexus_source", "read_nexus_source", "search_nexus_source"} <= names


def test_the_agent_catalog_no_longer_touches_skills() -> None:
    """Skills moved out of Settings > Agents' agent: one owner per feature."""
    names = {tool.name for tool in AgentCatalogAgent.get_tools()}
    assert not {name for name in names if "skill" in name}


def test_skills_prompt_tells_the_agent_to_save_not_to_draft() -> None:
    prompt = SkillsAgent.system_prompt
    assert FEATURE_GROUNDING_GUIDELINES in prompt
    assert "<skill_writing>" in prompt
    assert "create_skill saves it" in prompt
    assert "Never print the skill as a JSON block" in prompt
    assert "Preserve the language" in prompt


def test_skills_code_map_paths_exist() -> None:
    """Every file the prompt tells the agent to read is real."""
    paths = [
        token.rstrip(":,.")
        for line in SKILLS_CODE_MAP.splitlines()
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


def test_skills_default_model_follows_abi() -> None:
    assert SkillsAgent.get_chat_model_id() == DEFAULT_FEATURE_MODEL
    assert SkillsAgent.get_chat_model_ids() == [DEFAULT_FEATURE_MODEL]


def test_abi_hands_skill_requests_to_skills() -> None:
    skills = SimpleNamespace(
        name=SkillsAgent.name,
        description=SkillsAgent.description,
        intents=SkillsAgent.handoff_intents(),
    )
    intents = AbiAgent.get_intents(agents=[skills])
    values = " ".join(
        i.intent_value.lower() for i in intents if i.intent_target == "Skills"
    )

    assert "create a skill" in values
    assert "crée une skill" in values
    assert "Skills for skills" in AbiAgent.system_prompt


def test_new_builds_with_the_skill_tools(monkeypatch) -> None:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class _DummyChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "dummy-skills-model"

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

    class _Registry:
        def get_chat_model(self, model_id, provider=None):
            del model_id, provider
            return _DummyChatModel()

    module = SimpleNamespace(
        engine=SimpleNamespace(services=SimpleNamespace(model_registry=_Registry())),
        configuration=SimpleNamespace(
            abi_agent_model="abi-model", abi_agent_provider=None
        ),
    )
    monkeypatch.setattr("naas_abi.ABIModule.get_instance", lambda: module)

    agent = SkillsAgent.New()
    names = {tool.name for tool in agent.tools}

    assert isinstance(agent, SkillsAgent)
    assert agent.name == "Skills"
    assert "create_skill" in names
    assert "[TOOLS]" not in agent.configuration.system_prompt
    assert agent._markdown_pretty_display is False
    # The API runs a per-request duplicate: it must keep the step budget.
    assert agent.recursion_limit == 60
    assert agent.duplicate().recursion_limit == 60
