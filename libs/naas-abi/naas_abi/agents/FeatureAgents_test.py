"""Contract tests for every Nexus feature office agent (Slides-parity).

Structural checks only; ``naas_abi.agents.feature.competency_eval`` runs the
competency questions against a live model.
"""

import importlib
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.feature import FEATURE_GROUNDING_GUIDELINES
from naas_abi.agents.feature.competency import (
    COMPETENCY_QUESTIONS,
    SOURCE_TOOLS,
    CompetencyQuestion,
    grade,
)
from naas_abi.agents.feature.registry import FEATURE_AGENTS, FeatureAgentSpec
from naas_abi.agents.tools.nexus_source_tools import PACKAGE_ROOT, resolve_source_path
from naas_abi_core.utils.Expose import Expose

GENERIC = [spec for spec in FEATURE_AGENTS if spec.name != "Slides"]
WEB_ROOT = PACKAGE_ROOT / "apps/nexus/apps/web"
WEB_MAP = WEB_ROOT / "src/lib/feature-office-agents.ts"
_FRENCH_RE = re.compile(r"^(Comment|Quel|Quelle|Quelles|Qu'|Pourquoi)")
_PATH_RE = re.compile(r"(naas_abi(?:_core)?/[^\s:,()]+)")


def _ids(spec: FeatureAgentSpec) -> str:
    return spec.class_name


def _code_map(spec: FeatureAgentSpec) -> str:
    module = importlib.import_module(spec.module)
    names = [n for n in vars(module) if n.endswith("_CODE_MAP")]
    assert names, f"{spec.module} has no *_CODE_MAP"
    return getattr(module, names[0])


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_agent_name_matches_the_registry(spec: FeatureAgentSpec) -> None:
    cls = spec.load()
    assert cls.__name__ == spec.class_name
    assert cls.name == spec.name
    assert "model_id" in inspect.signature(cls.New).parameters


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_loader_sees_only_the_agent_class(spec: FeatureAgentSpec) -> None:
    """ModuleAgentLoader registers every naas_abi Expose class in the module."""
    module = importlib.import_module(spec.module)
    exposed = [
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, Expose)
        and value.__module__.split(".")[0] == "naas_abi"
    ]
    assert exposed == [spec.load()]
    assert not hasattr(module, "create_agent")


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_agent_can_read_the_code(spec: FeatureAgentSpec) -> None:
    names = {tool.name for tool in spec.load().get_tools()}
    assert set(SOURCE_TOOLS) <= names


@pytest.mark.parametrize("spec", GENERIC, ids=_ids)
def test_prompt_is_grounded(spec: FeatureAgentSpec) -> None:
    prompt = spec.load().system_prompt
    assert FEATURE_GROUNDING_GUIDELINES in prompt
    assert "<code_map>" in prompt and "<capabilities>" in prompt
    assert "[TOOLS]" in prompt
    assert "Preserve the language" in prompt
    assert f"You are {spec.name}" in prompt


@pytest.mark.parametrize("spec", GENERIC, ids=_ids)
def test_code_map_paths_exist(spec: FeatureAgentSpec) -> None:
    """Every path the prompt tells the agent to read is real."""
    paths = [p.rstrip(".") for p in _PATH_RE.findall(_code_map(spec))]
    assert paths
    for raw in paths:
        if "/apps/web/" in raw and not WEB_ROOT.is_dir():
            continue
        if "<" in raw:  # templates like app/api/maps/<feed>/route.ts
            raw = raw.split("<", 1)[0]
        if "*" in raw:  # globs like components/maps-*.tsx
            parent, _, pattern = raw.rpartition("/")
            assert list(resolve_source_path(parent).glob(pattern)), raw
            continue
        assert resolve_source_path(raw).exists(), raw


@pytest.mark.parametrize("spec", GENERIC, ids=_ids)
def test_abi_gets_the_handoff_intents(spec: FeatureAgentSpec) -> None:
    cls = spec.load()
    fake = SimpleNamespace(
        name=cls.name, description=cls.description, intents=cls.handoff_intents()
    )
    intents = AbiAgent.get_intents(agents=[fake])
    targets = [i for i in intents if i.intent_target == spec.name]
    assert len(targets) > len(cls.handoff_intents())  # routing + description + phrases
    assert any(not i.intent_value.isascii() or " " in i.intent_value for i in targets)


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_abi_prompt_hands_the_feature_off(spec: FeatureAgentSpec) -> None:
    assert f"{spec.name} for {spec.summary}" in AbiAgent.system_prompt
    assert "[FEATURE_AGENTS]" not in AbiAgent.system_prompt


def test_abi_skips_a_supervisor_that_delegates_to_it(monkeypatch) -> None:
    """Bob has Abi as a sub-agent; Abi building Bob back would never end."""
    import naas_abi
    from naas_abi_core.services.agent.Agent import Agent

    built: list[str] = []

    def _stub(name: str, **attrs: object) -> type:
        def new(cls: type) -> SimpleNamespace:
            built.append(name)
            return SimpleNamespace(duplicate=lambda **_: SimpleNamespace(name=name))

        return type(name, (Agent,), {"New": classmethod(new), **attrs})

    apps = _stub("Apps")
    bob = _stub("Bob", delegates_to_abi=True)
    fake_module = SimpleNamespace(
        agents=[apps, AbiAgent],
        engine=SimpleNamespace(modules={"bob": SimpleNamespace(agents=[bob])}),
    )
    monkeypatch.setattr(
        naas_abi.ABIModule, "get_instance", classmethod(lambda cls: fake_module)
    )

    agents, _ = AbiAgent.get_agents()

    assert [a.name for a in agents] == ["Apps"]
    assert built == ["Apps"]


def test_sandbox_tools_are_hidden_without_a_coding_workspace() -> None:
    """Abi listed "the workspace drive" with list_coding_dir (an error outside
    Code) and Files then invented the listing."""
    from naas_abi.agents.tools.coding_tools import coding_tools
    from naas_abi_core.services.agent.Agent import Agent

    gated = {t.name for t in coding_tools() if Agent._requires_workspace(t)}

    assert gated == {
        "read_coding_file",
        "write_coding_file",
        "list_coding_dir",
        "run_in_coding_sandbox",
    }


def test_eval_orchestrator_defaults_to_abi() -> None:
    from naas_abi.agents.feature.competency_eval import (
        ABI_ORCHESTRATOR,
        load_orchestrator,
    )

    assert load_orchestrator(ABI_ORCHESTRATOR) is AbiAgent
    with pytest.raises(ValueError):
        load_orchestrator("naas_abi.agents.AbiAgent")


def test_abi_does_not_own_feature_tools() -> None:
    source = inspect.getsource(AbiAgent.get_tools)
    for module in ("apps_tools", "graph_tools", "files_tools", "nexus_source_tools"):
        assert module not in source


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_competency_questions_cover_the_four_kinds(spec: FeatureAgentSpec) -> None:
    questions = COMPETENCY_QUESTIONS[spec.name]
    kinds = {q.kind for q in questions}
    assert {"capabilities", "implementation", "other"} <= kinds
    assert any(_FRENCH_RE.match(q.question) for q in questions), (
        "each agent needs a French question"
    )


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_competency_questions_only_expect_tools_the_agent_has(
    spec: FeatureAgentSpec,
) -> None:
    names = {tool.name for tool in spec.load().get_tools()}
    for question in COMPETENCY_QUESTIONS[spec.name]:
        if question.expect_tools:
            assert set(question.expect_tools) & names, question.question


@pytest.mark.parametrize("spec", FEATURE_AGENTS, ids=_ids)
def test_feature_keys_match_the_web_map(spec: FeatureAgentSpec) -> None:
    if not WEB_MAP.is_file():
        pytest.skip("web sources not shipped")
    text = WEB_MAP.read_text(encoding="utf-8")
    for key in spec.feature_keys:
        assert re.search(
            rf"'?{re.escape(key)}'?:\s*\{{\s*name:\s*'{re.escape(spec.name)}',\s*className:\s*'{spec.class_name}'",
            text,
        ), f"{key} -> {spec.class_name} missing from {WEB_MAP.name}"


def test_grade_requires_a_tool_and_a_term() -> None:
    q = CompetencyQuestion("How?", "implementation", SOURCE_TOOLS, ("manifest.json",))
    assert grade(q, "It reads manifest.json", ["read_nexus_source"]).passed
    assert not grade(q, "It reads manifest.json", []).passed
    assert not grade(q, "From memory", ["read_nexus_source"]).passed
    assert not grade(q, "", ["read_nexus_source"], error="boom").passed
    assert not grade(
        CompetencyQuestion("x", "other"),
        "I do not have the capabilities to handle it",
        [],
    ).passed


def test_registry_paths_are_package_relative() -> None:
    for spec in FEATURE_AGENTS:
        assert (PACKAGE_ROOT / "agents" / f"{spec.class_name}.py").is_file()
    assert Path(__file__).parent == PACKAGE_ROOT / "agents"


def test_collect_stream_assembles_the_pane_reply() -> None:
    from naas_abi.agents.feature.competency_eval import collect_stream

    events = [
        {"event": "tool_usage", "data": "transfer_to_Apps"},
        {"event": "ai_message", "data": ""},
        {"event": "ai_message", "data": "It scans manifest.json."},
        {"event": "message", "data": ""},
        {"event": "done", "data": "[DONE]"},
        {"event": "ai_message", "data": "after done"},
    ]
    assert collect_stream(events) == "It scans manifest.json."
    assert (
        collect_stream(
            [{"event": "message", "data": "a"}, {"event": "message", "data": "b"}]
        )
        == "a\nb"
    )


@pytest.mark.parametrize("spec", GENERIC, ids=_ids)
def test_feature_agents_get_a_grounding_step_budget(spec: FeatureAgentSpec) -> None:
    from naas_abi.agents.feature import FEATURE_RECURSION_LIMIT

    assert spec.load().recursion_limit == FEATURE_RECURSION_LIMIT > 25


def test_abi_budget_covers_a_handoff_that_reads_code() -> None:
    from naas_abi.agents.feature import FEATURE_RECURSION_LIMIT

    assert AbiAgent.recursion_limit == FEATURE_RECURSION_LIMIT


@pytest.mark.parametrize("spec", GENERIC, ids=_ids)
def test_agent_knows_its_roster_line(spec: FeatureAgentSpec) -> None:
    assert f'"naas_abi {spec.class_name}"' in spec.load().system_prompt


def test_app_builder_write_tools_match_the_web_list() -> None:
    """The editor refreshes after exactly these tools (isAppProjectWriteTool)."""
    from naas_abi.agents.tools.app_builder_tools import (
        APP_PROJECT_WRITE_TOOLS,
        app_builder_tools,
    )

    names = {t.name for t in app_builder_tools()}
    assert set(APP_PROJECT_WRITE_TOOLS) <= names
    web = WEB_ROOT / "src/lib/app-projects.ts"
    if not web.is_file():
        pytest.skip("web sources not shipped")
    block = web.read_text(encoding="utf-8").split("APP_PROJECT_WRITE_TOOLS = [", 1)[1]
    listed = set(re.findall(r"'([a-z_]+)'", block.split("]", 1)[0]))
    assert listed == set(APP_PROJECT_WRITE_TOOLS)


def test_apps_agent_builds_apps() -> None:
    from naas_abi.agents.AppsAgent import AppsAgent

    names = {t.name for t in AppsAgent.get_tools()}
    assert {
        "create_app_project",
        "edit_module_app",
        "write_app_file",
        "check_app",
    } <= names
    assert "<app_building>" in AppsAgent.system_prompt
