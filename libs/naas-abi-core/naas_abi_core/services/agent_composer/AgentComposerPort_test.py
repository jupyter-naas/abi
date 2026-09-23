import pytest
from pydantic import ValidationError

from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentCompositionError,
    AgentSpec,
    CapabilitiesSpec,
    ModelRef,
    SecretRef,
    SubAgentCycleError,
    SubAgentRef,
    ToolBindingSpec,
)


def _spec(**overrides) -> AgentSpec:
    values = {"name": "triage", "prompt": "You triage bugs."}
    values.update(overrides)
    return AgentSpec.model_validate(values)


class TestAgentSpec:
    def test_minimal_record(self):
        spec = _spec()
        assert spec.kind == "abi.agent/v1"
        assert spec.model is None
        assert spec.tools == []
        assert spec.sub_agents == []
        assert spec.capabilities == CapabilitiesSpec()

    def test_accepts_the_short_forms_used_in_hand_written_records(self):
        spec = _spec(
            model="gpt-4.1-mini",
            tools=["acme.github/create_issue@1"],
            sub_agents=["researcher"],
        )
        assert spec.model == ModelRef(id="gpt-4.1-mini")
        assert spec.tools == [ToolBindingSpec(tool="acme.github/create_issue@1")]
        assert spec.sub_agents == [SubAgentRef(agent="researcher")]

    def test_accepts_the_long_forms(self):
        spec = _spec(
            model={"id": "gpt-4.1-mini", "provider": "openai"},
            tools=[
                {
                    "tool": "acme.github/create_issue",
                    "config": {
                        "access_token": {"secret": "GITHUB_TOKEN"},
                        "retries": 2,
                    },
                }
            ],
        )
        assert spec.model.provider == "openai"
        assert spec.tools[0].config["access_token"] == SecretRef(secret="GITHUB_TOKEN")
        assert spec.tools[0].config["retries"] == 2

    def test_round_trips_through_json(self):
        spec = _spec(
            model="m",
            tools=[
                {"tool": "acme.github/create_issue", "config": {"t": {"secret": "S"}}}
            ],
            sub_agents=["researcher"],
            capabilities={"enabled": True, "allow": ["acme.*"], "max_enabled": 3},
        )
        assert AgentSpec.model_validate_json(spec.model_dump_json()) == spec

    @pytest.mark.parametrize(
        "overrides",
        [
            {"name": "has space"},
            {"name": ""},
            {"prompt": ""},
            {"kind": "abi.agent/v2"},
            {"tools": ["not a tool ref"]},
            {"unexpected": True},
            {"capabilities": {"max_enabled": 0}},
            {"capabilities": {"enabled": True, "allow": []}},
        ],
    )
    def test_rejects_invalid_records(self, overrides):
        with pytest.raises(ValidationError):
            _spec(**overrides)

    def test_rejects_the_same_tool_twice(self):
        with pytest.raises(ValidationError, match="more than once"):
            _spec(tools=["acme.github/create_issue", "acme.github/create_issue"])

    def test_rejects_the_same_sub_agent_twice(self):
        with pytest.raises(ValidationError, match="more than once"):
            _spec(sub_agents=["researcher", "researcher"])

    def test_records_never_hold_credentials_inline_only_references(self):
        spec = _spec(tools=[{"tool": "a/b", "config": {"token": {"secret": "TOKEN"}}}])
        assert "TOKEN" in spec.model_dump_json()
        with pytest.raises(ValidationError):
            _spec(tools=[{"tool": "a/b", "config": {"token": {"value": "sk-live"}}}])


class TestErrors:
    def test_composition_errors_list_every_problem(self):
        error = AgentCompositionError("triage", ["tool x missing", "model y missing"])
        assert error.problems == ("tool x missing", "model y missing")
        assert "tool x missing" in str(error) and "model y missing" in str(error)
        assert "triage" in str(error)

    def test_cycle_errors_show_the_path(self):
        error = SubAgentCycleError(["a", "b", "a"])
        assert error.cycle == ("a", "b", "a")
        assert "a -> b -> a" in str(error)
        assert isinstance(error, AgentCompositionError)
