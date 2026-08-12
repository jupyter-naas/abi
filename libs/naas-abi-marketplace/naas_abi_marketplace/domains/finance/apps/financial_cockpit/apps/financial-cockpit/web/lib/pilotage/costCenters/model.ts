import type { Dataset } from '@/lib/types';

/**
 * Cost center engine. One record per center per month, carrying the budget, the
 * actual spend, the headcount and the revenue / margin the center contributed.
 * A scenario selection narrows the months the section receives, so everything
 * below aggregates over exactly the selected window.
 *
 * Spend and contribution are flows and accumulate. Headcount is a stock: it is
 * read from the latest month in the window, never summed.
 */

export type CostCenterRecord = {
  period: string; // period-end ISO date, e.g. "2026-12-31"
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  cost_center: string;
  cost_center_label: string;
  division: string;
  division_label: string;
  budget: number;
  actual: number;
  headcount: number;
  revenue_contribution: number;
  margin_contribution: number;
};

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isCostCenterDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<CostCenterRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function costCenterRecords(dataset: Dataset | undefined): CostCenterRecord[] {
  if (!isCostCenterDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.actual === 'number' &&
      !Number.isNaN(record.actual) &&
      typeof record.budget === 'number' &&
      typeof record.period === 'string' &&
      typeof record.cost_center === 'string',
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

export type CostCenterSummary = {
  key: string;
  label: string;
  division: string;
  divisionLabel: string;
  budget: number;
  actual: number;
  /** Actual minus budget: positive is an overspend. */
  variance: number;
  variancePct: number | null;
  /** Headcount at the latest month in the window. */
  headcount: number;
  costPerEmployee: number | null;
  revenueContribution: number;
  marginContribution: number;
  /** Spend per month, for the heatmap and trend. */
  monthly: { period: string; label: string; budget: number; actual: number }[];
};

export type DivisionSummary = {
  key: string;
  label: string;
  actual: number;
  budget: number;
  variance: number;
  centers: CostCenterSummary[];
};

export type CostCenterKpis = {
  budget: number;
  actual: number;
  variance: number;
  variancePct: number | null;
  headcount: number;
  costPerEmployee: number | null;
  revenueContribution: number;
  marginContribution: number;
};

export type MonthlyPoint = {
  period: string;
  label: string;
  budget: number;
  actual: number;
};

export type HeatmapCell = { value: number; label: string };

export type VarianceHeatmap = {
  rowLabels: string[];
  colLabels: string[];
  /** `cells[centerIndex][monthIndex]` — variance as a rate, positive = over. */
  cells: number[][];
};

export type CostCentersView = {
  periods: { id: string; label: string }[];
  centers: CostCenterSummary[];
  divisions: DivisionSummary[];
  kpis: CostCenterKpis;
  monthly: MonthlyPoint[];
  heatmap: VarianceHeatmap | null;
  /** Centers ordered by spend, largest first. */
  ranking: CostCenterSummary[];
};

const EMPTY_KPIS: CostCenterKpis = {
  budget: 0,
  actual: 0,
  variance: 0,
  variancePct: null,
  headcount: 0,
  costPerEmployee: null,
  revenueContribution: 0,
  marginContribution: 0,
};

export function buildCostCenters(records: CostCenterRecord[]): CostCentersView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods = periodIds.map((id) => ({ id, label: formatPeriodLabel(id) }));
  const lastPeriod = periodIds[periodIds.length - 1] ?? null;

  // Preserve first-seen center order.
  const centerKeys: string[] = [];
  for (const record of records) {
    if (!centerKeys.includes(record.cost_center)) {
      centerKeys.push(record.cost_center);
    }
  }

  const centers: CostCenterSummary[] = centerKeys.map((key) => {
    const forCenter = records.filter((r) => r.cost_center === key);
    const sample = forCenter[0];

    const budget = forCenter.reduce((sum, r) => sum + r.budget, 0);
    const actual = forCenter.reduce((sum, r) => sum + r.actual, 0);
    const revenueContribution = forCenter.reduce(
      (sum, r) => sum + r.revenue_contribution,
      0,
    );
    const marginContribution = forCenter.reduce(
      (sum, r) => sum + r.margin_contribution,
      0,
    );
    // Headcount is a stock — read the latest month, never sum across months.
    const headcount =
      forCenter.find((r) => r.period === lastPeriod)?.headcount ??
      forCenter[forCenter.length - 1]?.headcount ??
      0;

    const monthly = periodIds
      .map((period) => {
        const record = forCenter.find((r) => r.period === period);
        return record
          ? {
              period,
              label: formatPeriodLabel(period),
              budget: record.budget,
              actual: record.actual,
            }
          : null;
      })
      .filter((point): point is MonthlyPoint => point !== null);

    return {
      key,
      label: sample?.cost_center_label ?? key,
      division: sample?.division ?? '',
      divisionLabel: sample?.division_label ?? '',
      budget,
      actual,
      variance: actual - budget,
      variancePct: budget !== 0 ? (actual - budget) / budget : null,
      headcount,
      costPerEmployee: headcount > 0 ? actual / headcount : null,
      revenueContribution,
      marginContribution,
      monthly,
    };
  });

  // --- divisions, preserving first-seen order.
  const divisionKeys: string[] = [];
  for (const center of centers) {
    if (!divisionKeys.includes(center.division)) {
      divisionKeys.push(center.division);
    }
  }
  const divisions: DivisionSummary[] = divisionKeys.map((key) => {
    const inDivision = centers.filter((center) => center.division === key);
    const budget = inDivision.reduce((sum, center) => sum + center.budget, 0);
    const actual = inDivision.reduce((sum, center) => sum + center.actual, 0);
    return {
      key,
      label: inDivision[0]?.divisionLabel ?? key,
      budget,
      actual,
      variance: actual - budget,
      centers: [...inDivision].sort((a, b) => b.actual - a.actual),
    };
  });
  divisions.sort((a, b) => b.actual - a.actual);

  const budget = centers.reduce((sum, center) => sum + center.budget, 0);
  const actual = centers.reduce((sum, center) => sum + center.actual, 0);
  const headcount = centers.reduce((sum, center) => sum + center.headcount, 0);

  const kpis: CostCenterKpis =
    records.length === 0
      ? { ...EMPTY_KPIS }
      : {
          budget,
          actual,
          variance: actual - budget,
          variancePct: budget !== 0 ? (actual - budget) / budget : null,
          headcount,
          costPerEmployee: headcount > 0 ? actual / headcount : null,
          revenueContribution: centers.reduce(
            (sum, center) => sum + center.revenueContribution,
            0,
          ),
          marginContribution: centers.reduce(
            (sum, center) => sum + center.marginContribution,
            0,
          ),
        };

  // --- company-wide monthly budget vs actual.
  const monthly: MonthlyPoint[] = periodIds.map((period) => {
    const forPeriod = records.filter((r) => r.period === period);
    return {
      period,
      label: formatPeriodLabel(period),
      budget: forPeriod.reduce((sum, r) => sum + r.budget, 0),
      actual: forPeriod.reduce((sum, r) => sum + r.actual, 0),
    };
  });

  // --- heatmap: variance rate per center per month.
  const heatmap: VarianceHeatmap | null =
    centers.length > 0 && periodIds.length > 0
      ? {
          rowLabels: centers.map((center) => center.label),
          colLabels: periodIds.map((period) => formatPeriodLabel(period)),
          cells: centers.map((center) =>
            periodIds.map((period) => {
              const point = center.monthly.find((entry) => entry.period === period);
              if (!point || point.budget === 0) {
                return 0;
              }
              return (point.actual - point.budget) / point.budget;
            }),
          ),
        }
      : null;

  return {
    periods,
    centers,
    divisions,
    kpis,
    monthly,
    heatmap,
    ranking: [...centers].sort((a, b) => b.actual - a.actual),
  };
}
