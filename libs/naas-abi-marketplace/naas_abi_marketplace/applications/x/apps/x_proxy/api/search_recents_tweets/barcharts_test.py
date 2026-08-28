"""Top authors are ranked over the whole scenario window, not the table sample."""

from datetime import UTC, datetime

from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_recents_tweets import (
    barcharts,
)


class _Ctx:
    built_at = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    queries = [{"name": "drones_and_uas", "query": "drone OR drones"}]
    scenarios = [
        {
            "id": "24h",
            "start_time": "2026-08-13T10:00:00+00:00",
            "end_time": "2026-08-14T10:00:00+00:00",
        },
        {
            "id": "7d",
            "start_time": "2026-08-07T10:00:00+00:00",
            "end_time": "2026-08-14T10:00:00+00:00",
        },
        {
            "id": "all",
            "start_time": "2026-05-01T10:00:00+00:00",
            "end_time": "2026-08-14T10:00:00+00:00",
        },
    ]
    saved: dict | None = None
    facet_calls: list[tuple[str, str, str, int]] = []

    def __init__(self) -> None:
        self.facet_calls = []
        self.saved = None

    def facet_values_for_window(self, query, start, end, column, *, limit=500):
        del query
        self.facet_calls.append((start, end, column, limit))
        if column != "username":
            return []
        # 24h: alice dominates. 7d: bob has been posting all week.
        if start.startswith("2026-08-13"):
            return [{"value": "alice", "count": 40}, {"value": "bob", "count": 5}]
        if start.startswith("2026-08-12"):  # previous of 24h
            return [{"value": "alice", "count": 10}, {"value": "bob", "count": 8}]
        if start.startswith("2026-08-07"):
            return [{"value": "bob", "count": 90}, {"value": "alice", "count": 50}]
        if start.startswith("2026-07-31"):  # previous of 7d
            return [{"value": "bob", "count": 20}]
        return [{"value": "carol", "count": 200}, {"value": "bob", "count": 90}]

    def save_json(self, folder, name, doc):
        del folder, name
        self.saved = doc


def test_top_authors_differ_by_scenario_and_all_time_has_no_delta():
    ctx = _Ctx()
    doc = barcharts.publish(ctx)  # type: ignore[arg-type]
    by_id = {entry["scenario_id"]: entry for entry in doc["barcharts"]}

    day = {b["label"]: b for b in by_id["24h"]["items"][0]["bars"]}
    week = {b["label"]: b for b in by_id["7d"]["items"][0]["bars"]}
    all_time = {b["label"]: b for b in by_id["all"]["items"][0]["bars"]}

    assert list(day) == ["@alice", "@bob"]
    assert day["@alice"]["value"] == 40
    assert day["@alice"]["delta"] == 30
    assert week["@bob"]["value"] == 90
    assert week["@bob"]["delta"] == 70
    # Different windows, different ranking - not the newest-1000 sample.
    assert next(iter(week)) == "@bob"
    assert list(all_time) == ["@carol", "@bob"]
    assert all_time["@carol"]["delta"] is None
    assert all_time["@bob"]["delta"] is None
