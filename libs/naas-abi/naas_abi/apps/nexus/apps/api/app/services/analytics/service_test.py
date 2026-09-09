"""Characterization tests for the analytics domain service.

Written before the rebuild-scheduling refactor to pin what the aggregates
contain today, so a change to *when* rebuilds run cannot quietly change *what*
they produce. Every expectation here is the pre-refactor behaviour.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from datetime import UTC, datetime
from typing import Any

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics import service as analytics_service
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    AnalyticsStoragePort,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import (
    EVENTS_FILE,
    METADATA_FILE,
    OVERVIEW_FILE,
    PAGES_FILE,
    RECENT_EVENTS_FILE,
    REF_USERS_FILE,
    REF_WORKSPACES_FILE,
    SCENARIO_FILE,
    SESSIONS_FILE,
    USER_DETAILS_FILE,
    USERS_FILE,
    WORKSPACES_FILE,
    AnalyticsService,
    _build_overview,
    _build_page_rows,
    _build_scenarios,
    _build_sessions,
    _build_user_detail_map,
    _build_user_rows,
    _build_workspace_rows,
    _enumerate_days,
    _enumerate_hours,
    _RebuildScheduler,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventService import EventService

NOW = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached within timeout")


def _RealEventService() -> EventService:
    """A real EventService on a throwaway SQLite file.

    The point of these tests is the codec: a fake publish would not prove that
    a tracker payload survives serialize → store → deserialize.
    """
    tmp = tempfile.mkdtemp(prefix="analytics-events-")
    return EventService(adapter=EventSQLiteAdapter(db_path=os.path.join(tmp, "events.sqlite")))


class _StubScheduler:
    def __init__(self, sink: list) -> None:
        self._sink = sink

    def schedule(self, service) -> None:
        self._sink.append(service)


class FakeStorage(AnalyticsStoragePort):
    """In-memory stand-in for the object-storage adapter.

    Counts writes per file, which is what the scheduling refactor is about.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.json: dict[str, Any] = {}
        self.write_counts: dict[str, int] = {}

    def save_event(self, event: dict[str, Any]) -> str:
        self.events.append(event)
        return f"events/{event['event_id']}.pkl"

    def list_events(self) -> list[dict[str, Any]]:
        return [dict(e) for e in self.events]

    def save_json(self, file_name: str, data: Any) -> None:
        self.json[file_name] = data
        self.write_counts[file_name] = self.write_counts.get(file_name, 0) + 1

    def load_json(self, file_name: str, fallback: Any = None) -> Any:
        return self.json.get(file_name, fallback)

    @property
    def total_writes(self) -> int:
        return sum(self.write_counts.values())


def ev(
    event_id: str,
    timestamp: str,
    *,
    email: str = "alice@example.com",
    user_id: str = "u-alice",
    session_id: str = "s1",
    event_name: str = "page_viewed",
    page_path: str | None = "/home",
    page_title: str | None = "Home",
    workspace_id: str | None = "ws-1",
    workspace_name: str | None = "Workspace One",
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "user_id": user_id,
        "user_email": email,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "session_id": session_id,
        "event_name": event_name,
        "page_path": page_path,
        "page_title": page_title,
        "device": "desktop",
        "browser": "firefox",
    }


# Two users, three sessions, spread across today and yesterday.
FIXTURE = [
    ev("e1", "2026-09-09T09:00:00Z"),
    ev("e2", "2026-09-09T09:05:00Z", page_path="/chat/conv-abc", page_title="Chat"),
    ev("e3", "2026-09-09T09:10:00Z", event_name="session_ended", page_path=None, page_title=None),
    ev("e4", "2026-09-08T10:00:00Z", session_id="s2"),
    ev(
        "e5",
        "2026-09-09T11:00:00Z",
        email="bob@example.com",
        user_id="u-bob",
        session_id="s3",
        event_name="button_clicked",
        page_path=None,
        page_title=None,
        workspace_id="ws-2",
        workspace_name="Workspace Two",
    ),
]


@pytest.fixture(autouse=True)
def _clean_write_cache():
    """The skip-unchanged cache is process-wide; isolate it per test."""
    analytics_service._last_written_digests.clear()
    yield
    analytics_service._last_written_digests.clear()


@pytest.fixture
def storage() -> FakeStorage:
    store = FakeStorage()
    store.events = [dict(e) for e in FIXTURE]
    return store


@pytest.fixture
def service(storage: FakeStorage) -> AnalyticsService:
    return AnalyticsService(storage=storage)


# ---------------------------------------------------------------------------
# Pure aggregation helpers
# ---------------------------------------------------------------------------


class TestAggregateBuilders:
    def test_sessions_span_first_to_last_event(self):
        rows = _build_sessions(FIXTURE)
        by_id = {r["session_id"]: r for r in rows}
        assert set(by_id) == {"s1", "s2", "s3"}
        s1 = by_id["s1"]
        assert s1["started_at"] == "2026-09-09T09:00:00Z"
        assert s1["ended_at"] == "2026-09-09T09:10:00Z"
        assert s1["duration_seconds"] == 600
        assert s1["events"] == 3
        assert s1["page_views"] == 2
        assert s1["user_email"] == "alice@example.com"

    def test_sessions_are_newest_first(self):
        rows = _build_sessions(FIXTURE)
        assert [r["session_id"] for r in rows] == ["s3", "s1", "s2"]

    def test_user_rows_count_distinct_sessions_and_workspaces(self):
        rows = _build_user_rows(FIXTURE)
        alice = next(r for r in rows if r["user_email"] == "alice@example.com")
        assert alice["sessions"] == 2
        assert alice["workspaces"] == 1
        assert alice["page_views"] == 3
        assert alice["total_events"] == 4
        assert alice["last_seen"] == "2026-09-09T09:10:00Z"

    def test_user_rows_are_ordered_by_total_events(self):
        rows = _build_user_rows(FIXTURE)
        assert [r["user_email"] for r in rows] == ["alice@example.com", "bob@example.com"]

    def test_page_rows_only_count_page_views(self):
        rows = _build_page_rows(FIXTURE)
        by_path = {r["page_path"]: r for r in rows}
        assert set(by_path) == {"/home", "/chat/conv-abc"}
        assert by_path["/home"]["views"] == 2
        assert by_path["/home"]["unique_users"] == 1

    def test_chat_page_title_is_decorated_with_the_conversation(self):
        rows = _build_page_rows(FIXTURE)
        chat = next(r for r in rows if r["page_path"] == "/chat/conv-abc")
        assert chat["page_title"] == "Chat - conv-abc"

    def test_workspace_rows_count_users_sessions_and_events(self):
        rows = _build_workspace_rows(FIXTURE)
        by_id = {r["workspace_id"]: r for r in rows}
        assert by_id["ws-1"]["events"] == 4
        assert by_id["ws-1"]["sessions"] == 2
        assert by_id["ws-1"]["active_users"] == 1
        assert by_id["ws-2"]["workspace_name"] == "Workspace Two"

    def test_overview_kpi_matches_the_fixture(self):
        days = _enumerate_days("2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z")
        overview = _build_overview(FIXTURE, _build_sessions(FIXTURE), days)
        kpi = overview["kpi"]
        assert kpi["active_users"] == 2
        assert kpi["total_sessions"] == 3
        assert kpi["total_page_views"] == 3
        assert kpi["workspaces_used"] == 2
        assert kpi["returning_users"] == 1
        assert kpi["most_active_workspace"]["id"] == "ws-1"

    def test_overview_timeseries_covers_every_day_in_the_window(self):
        days = _enumerate_days("2026-09-07T00:00:00Z", "2026-09-09T00:00:00Z")
        overview = _build_overview(FIXTURE, _build_sessions(FIXTURE), days)
        assert [p["date"] for p in overview["sessions_over_time"]] == [
            "2026-09-07",
            "2026-09-08",
            "2026-09-09",
        ]
        assert [p["value"] for p in overview["sessions_over_time"]] == [0, 1, 2]

    def test_overview_of_nothing_is_fully_zeroed(self):
        overview = _build_overview(
            [], [], _enumerate_days("2026-09-09T00:00:00Z", "2026-09-09T00:00:00Z")
        )
        assert overview["kpi"]["active_users"] == 0
        assert overview["kpi"]["avg_sessions_per_user"] == 0.0
        assert overview["kpi"]["most_active_workspace"] is None

    def test_user_detail_map_is_keyed_by_email_and_newest_first(self):
        details = _build_user_detail_map(FIXTURE)
        assert set(details) == {"alice@example.com", "bob@example.com"}
        alice = details["alice@example.com"]
        assert alice["first_seen"] == "2026-09-08T10:00:00Z"
        assert alice["last_seen"] == "2026-09-09T09:10:00Z"
        assert alice["total_sessions"] == 2
        assert [e["event_id"] for e in alice["events"]] == ["e3", "e2", "e1", "e4"]
        assert alice["most_visited_page"]["path"] == "/home"


class TestScenarioWindows:
    def test_catalog_is_today_yesterday_and_three_lookbacks(self):
        scenarios = _build_scenarios(NOW)
        assert [s["scenario_id"] for s in scenarios] == [
            "today",
            "yesterday",
            "last_7_days",
            "last_30_days",
            "last_90_days",
        ]

    def test_today_starts_at_midnight_and_ends_now(self):
        today = _build_scenarios(NOW)[0]
        assert today["date_start"] == "2026-09-09T00:00:00Z"
        assert today["date_end"] == "2026-09-09T12:00:00Z"

    def test_yesterday_stops_one_second_before_today(self):
        yesterday = _build_scenarios(NOW)[1]
        assert yesterday["date_start"] == "2026-09-08T00:00:00Z"
        assert yesterday["date_end"] == "2026-09-08T23:59:59Z"

    def test_hourly_slots_are_enumerated_for_short_windows(self):
        slots = _enumerate_hours("2026-09-09T09:00:00Z", "2026-09-09T11:00:00Z")
        assert slots == ["2026-09-09T09", "2026-09-09T10", "2026-09-09T11"]


# ---------------------------------------------------------------------------
# Rebuild
# ---------------------------------------------------------------------------


class TestRebuild:
    def test_writes_every_aggregate_file(self, service: AnalyticsService, storage: FakeStorage):
        service.rebuild(now=NOW)
        assert set(storage.json) == {
            EVENTS_FILE,
            SCENARIO_FILE,
            OVERVIEW_FILE,
            USERS_FILE,
            SESSIONS_FILE,
            PAGES_FILE,
            WORKSPACES_FILE,
            USER_DETAILS_FILE,
            RECENT_EVENTS_FILE,
            METADATA_FILE,
        }

    def test_events_file_is_sorted_oldest_first(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        service.rebuild(now=NOW)
        ids = [e["event_id"] for e in storage.json[EVENTS_FILE]["events"]]
        assert ids == ["e4", "e1", "e2", "e3", "e5"]

    def test_each_aggregate_is_keyed_by_scenario(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        service.rebuild(now=NOW)
        for file_name in (OVERVIEW_FILE, USERS_FILE, SESSIONS_FILE, PAGES_FILE, WORKSPACES_FILE):
            assert set(storage.json[file_name]) == {
                "today",
                "yesterday",
                "last_7_days",
                "last_30_days",
                "last_90_days",
            }

    def test_today_scenario_excludes_yesterdays_events(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        service.rebuild(now=NOW)
        today = storage.json[OVERVIEW_FILE]["today"]
        assert today["kpi"]["total_sessions"] == 2
        yesterday = storage.json[OVERVIEW_FILE]["yesterday"]
        assert yesterday["kpi"]["total_sessions"] == 1

    def test_recent_events_are_newest_first(self, service: AnalyticsService, storage: FakeStorage):
        service.rebuild(now=NOW)
        events = storage.json[RECENT_EVENTS_FILE]["last_7_days"]["events"]
        assert [e["event_id"] for e in events] == ["e5", "e3", "e2", "e1", "e4"]

    def test_metadata_reports_the_event_count(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        metadata = service.rebuild(now=NOW)
        assert metadata.events.count == 5
        assert {a.file for a in metadata.aggregates} == {
            SCENARIO_FILE,
            OVERVIEW_FILE,
            USERS_FILE,
            SESSIONS_FILE,
            PAGES_FILE,
            WORKSPACES_FILE,
            USER_DETAILS_FILE,
            RECENT_EVENTS_FILE,
        }

    def test_users_aggregate_carries_the_directory(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        storage.json[REF_USERS_FILE] = [{"user_id": "u-alice", "user_email": "alice@example.com"}]
        service.rebuild(now=NOW)
        assert storage.json[USERS_FILE]["last_7_days"]["directory"] == storage.json[REF_USERS_FILE]

    def test_rebuild_of_an_empty_store_still_writes_every_file(self):
        storage = FakeStorage()
        AnalyticsService(storage=storage).rebuild(now=NOW)
        assert storage.json[EVENTS_FILE] == {"events": []}
        assert storage.json[OVERVIEW_FILE]["today"]["kpi"]["active_users"] == 0


# ---------------------------------------------------------------------------
# Ingest / reference directories
# ---------------------------------------------------------------------------


class TestIngest:
    def test_stores_the_event_and_returns_its_key(self):
        storage = FakeStorage()
        service = AnalyticsService(storage=storage)
        stored_at = service.ingest_event(AnalyticsEvent(**FIXTURE[0]))
        assert stored_at.endswith("e1.pkl")
        assert len(storage.events) == 1

    def test_registers_the_user_and_workspace_directories(self):
        storage = FakeStorage()
        service = AnalyticsService(storage=storage)
        service.ingest_event(AnalyticsEvent(**FIXTURE[0]))
        assert storage.json[REF_USERS_FILE] == [
            {
                "user_id": "u-alice",
                "user_email": "alice@example.com",
                "workspace_ids": ["ws-1"],
            }
        ]
        assert storage.json[REF_WORKSPACES_FILE] == [
            {"workspace_id": "ws-1", "workspace_name": "Workspace One"}
        ]

    def test_re_registering_the_same_user_does_not_rewrite_the_directory(self):
        storage = FakeStorage()
        service = AnalyticsService(storage=storage)
        service.ingest_event(AnalyticsEvent(**FIXTURE[0]))
        writes = storage.write_counts[REF_USERS_FILE]
        service.ingest_event(AnalyticsEvent(**FIXTURE[1]))
        assert storage.write_counts[REF_USERS_FILE] == writes

    def test_a_new_workspace_for_a_known_user_is_appended(self):
        storage = FakeStorage()
        service = AnalyticsService(storage=storage)
        service.ingest_event(AnalyticsEvent(**FIXTURE[0]))
        moved = dict(FIXTURE[0])
        moved.update(event_id="e9", workspace_id="ws-9", workspace_name="Workspace Nine")
        service.ingest_event(AnalyticsEvent(**moved))
        assert storage.json[REF_USERS_FILE][0]["workspace_ids"] == ["ws-1", "ws-9"]

    def test_a_renamed_workspace_updates_in_place(self):
        storage = FakeStorage()
        service = AnalyticsService(storage=storage)
        service.ingest_event(AnalyticsEvent(**FIXTURE[0]))
        renamed = dict(FIXTURE[0])
        renamed.update(event_id="e9", workspace_name="Renamed")
        service.ingest_event(AnalyticsEvent(**renamed))
        assert storage.json[REF_WORKSPACES_FILE] == [
            {"workspace_id": "ws-1", "workspace_name": "Renamed"}
        ]


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


class TestReadPath:
    def test_overview_serves_the_prebuilt_scenario_slice(self, service: AnalyticsService):
        service.rebuild(now=NOW)
        overview = service.get_overview("last_7_days")
        assert overview.kpi.active_users == 2

    def test_an_unknown_scenario_falls_back_to_a_zeroed_overview(self, service: AnalyticsService):
        service.rebuild(now=NOW)
        overview = service.get_overview("last_30_days_but_wrong")
        assert overview.kpi.active_users == 0

    def test_a_workspace_filter_recomputes_from_raw_events(self, service: AnalyticsService):
        service.rebuild(now=NOW)
        overview = service.get_overview("last_7_days", workspace_id="ws-2")
        assert overview.kpi.active_users == 1
        assert overview.kpi.total_page_views == 0

    def test_all_is_treated_as_no_filter(self, service: AnalyticsService):
        service.rebuild(now=NOW)
        assert service.get_overview("last_7_days", workspace_id="all").kpi.active_users == 2

    def test_metadata_round_trips(self, service: AnalyticsService):
        service.rebuild(now=NOW)
        assert service.get_metadata().events.count == 5

    def test_metadata_is_none_before_any_rebuild(self):
        assert AnalyticsService(storage=FakeStorage()).get_metadata() is None

    def test_scenarios_are_computed_live_without_a_rebuild(self):
        scenarios = AnalyticsService(storage=FakeStorage()).get_scenarios()
        assert [s.scenario_id for s in scenarios.scenarios] == [
            "today",
            "yesterday",
            "last_7_days",
            "last_30_days",
            "last_90_days",
        ]


# ---------------------------------------------------------------------------
# Rebuild scheduling (Phase 1)
# ---------------------------------------------------------------------------


class TestRebuildScheduler:
    """The scheduler is process-wide because AnalyticsService is per-request."""

    def test_a_burst_of_ingests_produces_one_rebuild(self):
        storage = FakeStorage()
        scheduler = _RebuildScheduler(debounce=0.05, max_delay=5.0)
        # A fresh service per call, exactly as the FastAPI dependency does.
        for i in range(10):
            service = AnalyticsService(storage=storage)
            service.ingest_event(AnalyticsEvent(**{**FIXTURE[0], "event_id": f"b{i}"}))
            scheduler.schedule(service)
        assert storage.write_counts.get(EVENTS_FILE, 0) == 0
        _wait_for(lambda: storage.write_counts.get(EVENTS_FILE, 0) == 1)
        assert storage.write_counts[EVENTS_FILE] == 1

    def test_a_steady_trickle_still_rebuilds_at_the_ceiling(self):
        storage = FakeStorage()
        scheduler = _RebuildScheduler(debounce=0.5, max_delay=0.1)
        deadline = time.monotonic() + 2.0
        # Each call would push a pure debounce out forever; the ceiling fires.
        while time.monotonic() < deadline and not storage.write_counts.get(EVENTS_FILE):
            scheduler.schedule(AnalyticsService(storage=storage))
            time.sleep(0.02)
        assert storage.write_counts.get(EVENTS_FILE, 0) >= 1

    def test_scheduling_during_a_rebuild_queues_exactly_one_more(self):
        started = threading.Event()
        release = threading.Event()

        # Every rebuild reads the event log exactly once, so counting reads
        # counts rebuilds — writes do not, since an unchanged aggregate is
        # skipped and a re-run over the same events writes nothing.
        class BlockingStorage(FakeStorage):
            def __init__(self) -> None:
                super().__init__()
                self.read_count = 0

            def list_events(self):
                self.read_count += 1
                if self.read_count == 1:
                    started.set()
                    release.wait(timeout=2)
                return super().list_events()

        blocking = BlockingStorage()
        scheduler = _RebuildScheduler(debounce=0.01, max_delay=1.0)
        scheduler.schedule(AnalyticsService(storage=blocking))
        assert started.wait(timeout=2)
        # Three more arrive mid-flight; they must collapse into one re-run.
        for _ in range(3):
            scheduler.schedule(AnalyticsService(storage=blocking))
        release.set()
        _wait_for(lambda: blocking.read_count >= 2)
        time.sleep(0.2)
        assert blocking.read_count == 2

    def test_a_failing_rebuild_does_not_wedge_the_scheduler(self):
        class BrokenStorage(FakeStorage):
            def list_events(self):
                raise RuntimeError("storage down")

        scheduler = _RebuildScheduler(debounce=0.01, max_delay=1.0)
        scheduler.schedule(AnalyticsService(storage=BrokenStorage()))
        time.sleep(0.15)
        healthy = FakeStorage()
        scheduler.schedule(AnalyticsService(storage=healthy))
        _wait_for(lambda: healthy.write_counts.get(EVENTS_FILE, 0) == 1)

    def test_ingest_arms_the_shared_scheduler(self, monkeypatch):
        storage = FakeStorage()
        armed: list[Any] = []
        monkeypatch.setattr(
            analytics_service, "_rebuild_scheduler", _StubScheduler(armed), raising=True
        )
        AnalyticsService(storage=storage).ingest_event(AnalyticsEvent(**FIXTURE[0]))
        assert len(armed) == 1


class TestUnchangedAggregatesAreNotRewritten:
    def test_a_second_identical_rebuild_rewrites_only_what_changed(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        service.rebuild(now=NOW)
        first = dict(storage.write_counts)
        service.rebuild(now=NOW)
        # metadata carries updated_at/duration_ms, so it always changes.
        assert storage.write_counts[METADATA_FILE] == first[METADATA_FILE] + 1
        for file_name in (EVENTS_FILE, OVERVIEW_FILE, USERS_FILE, USER_DETAILS_FILE):
            assert storage.write_counts[file_name] == first[file_name], file_name

    def test_a_new_event_rewrites_the_aggregates_it_touches(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        service.rebuild(now=NOW)
        before = dict(storage.write_counts)
        storage.events.append(
            ev(
                "e6",
                "2026-09-09T11:30:00Z",
                email="carol@example.com",
                user_id="u-carol",
                session_id="s4",
            )
        )
        service.rebuild(now=NOW)
        assert storage.write_counts[EVENTS_FILE] == before[EVENTS_FILE] + 1
        assert storage.write_counts[OVERVIEW_FILE] == before[OVERVIEW_FILE] + 1
        assert storage.write_counts[USERS_FILE] == before[USERS_FILE] + 1

    def test_metadata_still_lists_every_aggregate_even_when_skipped(
        self, service: AnalyticsService, storage: FakeStorage
    ):
        service.rebuild(now=NOW)
        metadata = service.rebuild(now=NOW)
        assert {a.file for a in metadata.aggregates} == {
            SCENARIO_FILE,
            OVERVIEW_FILE,
            USERS_FILE,
            SESSIONS_FILE,
            PAGES_FILE,
            WORKSPACES_FILE,
            USER_DETAILS_FILE,
            RECENT_EVENTS_FILE,
        }

    def test_a_failed_write_is_retried_on_the_next_rebuild(self, storage: FakeStorage):
        service = AnalyticsService(storage=storage)
        boom = {"n": 0}
        real_save = storage.save_json

        def flaky(file_name: str, data: Any) -> None:
            if file_name == OVERVIEW_FILE and boom["n"] == 0:
                boom["n"] = 1
                raise RuntimeError("write failed")
            real_save(file_name, data)

        storage.save_json = flaky  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            service.rebuild(now=NOW)
        storage.save_json = real_save  # type: ignore[method-assign]
        service.rebuild(now=NOW)
        assert OVERVIEW_FILE in storage.json


# ---------------------------------------------------------------------------
# Phase 2: the event log must produce byte-identical aggregates
# ---------------------------------------------------------------------------


class TestEventLogEquivalence:
    """The migration is only safe if the aggregates do not move."""

    @staticmethod
    def _rebuild_with(storage: AnalyticsStoragePort) -> dict[str, Any]:
        analytics_service._last_written_digests.clear()
        AnalyticsService(storage=storage).rebuild(now=NOW)
        return storage

    def test_both_adapters_produce_the_same_aggregates(self):
        from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary import (
            AnalyticsSecondaryAdapterEventLog,
        )

        legacy = FakeStorage()
        legacy.events = [dict(e) for e in FIXTURE]

        events = _RealEventService()
        backing = FakeStorage()
        migrated = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=backing)
        for raw in FIXTURE:
            migrated.save_event(dict(raw))

        self._rebuild_with(legacy)
        self._rebuild_with(migrated)

        for file_name in (
            EVENTS_FILE,
            OVERVIEW_FILE,
            USERS_FILE,
            SESSIONS_FILE,
            PAGES_FILE,
            WORKSPACES_FILE,
            USER_DETAILS_FILE,
            RECENT_EVENTS_FILE,
            SCENARIO_FILE,
        ):
            assert backing.json[file_name] == legacy.json[file_name], file_name

    def test_a_tracker_payload_survives_the_real_codec_unchanged(self):
        from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary import (
            AnalyticsSecondaryAdapterEventLog,
        )

        adapter = AnalyticsSecondaryAdapterEventLog(
            events=_RealEventService(), object_storage_adapter=FakeStorage()
        )
        original = {
            **FIXTURE[0],
            "properties": {"button": "export", "nested": {"n": 1}, "flag": True},
            "country": "FR",
            "count": 3,
            "ratio": 0.5,
        }
        adapter.save_event(dict(original))
        assert adapter.list_events() == [original]
