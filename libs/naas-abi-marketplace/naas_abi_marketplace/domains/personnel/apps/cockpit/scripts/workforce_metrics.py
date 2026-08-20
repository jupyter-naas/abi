"""Tenure, seniority, and scolarity metrics from process temporal regions."""

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


def scolarity_for_person(
    studying_rows: list[dict],
    *,
    person_label: str,
    reference: date,
) -> dict[str, float | int | list[str] | str]:
    """Merged act-of-studying span for one person (same interval logic as seniority)."""
    person_rows = [row for row in studying_rows if row.get("personLabel") == person_label]
    study_intervals: list[tuple[date, date]] = []
    diplomas: list[str] = []
    seen_diplomas: set[str] = set()

    for row in person_rows:
        interval = act_interval(row, reference=reference)
        if interval:
            study_intervals.append(interval)
        for key in ("degreeLabel", "programName"):
            label = (row.get(key) or "").strip()
            if label and label not in seen_diplomas:
                seen_diplomas.add(label)
                diplomas.append(label)

    merged_study = merge_intervals(study_intervals)
    study_days = total_days(merged_study)

    return {
        "scolarity_days": study_days,
        "scolarity_years": days_to_years(study_days),
        "study_count": len(study_intervals),
        "education_count": len(diplomas),
        "diplomas": diplomas,
        "diploma_labels": "; ".join(diplomas),
    }


def build_workforce_metrics(
    roster_rows: list[dict],
    working_rows: list[dict],
    studying_rows: list[dict] | None = None,
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
    scolarity_values: list[float] = []
    org_year_days_total = 0
    study_rows = studying_rows or []

    for row in roster_rows:
        person_label = row.get("personLabel") or ""
        person_metrics = metrics_for_person(
            working_rows,
            person_label=person_label,
            org_label=org_label,
            reference=today,
            year_start=year_start,
            year_end=year_end,
        )
        study_metrics = scolarity_for_person(
            study_rows,
            person_label=person_label,
            reference=today,
        )
        enriched_row = {**row, **person_metrics, **study_metrics}
        enriched.append(enriched_row)
        seniority_values.append(float(person_metrics["seniority_years"]))
        if int(study_metrics["scolarity_days"]) > 0:
            scolarity_values.append(float(study_metrics["scolarity_years"]))
        org_year_days_total += int(person_metrics["org_time_in_year_days"])

    active_rows = [row for row in enriched if row.get("status_value") == "active"]
    avg_seniority = round(
        sum(seniority_values) / len(seniority_values),
        1,
    ) if seniority_values else 0.0
    avg_scolarity = round(
        sum(scolarity_values) / len(scolarity_values),
        1,
    ) if scolarity_values else 0.0

    kpis = {
        "active_headcount": {"value": len(active_rows)},
        "org_time_in_year": {"value": days_to_years(org_year_days_total), "unit": "years"},
        "avg_seniority": {"value": avg_seniority, "unit": "years"},
        "avg_scolarity": {"value": avg_scolarity, "unit": "years"},
    }
    return kpis, enriched
