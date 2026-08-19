"""Tenure and seniority metrics from act-of-working temporal regions."""

from __future__ import annotations

from datetime import date


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: item[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def interval_days(start: date, end: date) -> int:
    return max(0, (end - start).days + 1)


def overlap_days(
    start: date,
    end: date,
    *,
    window_start: date,
    window_end: date,
) -> int:
    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)
    if clipped_start > clipped_end:
        return 0
    return interval_days(clipped_start, clipped_end)


def total_days(intervals: list[tuple[date, date]]) -> int:
    return sum(interval_days(start, end) for start, end in intervals)


def days_to_years(days: int) -> float:
    return round(days / 365.25, 1)


def act_interval(row: dict, *, reference: date) -> tuple[date, date] | None:
    start = parse_iso_date(row.get("temporalStart"))
    if not start:
        return None
    end = parse_iso_date(row.get("temporalEnd")) or reference
    if end < start:
        return None
    return start, end


def is_org_act(row: dict, org_label: str) -> bool:
    label = (row.get("orgLabel") or "").strip().lower()
    return org_label.strip().lower() in label


def metrics_for_person(
    working_rows: list[dict],
    *,
    person_label: str,
    org_label: str,
    reference: date,
    year_start: date,
    year_end: date,
) -> dict[str, float | int]:
    person_rows = [row for row in working_rows if row.get("personLabel") == person_label]
    career_intervals: list[tuple[date, date]] = []
    org_intervals: list[tuple[date, date]] = []

    for row in person_rows:
        interval = act_interval(row, reference=reference)
        if not interval:
            continue
        career_intervals.append(interval)
        if is_org_act(row, org_label):
            org_intervals.append(interval)

    merged_career = merge_intervals(career_intervals)
    merged_org = merge_intervals(org_intervals)
    career_days = total_days(merged_career)
    org_year_days = sum(
        overlap_days(
            start,
            end,
            window_start=year_start,
            window_end=year_end,
        )
        for start, end in merged_org
    )

    return {
        "org_tenure_days": total_days(merged_org),
        "org_tenure_years": days_to_years(total_days(merged_org)),
        "org_time_in_year_days": org_year_days,
        "org_time_in_year_years": days_to_years(org_year_days),
        "seniority_days": career_days,
        "seniority_years": days_to_years(career_days),
        "experience_count": len(career_intervals),
    }


def build_workforce_metrics(
    roster_rows: list[dict],
    working_rows: list[dict],
    *,
    org_label: str,
    reference: date | None = None,
) -> tuple[dict, list[dict]]:
    """Return KPI payload and roster rows enriched with tenure fields."""
    today = reference or date.today()
    year_start = date(today.year, 1, 1)
    year_end = today

    enriched: list[dict] = []
    seniority_values: list[float] = []
    org_year_days_total = 0

    for row in roster_rows:
        person_metrics = metrics_for_person(
            working_rows,
            person_label=row.get("personLabel") or "",
            org_label=org_label,
            reference=today,
            year_start=year_start,
            year_end=year_end,
        )
        enriched_row = {**row, **person_metrics}
        enriched.append(enriched_row)
        seniority_values.append(float(person_metrics["seniority_years"]))
        org_year_days_total += int(person_metrics["org_time_in_year_days"])

    active_rows = [row for row in enriched if row.get("status_value") == "active"]
    terminated_rows = [
        row for row in enriched if row.get("status_value") == "terminated"
    ]
    avg_seniority = round(
        sum(seniority_values) / len(seniority_values),
        1,
    ) if seniority_values else 0.0

    kpis = {
        "active_headcount": {"value": len(active_rows)},
        "org_time_in_year": {"value": days_to_years(org_year_days_total), "unit": "years"},
        "avg_seniority": {"value": avg_seniority, "unit": "years"},
        "total_headcount": {"value": len(active_rows) + len(terminated_rows)},
    }
    return kpis, enriched
