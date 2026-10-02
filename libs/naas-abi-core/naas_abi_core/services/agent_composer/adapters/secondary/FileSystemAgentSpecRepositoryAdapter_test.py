import json

import pytest
import yaml
from naas_abi_core.services.agent_composer.adapters.secondary.FileSystemAgentSpecRepositoryAdapter import (
    FileSystemAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentSpecInvalidError,
    AgentSpecNotFoundError,
)
from naas_abi_core.services.agent_composer.tests.agent_spec_repository__secondary_adapter__generic_test import (
    AgentSpecRepositorySecondaryAdapterContract,
)


class TestFileSystemAgentSpecRepositoryAdapter(
    AgentSpecRepositorySecondaryAdapterContract
):
    @pytest.fixture
    def repository(self, tmp_path):
        return FileSystemAgentSpecRepositoryAdapter(tmp_path / "agents")

    def test_reads_hand_written_yaml_records(self, tmp_path):
        (tmp_path / "triage.yaml").write_text(
            "name: triage\n"
            "prompt: You triage bugs.\n"
            "model: gpt-4.1-mini\n"
            "tools:\n"
            "  - acme.github/create_issue@1\n"
        )
        spec = FileSystemAgentSpecRepositoryAdapter(tmp_path).get("triage")
        assert spec.model.id == "gpt-4.1-mini"
        assert str(spec.tools[0].ref) == "acme.github/create_issue@1"

    def test_reads_json_records(self, tmp_path):
        (tmp_path / "triage.json").write_text(
            json.dumps({"name": "triage", "prompt": "You triage bugs."})
        )
        assert FileSystemAgentSpecRepositoryAdapter(tmp_path).get("triage").name == (
            "triage"
        )

    def test_saves_as_yaml(self, tmp_path):
        from naas_abi_core.services.agent_composer.AgentComposerPort import AgentSpec

        FileSystemAgentSpecRepositoryAdapter(tmp_path).save(
            AgentSpec(name="triage", prompt="Hi.")
        )
        assert (
            yaml.safe_load((tmp_path / "triage.yaml").read_text())["name"] == "triage"
        )

    def test_an_invalid_record_names_the_file(self, tmp_path):
        (tmp_path / "broken.yaml").write_text("name: broken\n")
        with pytest.raises(AgentSpecInvalidError, match="broken.yaml"):
            FileSystemAgentSpecRepositoryAdapter(tmp_path).get("broken")

    def test_a_file_whose_name_differs_from_the_record_is_invalid(self, tmp_path):
        (tmp_path / "triage.yaml").write_text("name: other\nprompt: Hi.\n")
        with pytest.raises(AgentSpecInvalidError, match="other"):
            FileSystemAgentSpecRepositoryAdapter(tmp_path).get("triage")

    def test_rejects_names_that_would_escape_the_directory(self, tmp_path):
        with pytest.raises(AgentSpecNotFoundError):
            FileSystemAgentSpecRepositoryAdapter(tmp_path).get("../secrets")

    def test_the_same_record_in_two_formats_is_ambiguous(self, tmp_path):
        (tmp_path / "triage.yaml").write_text("name: triage\nprompt: a\n")
        (tmp_path / "triage.json").write_text('{"name": "triage", "prompt": "b"}')
        with pytest.raises(AgentSpecInvalidError, match="more than one file"):
            FileSystemAgentSpecRepositoryAdapter(tmp_path).get("triage")
