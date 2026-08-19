#!/usr/bin/env python3
"""Generate the **fake** Fixed Assets demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → this script

Answers "how are our assets evolving?". The balance sheet already states the
net book value of the two non-current asset lines — Intangible assets and
Property, plant & equipment — every month. This script decides only **what
those lines are made of**: an asset register, each item with its acquisition
date, its useful life and its straight-line depreciation, so the register's net
values sum back to the balance sheet exactly, month by month.

The register is built in relative units first, then each class is scaled by
``balance-sheet net ÷ register net`` for that month. Gross value, accumulated
depreciation and net value are all scaled by the same factor, so the identity

    net = gross − accumulated depreciation

survives, and the class total lands on the balance sheet to the cent.

Acquisitions and disposals are real events on the timeline: an asset acquired
in a month appears from that month, a disposed one drops out of the register
and its last net book value is booked as the disposal.

Record kinds (`kind` discriminator):
  - ``asset`` — one asset, per period-end snapshot (a **stock**: read the
    latest period, never sum across months).
  - ``memo``  — per-period aggregates: ``gross_value``, ``net_value``,
    ``accumulated_depreciation``, ``depreciation_charge``, ``acquisitions``,
    ``disposals`` (the last three are **flows**: sum them over the window).

Run from the app root (after performance/balance_sheet.py):
    python scripts/comptabilite/fixed_assets.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
from dataclasses import dataclass
from datetime import date, datetime

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")

FA_PAGE_ID = "fixed-assets"
FA_RELATIVE_PATH = "fixed_assets/fixed_assets.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
SCHEMA_VERSION = "1.0"

INTANGIBLE_LINE = "Intangible assets"
TANGIBLE_LINE = "Property, plant & equipment"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Assets already on the books when the timeline opens were acquired somewhere
# in this window.
LEGACY_ACQUISITION_YEARS = (2015, 2022)

SITES = ("Paris HQ", "Lyon plant", "Lille warehouse", "Madrid office")

# Size of an asset acquired during the timeline, relative to a legacy one.
NEW_ASSET_SCALE = 0.30

# Useful life an asset must have left for a disposal to be worth booking.
DISPOSAL_MIN_MONTHS = 8


@dataclass(frozen=True)
class CategoryDef:
    key: str
    label: str
    # tangible | intangible — must match the balance-sheet line it belongs to.
    asset_class: str
    # Share of the class's gross value.
    weight: float
    useful_life_years: int
    # Assets already held when the timeline opens.
    legacy_count: int
    # Assets acquired during the timeline.
    new_count: int
    # Assets disposed of during the timeline.
    disposal_count: int
    names: tuple[str, ...]


CATEGORIES = [
    CategoryDef(
        "buildings", "Buildings & fit-out", "tangible", 0.44, 25, 3, 1, 0,
        ("Paris HQ fit-out", "Lyon plant building", "Lille warehouse shell",
         "Madrid office fit-out"),
    ),
    CategoryDef(
        "production", "Production equipment", "tangible", 0.28, 10, 5, 3, 1,
        ("Assembly line A", "Assembly line B", "CNC milling centre",
         "Press unit 400T", "Packaging line", "Quality bench",
         "Robotic welding cell", "Paint booth", "Conveyor system"),
    ),
    CategoryDef(
        "tooling", "Tooling & fixtures", "tangible", 0.09, 7, 3, 2, 1,
        ("Injection mould set", "Press tooling kit", "Calibration jigs",
         "Assembly fixtures", "Cutting die set"),
    ),
    CategoryDef(
        "vehicles", "Vehicles & fleet", "tangible", 0.07, 5, 4, 3, 2,
        ("Delivery van #1", "Delivery van #2", "Forklift #1", "Forklift #2",
         "Company car pool", "Utility truck"),
    ),
    CategoryDef(
        "it_hardware", "IT hardware", "tangible", 0.07, 4, 3, 3, 1,
        ("Data centre racks", "Laptop fleet 2021", "Laptop fleet 2024",
         "Network backbone", "Workshop terminals", "Meeting-room AV"),
    ),
    CategoryDef(
        "furniture", "Office furniture", "tangible", 0.05, 8, 2, 1, 0,
        ("Paris HQ furniture", "Lyon office furniture", "Madrid furniture"),
    ),
    CategoryDef(
        "erp", "ERP & core systems", "intangible", 0.38, 8, 2, 1, 0,
        ("ERP core implementation", "Finance module rollout", "MES deployment"),
    ),
    CategoryDef(
        "software", "Software licences", "intangible", 0.24, 5, 3, 2, 1,
        ("CAD licence pool", "BI platform licences", "CRM licences",
         "Security suite", "PLM licences", "Design suite"),
    ),
    CategoryDef(
        "development", "Capitalised development", "intangible", 0.21, 5, 2, 3, 0,
        ("Product platform v2", "Customer portal", "Mobile app",
         "Automation toolchain", "Data pipeline"),
    ),
    CategoryDef(
        "patents", "Patents & trademarks", "intangible", 0.17, 10, 3, 1, 0,
        ("Process patent FR-2019", "Brand portfolio", "Alloy patent EU",
         "Design registrations"),
    ),
]

CLASS_LABELS = {"tangible": "Property, plant & equipment", "intangible": "Intangible assets"}
CLASS_LINES = {"tangible": TANGIBLE_LINE, "intangible": INTANGIBLE_LINE}


@dataclass
class Asset:
    ref: str
    name: str
    category: CategoryDef
    site: str
    acquired: date
    disposed: date | None
    # Gross value in relative units — scaled to the balance sheet per period.
    raw_gross: float

    @property
    def life_months(self) -> int:
        return self.category.useful_life_years * 12


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"fa-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _class_lines(balance_sheet: dict) -> tuple[list[tuple[str, str, str]], dict[str, dict[str, float]]]:
    """``[(period, scenario, scenario_year)]`` and ``{class: {period: net}}``."""
    periods: dict[str, tuple[str, str]] = {}
    values: dict[str, dict[str, float]] = {"tangible": {}, "intangible": {}}
    for record in balance_sheet.get("records", []):
        category = record.get("category")
        if category not in (INTANGIBLE_LINE, TANGIBLE_LINE):
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        asset_class = "intangible" if category == INTANGIBLE_LINE else "tangible"
        values[asset_class][period] = float(record["amount"])
    ordered = [(period, *periods[period]) for period in sorted(periods)]
    return ordered, values


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _month_start(rng: random.Random, year: int) -> date:
    return date(year, rng.randint(1, 12), 1)


def _build_register(rng: random.Random, periods: list[tuple[str, str, str]]) -> list[Asset]:
    """The asset register in relative units, with acquisitions and disposals."""
    first = date.fromisoformat(periods[0][0])
    last = date.fromisoformat(periods[-1][0])
    assets: list[Asset] = []

    for category in CATEGORIES:
        total = category.legacy_count + category.new_count
        # Weights inside the category, so a few items dominate as they would in
        # a real register. Assets bought during the timeline are deliberately
        # smaller than the legacy base — a year of capex renews a fraction of
        # the register, it does not rebuild it.
        shares = [
            (0.4 + rng.random() * 1.4)
            * (1.0 if index < category.legacy_count else NEW_ASSET_SCALE)
            for index in range(total)
        ]
        share_sum = sum(shares)
        # Acquisition months for the assets bought during the timeline, spread
        # across the window rather than bunched.
        window_months = _months_between(first, last)
        new_months = sorted(
            rng.sample(range(2, max(3, window_months - 2)), category.new_count)
        ) if category.new_count else []

        for index in range(total):
            legacy = index < category.legacy_count
            if legacy:
                acquired = _month_start(rng, rng.randint(*LEGACY_ACQUISITION_YEARS))
            else:
                offset = new_months[index - category.legacy_count]
                month = first.month + offset
                acquired = date(first.year + (month - 1) // 12, (month - 1) % 12 + 1, 1)

            name = category.names[index % len(category.names)]
            assets.append(
                Asset(
                    ref=f"FA-{category.key[:3].upper()}-{index + 1:03d}",
                    name=name,
                    category=category,
                    site=SITES[rng.randrange(len(SITES))],
                    acquired=acquired,
                    disposed=None,
                    raw_gross=category.weight * shares[index] / share_sum,
                )
            )

        # Disposals only touch assets that were already on the books, and are
        # scheduled while the asset still has book value left — selling off a
        # fully depreciated item would show up as a disposal of zero.
        candidates = [
            asset
            for asset in assets[-total:]
            if asset.acquired < first and asset.disposed is None
        ]
        rng.shuffle(candidates)
        disposed = 0
        for asset in candidates:
            if disposed >= category.disposal_count:
                break
            # Last month at which the asset still has ``DISPOSAL_MIN_MONTHS``
            # of useful life to write off.
            latest = _months_between(first, asset.acquired) + asset.life_months
            latest = min(window_months - 1, latest - DISPOSAL_MIN_MONTHS)
            earliest = window_months // 4
            if latest < earliest:
                continue
            month = first.month + rng.randint(earliest, latest)
            asset.disposed = date(
                first.year + (month - 1) // 12, (month - 1) % 12 + 1, 1
            )
            disposed += 1

    return assets


def _build_records(entity_id: str, balance_sheet: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods, class_values = _class_lines(balance_sheet)
    if not periods:
        return []
    assets = _build_register(rng, periods)

    records: list[dict] = []
    # Net book value carried from the previous month, so a disposal can be
    # booked at what the asset was actually worth when it left.
    previous_net: dict[str, float] = {}

    for period, scenario, scenario_year in periods:
        period_end = date.fromisoformat(period)
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }

        held = [
            asset
            for asset in assets
            if asset.acquired <= period_end
            and (asset.disposed is None or asset.disposed > period_end)
        ]

        # --- register in relative units, then scaled onto the balance sheet ---
        raw: dict[str, tuple[float, float, float, int]] = {}
        raw_net_by_class = {"tangible": 0.0, "intangible": 0.0}
        for asset in held:
            months = min(_months_between(asset.acquired, period_end), asset.life_months)
            months = max(0, months)
            accumulated = asset.raw_gross * months / asset.life_months
            net = asset.raw_gross - accumulated
            remaining = max(0, asset.life_months - months)
            raw[asset.ref] = (asset.raw_gross, accumulated, net, remaining)
            raw_net_by_class[asset.category.asset_class] += net

        scale = {
            asset_class: (
                class_values[asset_class].get(period, 0.0) / raw_net
                if raw_net > 0
                else 0.0
            )
            for asset_class, raw_net in raw_net_by_class.items()
        }

        gross_total = {"tangible": 0.0, "intangible": 0.0}
        accumulated_total = {"tangible": 0.0, "intangible": 0.0}
        charge_total = {"tangible": 0.0, "intangible": 0.0}
        acquisitions = 0.0
        current_net: dict[str, float] = {}

        for asset in held:
            asset_class = asset.category.asset_class
            factor = scale[asset_class]
            raw_gross, raw_accumulated, raw_net, remaining = raw[asset.ref]
            gross = raw_gross * factor
            accumulated = raw_accumulated * factor
            net = raw_net * factor
            monthly = (gross / asset.life_months) if remaining > 0 else 0.0

            gross_total[asset_class] += gross
            accumulated_total[asset_class] += accumulated
            charge_total[asset_class] += monthly
            current_net[asset.ref] = net
            if (asset.acquired.year, asset.acquired.month) == (
                period_end.year,
                period_end.month,
            ):
                acquisitions += gross

            records.append(
                {
                    **common,
                    "kind": "asset",
                    "asset_ref": asset.ref,
                    "asset_name": asset.name,
                    "category": asset.category.key,
                    "category_label": asset.category.label,
                    "asset_class": asset_class,
                    "asset_class_label": CLASS_LABELS[asset_class],
                    "site": asset.site,
                    "acquisition_date": asset.acquired.isoformat(),
                    "disposal_date": asset.disposed.isoformat() if asset.disposed else "",
                    "useful_life_years": asset.category.useful_life_years,
                    "depreciation_method": "straight_line",
                    "gross_value": round(gross, 2),
                    "accumulated_depreciation": round(accumulated, 2),
                    "net_value": round(net, 2),
                    "monthly_depreciation": round(monthly, 2),
                    "remaining_months": remaining,
                    "is_fully_depreciated": remaining == 0,
                    # The stock the page reads — kept as `amount` so the shared
                    # dataset validator sees a numeric value.
                    "amount": round(net, 2),
                }
            )

        # --- disposals: assets that left the register this month --------------
        disposals = sum(
            previous_net.get(asset.ref, 0.0)
            for asset in assets
            if asset.disposed is not None
            and (asset.disposed.year, asset.disposed.month)
            == (period_end.year, period_end.month)
        )
        previous_net = current_net

        for metric, label, amount in (
            ("gross_value", "Gross value", sum(gross_total.values())),
            ("net_value", "Net value", sum(current_net.values())),
            (
                "accumulated_depreciation",
                "Accumulated depreciation",
                sum(accumulated_total.values()),
            ),
            ("depreciation_charge", "Depreciation charge", sum(charge_total.values())),
            ("acquisitions", "Acquisitions", acquisitions),
            ("disposals", "Disposals", disposals),
        ):
            records.append(
                {
                    **common,
                    "kind": "memo",
                    "metric": metric,
                    "metric_label": label,
                    "asset_ref": "",
                    "asset_name": label,
                    "category": "memo",
                    "category_label": "Memo",
                    "asset_class": "memo",
                    "asset_class_label": "Memo",
                    "site": "",
                    "acquisition_date": "",
                    "disposal_date": "",
                    "useful_life_years": 0,
                    "depreciation_method": "",
                    "gross_value": 0.0,
                    "accumulated_depreciation": 0.0,
                    "net_value": 0.0,
                    "monthly_depreciation": 0.0,
                    "remaining_months": 0,
                    "is_fully_depreciated": False,
                    "amount": round(amount, 2),
                }
            )

    return records


def _scenarios(payload: dict, records: list[dict]) -> list[dict[str, str]]:
    """Reuse the upstream scenario list, or rebuild it from the records."""
    existing = payload.get("scenarios")
    if existing:
        return existing
    months = sorted({record["scenario"] for record in records})
    years = sorted({record["scenario_year"] for record in records})
    options: list[dict[str, str]] = [
        {"id": year, "label": year, "split": "date_year"} for year in reversed(years)
    ]
    for month in reversed(months):
        year_part, _, month_part = month.partition("-")
        options.append(
            {
                "id": month,
                "label": f"{MONTH_LABELS[int(month_part)]} {year_part}",
                "split": "date_month",
            }
        )
    return options


def _patch_manifest(entity_id: str, data_version: str) -> None:
    path = os.path.join(ENTITIES_DIR, entity_id, "manifest.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    pages = manifest.setdefault("datasets", {}).setdefault("pages", {})
    pages[FA_PAGE_ID] = [FA_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if os.path.exists(os.path.join(entity_dir, BS_RELATIVE_PATH)):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No balance sheet found — run scripts/performance/balance_sheet.py first."
        )
    print(f"Generating fake asset registers for {len(entities)} entity(ies)…")

    for entity_id in entities:
        balance_sheet = _load(entity_id, BS_RELATIVE_PATH)
        if balance_sheet is None:
            continue
        records = _build_records(entity_id, balance_sheet)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": _scenarios(balance_sheet, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "fixed_assets")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "fixed_assets.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
