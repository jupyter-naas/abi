"""FastAPI routes for the Yahoo Finance screener app."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from naas_abi_marketplace.applications.yahoofinance.apps.screener.schema import (
    public_schema,
)
from naas_abi_marketplace.applications.yahoofinance.integrations.utils.DedupScreenerOrgs import (
    dedup_records,
)
from naas_abi_marketplace.applications.yahoofinance.integrations.YahooFinanceScreenerIntegration import (
    INCLUDE_FIELDS,
    REGIONS,
    _join_output,
    _page,
    build_payload,
    fetch_all_pages,
    fetch_screener,
    local_screener_root,
    output_dir_for,
    save_json,
)

DATA_DIR = local_screener_root()
from pydantic import BaseModel, Field

router = APIRouter(tags=["yahoofinance-screener"])


class ScreenerRunRequest(BaseModel):
    size: int = Field(default=100, ge=1, le=250)
    offset: int = Field(default=0, ge=0)
    fetch_all: bool = False
    save: bool = False
    sector: str | None = "Technology"
    industry: str | None = "Software—Infrastructure"
    sort_type: str = "DESC"
    sort_field: str = "intradaymarketcap"
    min_revenue: float | None = 0
    include_fields: list[str] | None = None
    regions: list[str] | None = None
    cookie: str | None = None
    crumb: str | None = None
    formatted: bool = True
    use_records_response: bool = True
    lang: str = "en-US"
    query_region: str = "US"
    require_positive: bool = True
    view: str = "listings"


class DedupRequest(BaseModel):
    records: list[dict[str, Any]]
    view: str = "organizations"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def flatten_organization(org: dict[str, Any]) -> dict[str, Any]:
    """Spread the primary listing onto an organization row for the table."""
    listings = org.get("parameters", {}).get("listings") or []
    primary = listings[0] if listings else {}
    row = dict(primary)
    row.update(
        {
            "companyName": org.get("companyName"),
            "sector": org.get("sector"),
            "industry": org.get("industry"),
            "primaryTicker": org.get("primaryTicker"),
            "ticker": org.get("primaryTicker") or primary.get("ticker"),
            "listingCount": org.get("listingCount", len(listings)),
            "stockIds": ", ".join(
                str(item)
                for item in (org.get("parameters", {}).get("stockIds") or [])
                if item
            ),
        }
    )
    return row


def extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("organizations"), list):
        return payload["organizations"]
    return list(_page(payload).get("records") or [])


def rows_for_view(payload: dict[str, Any], view: str) -> list[dict[str, Any]]:
    if view not in {"listings", "organizations"}:
        raise HTTPException(
            status_code=400, detail="view must be listings or organizations"
        )
    if isinstance(payload.get("organizations"), list):
        organizations = payload["organizations"]
        if view == "listings":
            rows: list[dict[str, Any]] = []
            for org in organizations:
                company = org.get("companyName")
                for listing in org.get("parameters", {}).get("listings") or []:
                    row = dict(listing)
                    row["companyName"] = company
                    row["sector"] = org.get("sector")
                    row["industry"] = org.get("industry")
                    row["primaryTicker"] = org.get("primaryTicker")
                    row["listingCount"] = org.get("listingCount")
                    rows.append(row)
            return rows
        return [flatten_organization(org) for org in organizations]

    records = extract_records(payload)
    if view == "organizations":
        return [flatten_organization(org) for org in dedup_records(records)]
    return records


def resolve_snapshot(relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HTTPException(status_code=400, detail="Invalid snapshot path")
    path = (DATA_DIR / candidate).resolve()
    data_root = DATA_DIR.resolve()
    if path != data_root and data_root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid snapshot path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return path


def list_snapshots() -> list[dict[str, Any]]:
    if not DATA_DIR.exists():
        return []
    snapshots: list[dict[str, Any]] = []
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.name.startswith("."):
            continue
        relative = path.relative_to(DATA_DIR).as_posix()
        snapshots.append(
            {
                "id": relative,
                "name": path.name,
                "sector": path.relative_to(DATA_DIR).parts[0]
                if path.parent != DATA_DIR
                else None,
                "modified": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=UTC
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    snapshots.sort(key=lambda item: item["modified"], reverse=True)
    return snapshots


def run_response(
    payload: dict[str, Any], view: str, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    rows = rows_for_view(payload, view)
    page = _page(payload) if "finance" in payload else {}
    body = {
        "view": view,
        "count": len(rows),
        "total": page.get("total", len(rows)),
        "start": page.get("start", 0),
        "rows": rows,
    }
    if extra:
        body.update(extra)
    return body


@router.get("/schema")
def get_schema() -> dict[str, Any]:
    return public_schema()


@router.post("/payload")
def preview_payload(body: ScreenerRunRequest) -> dict[str, Any]:
    try:
        payload = build_payload(
            body.size,
            body.offset,
            _blank_to_none(body.sector),
            _blank_to_none(body.industry),
            body.sort_type,
            body.sort_field,
            body.min_revenue,
            body.include_fields or list(INCLUDE_FIELDS),
            body.regions or list(REGIONS),
            body.require_positive,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "query": {
            "formatted": body.formatted,
            "useRecordsResponse": body.use_records_response,
            "lang": body.lang,
            "region": body.query_region,
        },
        "body": payload,
    }


@router.post("/run")
def run_screener(body: ScreenerRunRequest) -> dict[str, Any]:
    sector = _blank_to_none(body.sector)
    industry = _blank_to_none(body.industry)
    kwargs = {
        "sector": sector,
        "industry": industry,
        "sort_type": body.sort_type,
        "sort_field": body.sort_field,
        "min_revenue": body.min_revenue,
        "include_fields": body.include_fields or list(INCLUDE_FIELDS),
        "regions": body.regions or list(REGIONS),
        "require_positive": body.require_positive,
        "cookie": _blank_to_none(body.cookie),
        "crumb": _blank_to_none(body.crumb),
        "formatted": body.formatted,
        "use_records_response": body.use_records_response,
        "lang": body.lang,
        "query_region": body.query_region,
    }
    export_root = None
    page_log_dir = None
    if body.save:
        export_root = output_dir_for(sector, industry)
        if body.fetch_all:
            page_log_dir = _join_output(
                export_root, datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            )
        else:
            page_log_dir = export_root
    try:
        if body.fetch_all:
            payload = fetch_all_pages(
                body.size,
                body.offset,
                combined_output_dir=export_root,
                page_log_dir=page_log_dir,
                **kwargs,
            )
        else:
            payload = fetch_screener(body.size, body.offset, **kwargs)
            if page_log_dir is not None:
                save_json(
                    payload,
                    _join_output(
                        page_log_dir, f"{body.offset}_{body.size}_screener.json"
                    ),
                )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    extra: dict[str, Any] = {}
    if export_root is not None:
        extra["savedTo"] = export_root
        if page_log_dir is not None and page_log_dir != export_root:
            extra["pageLogDir"] = page_log_dir
    return run_response(payload, body.view, extra)


@router.get("/snapshots")
def get_snapshots() -> dict[str, Any]:
    return {"snapshots": list_snapshots()}


@router.get("/snapshot")
def get_snapshot(id: str, view: str = "listings") -> dict[str, Any]:
    path = resolve_snapshot(id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Snapshot is not valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Snapshot is not a JSON object")
    return run_response(payload, view, {"id": id})


@router.post("/dedup")
def dedup(body: DedupRequest) -> dict[str, Any]:
    payload = {"organizations": dedup_records(body.records)}
    return run_response(payload, body.view)
