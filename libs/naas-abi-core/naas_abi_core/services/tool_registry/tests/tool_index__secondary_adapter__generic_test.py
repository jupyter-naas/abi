"""Contract every ``IToolIndexPort`` adapter must satisfy.

Subclass ``ToolIndexSecondaryAdapterContract`` in the adapter's test file and
provide an ``index`` fixture returning a fresh, unprepared adapter.
"""

from abc import ABC

import pytest

from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolIndexPort,
    ToolIndexEntry,
)


def _entry(
    id: str, vector: tuple[float, ...], fingerprint: str = "fp"
) -> ToolIndexEntry:
    return ToolIndexEntry(id=id, fingerprint=fingerprint, vector=vector)


class ToolIndexSecondaryAdapterContract(ABC):
    def test_is_an_index_port(self, index):
        assert isinstance(index, IToolIndexPort)

    def test_operations_before_prepare_fail_loudly(self, index):
        with pytest.raises(RuntimeError):
            index.upsert([_entry("a/b@1", (1.0, 0.0))])

    def test_fresh_index_is_empty(self, index):
        index.prepare("model-a")
        assert index.size() == 0
        assert index.search((1.0, 0.0), limit=3) == []
        assert index.fingerprints(["a/b@1"]) == {}

    def test_fingerprints_only_report_indexed_ids(self, index):
        index.prepare("model-a")
        index.upsert([_entry("a/b@1", (1.0, 0.0), "fp-1")])
        assert index.fingerprints(["a/b@1", "a/c@1"]) == {"a/b@1": "fp-1"}

    def test_search_orders_by_similarity_and_respects_limit(self, index):
        index.prepare("model-a")
        index.upsert(
            [
                _entry("ns/near@1", (1.0, 0.1)),
                _entry("ns/far@1", (0.0, 1.0)),
                _entry("ns/middle@1", (1.0, 1.0)),
            ]
        )
        hits = index.search((1.0, 0.0), limit=2)
        assert [hit.id for hit in hits] == ["ns/near@1", "ns/middle@1"]
        assert hits[0].score > hits[1].score

    def test_identical_direction_scores_one(self, index):
        index.prepare("model-a")
        index.upsert([_entry("ns/same@1", (3.0, 4.0))])
        (hit,) = index.search((0.6, 0.8), limit=1)
        assert hit.score == pytest.approx(1.0, abs=1e-5)

    def test_upsert_replaces_an_existing_entry(self, index):
        index.prepare("model-a")
        index.upsert([_entry("ns/tool@1", (1.0, 0.0), "old")])
        index.upsert([_entry("ns/tool@1", (0.0, 1.0), "new")])
        assert index.size() == 1
        assert index.fingerprints(["ns/tool@1"]) == {"ns/tool@1": "new"}
        (hit,) = index.search((0.0, 1.0), limit=1)
        assert hit.score == pytest.approx(1.0, abs=1e-5)

    def test_delete_removes_entries_and_ignores_unknown_ids(self, index):
        index.prepare("model-a")
        index.upsert([_entry("ns/a@1", (1.0, 0.0)), _entry("ns/b@1", (0.0, 1.0))])
        index.delete(["ns/a@1", "ns/unknown@1"])
        assert index.size() == 1
        assert [hit.id for hit in index.search((1.0, 0.0), limit=5)] == ["ns/b@1"]

    def test_preparing_the_same_model_keeps_entries(self, index):
        index.prepare("model-a")
        index.upsert([_entry("ns/a@1", (1.0, 0.0))])
        index.prepare("model-a")
        assert index.size() == 1

    def test_preparing_another_model_discards_entries(self, index):
        index.prepare("model-a")
        index.upsert([_entry("ns/a@1", (1.0, 0.0))])
        index.prepare("model-b")
        assert index.size() == 0
        assert index.fingerprints(["ns/a@1"]) == {}
        # A new model may use another dimensionality.
        index.upsert([_entry("ns/a@1", (1.0, 0.0, 0.0))])
        assert index.size() == 1

    def test_dimension_mismatch_is_rejected(self, index):
        index.prepare("model-a")
        index.upsert([_entry("ns/a@1", (1.0, 0.0))])
        with pytest.raises(ValueError):
            index.upsert([_entry("ns/b@1", (1.0, 0.0, 0.0))])

    def test_limit_must_be_positive(self, index):
        index.prepare("model-a")
        with pytest.raises(ValueError):
            index.search((1.0, 0.0), limit=0)
