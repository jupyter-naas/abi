"""Search line chart: per-period matched ingest counts, not a cumulative sample."""

from datetime import UTC, datetime

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_recents_tweets import (
    linecharts,
)


class _Ctx:
    built_at = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    queries = [{"name": "drones_and_uas", "query": "drone OR drones"}]
    scenarios = [
        {
            "id": "24h",
            "start_time": "2026-08-13T10:00:00+00:00",
            "end_time": "2026-08-14T10:00:00+00:00",
        }
    ]
    saved: dict | None = None

    def ingested_timeseries(self, query, start, end):
        del query, start, end
        return [
            {
                "start": "2026-08-12T12:00:00+00:00",
                "end": "2026-08-12T13:00:00+00:00",
                "count": 4,
            },
            {
                "start": "2026-08-13T12:00:00+00:00",
                "end": "2026-08-13T13:00:00+00:00",
                "count": 3,
            },
            {
                "start": "2026-08-13T14:00:00+00:00",
                "end": "2026-08-13T15:00:00+00:00",
                "count": 2,
            },
        ]

    def aggregate_buckets(self, buckets, start, end, *, daily):
        return SnapshotContext.aggregate_buckets(self, buckets, start, end, daily=daily)

    def save_json(self, folder, name, doc):
        del folder, name
        self.saved = doc


def test_search_linechart_is_hourly_counts_not_cumulative():
    ctx = _Ctx()
    doc = linecharts.publish(ctx)  # type: ignore[arg-type]
    chart = doc["linecharts"][0]
    assert chart["granularity"] == "hour"
    current = chart["series"][0]["points"]
    previous = chart["series"][1]["points"]

    assert len(current) == 24
    assert len(previous) == 24
    # 10:00, 11:00, 12:00, 13:00, 14:00 — counts, not a running total.
    assert [p["value"] for p in current[:5]] == [0, 0, 3, 0, 2]
    assert sum(p["value"] for p in current) == 5
    # Previous window is the 24h before 13T10:00, so 12T12:00 lines up by index.
    assert previous[2]["value"] == 4
