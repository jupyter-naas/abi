"""Shape of the Search page KPI snapshot."""

from datetime import UTC, datetime

from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import kpis


class _Ctx:
    built_at = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    queries = [{"name": "drones_and_uas", "query": "drone OR drones"}]
    scenarios = [
        {
            "id": "7d",
            "start_time": "2026-08-07T10:00:00+00:00",
            "end_time": "2026-08-14T10:00:00+00:00",
        }
    ]
    saved: dict | None = None

    def banded_count_for_window(self, query, start, end, referenced=False):
        del query
        current = start.startswith("2026-08-07")
        if referenced:
            return 3994 if current else 3000
        return 16586 if current else 10000

    def sum_counts_in_window(self, query, start, end):
        del query, end
        return 20000 if start.startswith("2026-08-07") else 15000

    def save_json(self, folder, name, doc):
        del folder, name
        self.saved = doc


def test_search_kpis_split_matched_referenced_and_drop_count_total():
    ctx = _Ctx()
    doc = kpis.publish(ctx)  # type: ignore[arg-type]
    items = {it["id"]: it for it in doc["kpis"][0]["items"]}

    assert set(items) == {
        "tweets_ingested",
        "tweets",
        "referenced_tweets",
        "coverage",
    }

    ingested = items["tweets_ingested"]
    assert ingested["label"] == "Total Posts Ingested"
    assert ingested["value"] == 16586 + 3994
    assert ingested["delta"] == (16586 + 3994) - (10000 + 3000)
    assert ingested["hint"] == (
        "2026-08-07T10:00:00+00:00 to 2026-08-14T10:00:00+00:00"
    )

    tweets = items["tweets"]
    assert tweets["value"] == 16586
    assert tweets["delta"] == 6586
    assert tweets["hint"] == "80.6% of posts ingested"

    referenced = items["referenced_tweets"]
    assert referenced["value"] == 3994
    assert referenced["delta"] == 994
    assert referenced["hint"] == "19.4% of posts ingested"

    coverage = items["coverage"]
    assert coverage["value"] == 82.9  # 16586 / 20000
    assert coverage["unit"] == "%"
    assert coverage["hint"] == "20,000 tweets"
    assert "delta" not in coverage
