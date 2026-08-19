from datetime import date

from naas_abi_marketplace.domains.personnel.scripts.workforce_metrics import (
    build_workforce_metrics,
    days_to_years,
    merge_intervals,
    total_days,
)


def test_merge_intervals_combines_overlaps() -> None:
    merged = merge_intervals(
        [
            (date(2020, 1, 1), date(2021, 12, 31)),
            (date(2021, 6, 1), date(2022, 5, 31)),
        ]
    )
    assert len(merged) == 1
    assert total_days(merged) == 882


def test_build_workforce_metrics_enriches_roster_and_kpis() -> None:
    roster = [
        {"personLabel": "Ada Lovelace", "status_value": "active"},
        {"personLabel": "Grace Hopper", "status_value": "terminated"},
    ]
    working = [
        {
            "personLabel": "Ada Lovelace",
            "orgLabel": "naas.ai",
            "temporalStart": "2024-01-01",
            "temporalEnd": None,
        },
        {
            "personLabel": "Ada Lovelace",
            "orgLabel": "Other Co",
            "temporalStart": "2020-01-01",
            "temporalEnd": "2023-12-31",
        },
        {
            "personLabel": "Grace Hopper",
            "orgLabel": "naas.ai",
            "temporalStart": "2018-01-01",
            "temporalEnd": "2020-12-31",
        },
    ]
    kpis, enriched = build_workforce_metrics(
        roster,
        working,
        org_label="naas.ai",
        reference=date(2026, 8, 19),
    )

    assert kpis["active_headcount"]["value"] == 1
    assert kpis["total_headcount"]["value"] == 2
    assert kpis["avg_seniority"]["value"] > 0
    assert enriched[0]["org_tenure_years"] > 0
    assert enriched[0]["experience_count"] == 2
    # Two acts (2020-2023 and 2024-present) merge to one career span, not double-counted.
    assert enriched[0]["seniority_years"] < 10
    assert enriched[0]["seniority_years"] >= enriched[0]["org_tenure_years"]


def test_seniority_merges_overlapping_career_acts() -> None:
    roster = [{"personLabel": "Ada Lovelace", "status_value": "active"}]
    working = [
        {
            "personLabel": "Ada Lovelace",
            "orgLabel": "Other Co",
            "temporalStart": "2020-01-01",
            "temporalEnd": "2022-12-31",
        },
        {
            "personLabel": "Ada Lovelace",
            "orgLabel": "Other Co",
            "temporalStart": "2021-06-01",
            "temporalEnd": "2023-12-31",
        },
    ]
    _, enriched = build_workforce_metrics(
        roster,
        working,
        org_label="naas.ai",
        reference=date(2026, 8, 19),
    )
    assert enriched[0]["experience_count"] == 2
    assert enriched[0]["seniority_years"] == days_to_years(total_days(merge_intervals([
        (date(2020, 1, 1), date(2023, 12, 31)),
    ])))
