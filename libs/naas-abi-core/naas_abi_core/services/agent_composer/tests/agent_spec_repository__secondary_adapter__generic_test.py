"""Contract every ``IAgentSpecRepository`` adapter must satisfy.

Subclass ``AgentSpecRepositorySecondaryAdapterContract`` and provide a
``repository`` fixture returning an empty repository.
"""

from abc import ABC

import pytest

from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentSpec,
    AgentSpecNotFoundError,
    IAgentSpecRepository,
)


def _spec(name: str, prompt: str = "You help.") -> AgentSpec:
    return AgentSpec.model_validate(
        {
            "name": name,
            "prompt": prompt,
            "model": {"id": "m", "provider": "p"},
            "tools": [
                {"tool": "acme.github/create_issue@1", "config": {"t": {"secret": "S"}}}
            ],
            "sub_agents": ["helper"],
            "capabilities": {"enabled": True, "allow": ["acme.*"]},
        }
    )


class AgentSpecRepositorySecondaryAdapterContract(ABC):
    def test_is_a_repository_port(self, repository):
        assert isinstance(repository, IAgentSpecRepository)

    def test_empty_repository(self, repository):
        assert repository.list() == []
        with pytest.raises(AgentSpecNotFoundError, match="triage"):
            repository.get("triage")

    def test_save_then_get_round_trips_the_whole_record(self, repository):
        spec = _spec("triage")
        repository.save(spec)
        assert repository.get("triage") == spec

    def test_save_replaces_a_record_of_the_same_name(self, repository):
        repository.save(_spec("triage", "v1"))
        repository.save(_spec("triage", "v2"))
        assert repository.get("triage").prompt == "v2"
        assert len(repository.list()) == 1

    def test_list_is_sorted_by_name(self, repository):
        for name in ["zeta", "alpha", "mid"]:
            repository.save(_spec(name))
        assert [s.name for s in repository.list()] == ["alpha", "mid", "zeta"]

    def test_delete(self, repository):
        repository.save(_spec("triage"))
        repository.delete("triage")
        assert repository.list() == []
        with pytest.raises(AgentSpecNotFoundError):
            repository.delete("triage")
