"""Count page KPI snapshot: previous-period delta and scenario windows."""

from datetime import UTC, datetime

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x_proxy.api.count_recent_tweets import (
    kpis,
)


class _CountKpiCtx:
    built_at = datetime(2026, 7, 7, 16, 0, tzinfo=UTC)
    queries = [{"name": "drones_and_uas", "query": "drone"}]
    scenarios = [
        {
            "id": "24h",
            "start_time": "2026-07-06T16:00:00+00:00",
            "end_time": "2026-07-07T16:00:00+00:00",
        },
        {
            "id": "all",
            "start_time": "2026-07-06T16:00:00+00:00",
            "end_time": "2026-07-07T16:00:00+00:00",
        },
    ]
    saved: dict | None = None

    def timeseries(self, query):
        del query
        return [
            {
                "start": "2026-07-07T14:00:00+00:00",
                "end": "2026-07-07T15:00:00+00:00",
                "count": 100,
            },
            {
                "start": "2026-07-07T15:00:00+00:00",
                "end": "2026-07-07T16:00:00+00:00",
                "count": 50,
            },
        ]

    def aggregate_buckets(self, buckets, start, end, *, daily):
        return SnapshotContext.aggregate_buckets(self, buckets, start, end, daily=daily)

    def save_json(self, folder, name, doc):
        del folder, name
        self.saved = doc


def test_count_kpis_omit_delta_when_previous_period_is_empty():
    ctx = _CountKpiCtx()
    doc = kpis.publish(ctx)  # type: ignore[arg-type]
    by_scenario = {entry["scenario_id"]: entry for entry in doc["kpis"]}

    day = {item["id"]: item for item in by_scenario["24h"]["items"]}
    assert day["total"]["value"] == 150
    assert day["total"]["delta"] is None
    assert day["total"]["prev_value"] is None
    assert day["total"]["hint"] == "no prior period"
    assert day["mean"]["delta"] is None
    assert day["low"]["hint"] == "Jul 7, 15:00 – 16:00"
    assert day["high"]["hint"] == "Jul 7, 14:00 – 15:00"

    all_time = {item["id"]: item for item in by_scenario["all"]["items"]}
    assert all_time["total"]["value"] == 150
    assert all_time["total"]["delta"] is None
    assert all_time["total"]["hint"] == "all ingested counts"
