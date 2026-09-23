import pytest
from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.tests.tool_index__secondary_adapter__generic_test import (
    ToolIndexSecondaryAdapterContract,
)


class TestInMemoryToolIndexAdapter(ToolIndexSecondaryAdapterContract):
    @pytest.fixture
    def index(self):
        return InMemoryToolIndexAdapter()

    def test_equal_scores_are_ordered_by_id_for_determinism(self, index):
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            ToolIndexEntry,
        )

        index.prepare("model-a")
        index.upsert(
            [
                ToolIndexEntry(id="ns/b@1", fingerprint="x", vector=(1.0, 0.0)),
                ToolIndexEntry(id="ns/a@1", fingerprint="x", vector=(1.0, 0.0)),
            ]
        )
        assert [hit.id for hit in index.search((1.0, 0.0), limit=2)] == [
            "ns/a@1",
            "ns/b@1",
        ]

    def test_zero_vectors_score_zero_instead_of_dividing_by_zero(self, index):
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            ToolIndexEntry,
        )

        index.prepare("model-a")
        index.upsert([ToolIndexEntry(id="ns/a@1", fingerprint="x", vector=(0.0, 0.0))])
        (hit,) = index.search((1.0, 0.0), limit=1)
        assert hit.score == 0.0
