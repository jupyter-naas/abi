import type { Dataset } from '@/lib/types';

/**
 * Fixed assets engine. Two record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `asset` — one asset, per period-end snapshot. A **stock**: read the latest
 *   period in the window, never sum across months, or a single asset counts
 *   once per month it was held.
 * - `memo`  — per-period aggregates. `gross_value`, `net_value` and
 *   `accumulated_depreciation` are stocks (read the last period);
 *   `depreciation_charge`, `acquisitions` and `disposals` are flows (sum them).
 *
 * The register's net values sum back to the balance sheet's Intangible assets
 * and Property, plant & equipment lines for every month, which is what makes
 * this page agree with the Balance Sheet.
 */

export type FixedAssetRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'asset' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  asset_ref: string;
  asset_name: string;
  category: string;
  category_label: string;
  asset_class: string;
  asset_class_label: string;
  site: string;
  acquisition_date: string;
  disposal_date: string;
  useful_life_years: number;
  depreciation_method: string;
  gross_value: number;
  accumulated_depreciation: number;
  net_value: number;
  monthly_depreciation: number;
  remaining_months: number;
  is_fully_depreciated: boolean;
  amount: number;
};

/** Years of forward depreciation the schedule projects. */
export const SCHEDULE_YEARS = 5;

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isFixedAssetDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<FixedAssetRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function fixedAssetRecords(
  dataset: Dataset | undefined,
): FixedAssetRecord[] {
  if (!isFixedAssetDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'asset' || record.kind === 'memo'),
  );
}

/** "2026-12-31" → "Dec 2026". Falls back to the raw string when unparseable. */
export function formatPeriodLabel(period: string): string {
  const [year, month] = period.split('-');
  const index = Number(month) - 1;
  if (!year || index < 0 || index > 11) {
    return period;
  }
  return `${MONTH_ABBR[index]} ${year}`;
}

export type AssetGroup = {
  key: string;
  label: string;
  /** Net book value of the group at the as-of date. */
  amount: number;
  gross: number;
  count: number;
  share: number;
};

export type AssetEvolutionPoint = {
  period: string;
  label: string;
  gross: number;
  net: number;
  accumulated: number;
  charge: number;
};

export type DepreciationYear = {
  year: string;
  /** Charge the assets held at the as-of date will take that year. */
  amount: number;
};

export type FixedAssetKpis = {
  /** Stocks, read at the as-of date. */
  gross: number;
  net: number;
  accumulated: number;
  /** Share of the gross value already written off. */
  depreciationRate: number | null;
  /** Flows, summed across the window. */
  acquisitions: number;
  disposals: number;
  charge: number;
  assetCount: number;
  fullyDepreciated: number;
  /** Net-value-weighted mean remaining useful life, in years. */
  remainingLife: number | null;
};

export type FixedAssetView = {
  asOf: string | null;
  asOfLabel: string;
  kpis: FixedAssetKpis;
  categories: AssetGroup[];
  classes: AssetGroup[];
  evolution: AssetEvolutionPoint[];
  schedule: DepreciationYear[];
  /** The register at the as-of date, largest net value first. */
  assets: FixedAssetRecord[];
};

const EMPTY_KPIS: FixedAssetKpis = {
  gross: 0,
  net: 0,
  accumulated: 0,
  depreciationRate: null,
  acquisitions: 0,
  disposals: 0,
  charge: 0,
  assetCount: 0,
  fullyDepreciated: 0,
  remainingLife: null,
};

function groupAssets(
  assets: FixedAssetRecord[],
  keyOf: (asset: FixedAssetRecord) => string,
  labelOf: (asset: FixedAssetRecord) => string,
  total: number,
): AssetGroup[] {
  const keys: string[] = [];
  for (const asset of assets) {
    const key = keyOf(asset);
    if (!keys.includes(key)) {
      keys.push(key);
    }
  }
  return keys
    .map((key) => {
      const inGroup = assets.filter((asset) => keyOf(asset) === key);
      const amount = inGroup.reduce((sum, asset) => sum + asset.net_value, 0);
      return {
        key,
        label: labelOf(inGroup[0]),
        amount,
        gross: inGroup.reduce((sum, asset) => sum + asset.gross_value, 0),
        count: inGroup.length,
        share: total > 0 ? amount / total : 0,
      };
    })
    .sort((a, b) => b.amount - a.amount);
}

/**
 * Forward depreciation for the assets held at the as-of date, by calendar
 * year. Each asset contributes its monthly charge for as many of its remaining
 * months as fall in that year — no new capex is assumed, so the schedule is
 * what the register already commits to.
 */
function buildSchedule(
  assets: FixedAssetRecord[],
  asOf: string,
): DepreciationYear[] {
  const [yearPart, monthPart] = asOf.split('-');
  const startYear = Number(yearPart);
  const startMonth = Number(monthPart); // 1-12, the month just closed
  if (!Number.isFinite(startYear) || !Number.isFinite(startMonth)) {
    return [];
  }

  const horizon = SCHEDULE_YEARS * 12;
  const totals = new Map<number, number>();
  for (const asset of assets) {
    const months = Math.min(asset.remaining_months, horizon);
    for (let offset = 1; offset <= months; offset += 1) {
      const year = startYear + Math.floor((startMonth - 1 + offset) / 12);
      totals.set(year, (totals.get(year) ?? 0) + asset.monthly_depreciation);
    }
  }

  return Array.from(totals.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([year, amount]) => ({ year: String(year), amount }));
}

export function buildFixedAssets(records: FixedAssetRecord[]): FixedAssetView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const memoRows = records.filter((record) => record.kind === 'memo');
  const assets = records
    .filter((record) => record.kind === 'asset' && record.period === asOf)
    .sort((a, b) => b.net_value - a.net_value);

  const net = assets.reduce((sum, asset) => sum + asset.net_value, 0);
  const gross = assets.reduce((sum, asset) => sum + asset.gross_value, 0);
  const accumulated = assets.reduce(
    (sum, asset) => sum + asset.accumulated_depreciation,
    0,
  );

  const categories = groupAssets(
    assets,
    (asset) => asset.category,
    (asset) => asset.category_label,
    net,
  );
  const classes = groupAssets(
    assets,
    (asset) => asset.asset_class,
    (asset) => asset.asset_class_label,
    net,
  );

  const evolution: AssetEvolutionPoint[] = periodIds.map((period) => {
    const metricOf = (metric: string) =>
      memoRows
        .filter((record) => record.period === period && record.metric === metric)
        .reduce((sum, record) => sum + record.amount, 0);
    return {
      period,
      label: formatPeriodLabel(period),
      gross: metricOf('gross_value'),
      net: metricOf('net_value'),
      accumulated: metricOf('accumulated_depreciation'),
      charge: metricOf('depreciation_charge'),
    };
  });

  // Flows are summed across the window; stocks come from the as-of snapshot.
  const flowOf = (metric: string) =>
    memoRows
      .filter((record) => record.metric === metric)
      .reduce((sum, record) => sum + record.amount, 0);

  const lifeWeight = assets.reduce((sum, asset) => sum + asset.net_value, 0);

  const kpis: FixedAssetKpis =
    assets.length === 0
      ? { ...EMPTY_KPIS }
      : {
          gross,
          net,
          accumulated,
          depreciationRate: gross > 0 ? accumulated / gross : null,
          acquisitions: flowOf('acquisitions'),
          disposals: flowOf('disposals'),
          charge: flowOf('depreciation_charge'),
          assetCount: assets.length,
          fullyDepreciated: assets.filter((asset) => asset.is_fully_depreciated).length,
          remainingLife:
            lifeWeight > 0
              ? assets.reduce(
                  (sum, asset) =>
                    sum + (asset.remaining_months / 12) * asset.net_value,
                  0,
                ) / lifeWeight
              : null,
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    kpis,
    categories,
    classes,
    evolution,
    schedule: asOf ? buildSchedule(assets, asOf) : [],
    assets,
  };
}
