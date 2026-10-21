import pytest
from naas_abi_core.services.agent_composer.adapters.secondary.DocumentAgentSpecRepositoryAdapter import (
    AGENT_SPEC_COLLECTION,
    AGENT_SPEC_NAMESPACE,
    DocumentAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentSpec,
    AgentSpecInvalidError,
    AgentSpecNotFoundError,
)
from naas_abi_core.services.agent_composer.tests.agent_spec_repository__secondary_adapter__generic_test import (
    AgentSpecRepositorySecondaryAdapterContract,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentService import DocumentService


@pytest.fixture
def root(tmp_path):
    adapter = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    yield DocumentService._for_engine(adapter)
    adapter.close()


class TestDocumentAgentSpecRepositoryAdapter(
    AgentSpecRepositorySecondaryAdapterContract
):
    @pytest.fixture
    def repository(self, root):
        return DocumentAgentSpecRepositoryAdapter.for_engine(root)

    def test_records_are_shared_by_every_adapter_on_the_service(self, root):
        first = DocumentAgentSpecRepositoryAdapter.for_engine(root)
        second = DocumentAgentSpecRepositoryAdapter.for_engine(root)
        first.save(AgentSpec(name="triage", prompt="v1"))
        second.save(AgentSpec(name="triage", prompt="v2"))
        assert first.get("triage").prompt == "v2"

    def test_records_live_in_the_composers_own_namespace(self, root):
        DocumentAgentSpecRepositoryAdapter.for_engine(root).save(
            AgentSpec(name="triage", prompt="Hi.")
        )
        assert root.namespaces() == [AGENT_SPEC_NAMESPACE]
        view = root.for_namespace(AGENT_SPEC_NAMESPACE)
        assert view.collections() == [AGENT_SPEC_COLLECTION]
        assert view.get(AGENT_SPEC_COLLECTION, "triage").data["prompt"] == "Hi."

    def test_a_bound_view_is_used_as_it_is(self, root):
        module_view = root.for_namespace("acme.module")
        repository = DocumentAgentSpecRepositoryAdapter.for_engine(module_view)
        repository.save(AgentSpec(name="triage", prompt="Hi."))
        assert root.namespaces() == ["acme.module"]

    def test_construction_does_not_touch_the_service(self):
        class Untouchable:
            def __getattr__(self, name):
                raise AssertionError(f"touched {name}")

        DocumentAgentSpecRepositoryAdapter(Untouchable())  # type: ignore[arg-type]

    def test_a_record_that_no_longer_matches_the_schema_is_reported(self, root):
        repository = DocumentAgentSpecRepositoryAdapter.for_engine(root)
        repository.save(AgentSpec(name="triage", prompt="Hi."))
        view = root.for_namespace(AGENT_SPEC_NAMESPACE)
        view.put(AGENT_SPEC_COLLECTION, "broken", {"name": "broken", "prompt": ""})
        view.put(AGENT_SPEC_COLLECTION, "renamed", {"name": "other", "prompt": "x"})
        with pytest.raises(AgentSpecInvalidError):
            repository.get("broken")
        with pytest.raises(AgentSpecInvalidError, match="declares name 'other'"):
            repository.get("renamed")

    def test_names_that_cannot_be_records_are_not_found(self, root):
        repository = DocumentAgentSpecRepositoryAdapter.for_engine(root)
        with pytest.raises(AgentSpecNotFoundError):
            repository.get("../etc")
        with pytest.raises(AgentSpecNotFoundError):
            repository.delete("a b")
