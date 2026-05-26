from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.tests.activity_log__secondary_adapter__generic_test import (
    GenericActivityLogSecondaryAdapterTest,
)


class TestActivityLogSqliteAdapter(GenericActivityLogSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return ActivityLogSqliteAdapter

    @pytest.fixture
    def adapter(self, tmp_path):
        ad = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        yield ad
        ad.shutdown()

    def test_persistence_across_restart(self, tmp_path):
        actor = f"user:{uuid4()}"
        first = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        first.record(
            ActivityEvent(
                actor_id=actor,
                event_type="http.request",
                attributes={"path": "/x"},
            )
        )
        first.shutdown()

        second = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        try:
            events = second.query(actor)
            assert len(events) == 1
            assert events[0].attributes == {"path": "/x"}
        finally:
            second.shutdown()

    def test_concurrent_writes_same_actor_are_safe(self, tmp_path):
        actor = f"user:{uuid4()}"
        adapter = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        try:
            def _writer(i: int) -> None:
                adapter.record(
                    ActivityEvent(
                        actor_id=actor,
                        event_type="x",
                        attributes={"i": i},
                    )
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(_writer, range(50)))

            events = adapter.query(actor)
            assert len(events) == 50
            assert sorted(e.attributes["i"] for e in events) == list(range(50))
        finally:
            adapter.shutdown()

    def test_concurrent_writes_different_actors_do_not_contend(self, tmp_path):
        adapter = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        try:
            actors = [f"user:{uuid4()}" for _ in range(5)]

            def _writer(actor: str) -> None:
                for i in range(10):
                    adapter.record(
                        ActivityEvent(
                            actor_id=actor,
                            event_type="x",
                            attributes={"i": i},
                        )
                    )

            with ThreadPoolExecutor(max_workers=5) as executor:
                list(executor.map(_writer, actors))

            for actor in actors:
                assert len(adapter.query(actor)) == 10
        finally:
            adapter.shutdown()

    def test_lru_evicts_connections_over_cap(self, tmp_path):
        adapter = ActivityLogSqliteAdapter(
            data_dir=str(tmp_path), max_open_connections=3
        )
        try:
            actors = [f"user:{i}" for i in range(10)]
            for actor in actors:
                adapter.record(ActivityEvent(actor_id=actor, event_type="x"))

            assert len(adapter._connections) <= 3

            # Previously-evicted actor must still be queryable — connection
            # is just reopened lazily.
            assert len(adapter.query(actors[0])) == 1
        finally:
            adapter.shutdown()

    def test_actor_filename_is_url_encoded(self, tmp_path):
        adapter = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        try:
            actor = "user:with/slash and:colon"
            adapter.record(ActivityEvent(actor_id=actor, event_type="x"))
            adapter.shutdown()

            import os
            files = os.listdir(tmp_path)
            sqlite_files = [f for f in files if f.endswith(".sqlite")]
            assert len(sqlite_files) == 1
            # Forward slashes must not appear in the filename.
            assert "/" not in sqlite_files[0]
        finally:
            adapter.shutdown()
