"""Tests for workforce and scolarity metrics."""

from datetime import date

from naas_abi_marketplace.domains.personnel.apps.cockpit.scripts.workforce_metrics import (
    build_workforce_metrics,
    scolarity_for_person,
)


def test_scolarity_merges_overlapping_study_intervals() -> None:
    studying_rows = [
        {
            "personLabel": "Florent Ravenel",
            "temporalStart": "2012-09-01",
            "temporalEnd": "2014-06-30",
        },
        {
            "personLabel": "Florent Ravenel",
            "temporalStart": "2014-01-01",
            "temporalEnd": "2016-06-30",
        },
    ]
    metrics = scolarity_for_person(
        studying_rows,
        person_label="Florent Ravenel",
        reference=date(2026, 8, 19),
    )
    assert metrics["study_count"] == 2
    assert metrics["scolarity_years"] == 3.8


def test_build_workforce_metrics_includes_avg_scolarity_kpi() -> None:
    roster_rows = [
        {"personLabel": "Florent Ravenel", "status_value": "active"},
        {"personLabel": "Jeremy Ravenel", "status_value": "active"},
        {"personLabel": "Alexis Monville", "status_value": "active"},
    ]
    studying_rows = [
        {
            "personLabel": "Florent Ravenel",
            "temporalStart": "2010-01-01",
            "temporalEnd": "2012-12-31",
            "degreeLabel": "Master's Degree, Corporate Finance",
        },
        {
            "personLabel": "Jeremy Ravenel",
            "temporalStart": "2005-01-01",
            "temporalEnd": "2007-12-31",
            "degreeLabel": "Baccalauréat Economique et Social, Economy & Sociology",
        },
    ]
    kpis, enriched = build_workforce_metrics(
        roster_rows,
        working_rows=[],
        studying_rows=studying_rows,
        org_label="naas.ai",
        reference=date(2026, 8, 19),
    )
    assert "avg_scolarity" in kpis
    assert enriched[0]["scolarity_years"] == 3.0
    assert enriched[0]["education_count"] == 1
    assert enriched[0]["diploma_labels"] == "Master's Degree, Corporate Finance"
    assert enriched[1]["scolarity_years"] == 3.0
    assert enriched[2]["scolarity_years"] == 0.0
    assert enriched[2]["diploma_labels"] == ""
    assert kpis["avg_scolarity"]["value"] == 3.0


def test_avg_scolarity_excludes_members_without_education() -> None:
    roster_rows = [
        {"personLabel": "Florent Ravenel", "status_value": "active"},
        {"personLabel": "Alexis Monville", "status_value": "active"},
    ]
    studying_rows = [
        {
            "personLabel": "Florent Ravenel",
            "temporalStart": "2010-01-01",
            "temporalEnd": "2012-12-31",
        },
    ]
    kpis, _ = build_workforce_metrics(
        roster_rows,
        working_rows=[],
        studying_rows=studying_rows,
        org_label="naas.ai",
        reference=date(2026, 8, 19),
    )
    assert kpis["avg_scolarity"]["value"] == 3.0
