import type { Dataset } from '@/lib/types';

/**
 * Forecast engine. Each record is one metric in one month, carrying the
 * `actual` (only for months already closed), the `forecast` standing for that
 * month, the `budget` set at the start of the year, and a `low`/`high`
 * confidence band that widens with the horizon.
 *
 * "Expected" is the value the page reasons about: the actual where the month is
 * closed, otherwise the forecast. Full-year figures sum the expected value of
 * every month in the selected window — except stocks (cash), which carry the
 * closing level of the last month rather than a sum.
 */

export type ForecastUnit = 'currency' | 'percent';

export type ForecastRecord = {
  period: string; // period-end ISO date, e.g. "2026-12-31"
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  metric: string;
  metric_label: string;
  unit: ForecastUnit;
  is_stock: boolean;
  is_actual: boolean;
  actual: number | null;
  forecast: number;
  budget: number;
  low: number;
  high: number;
};

/** Canonical top-to-bottom order of the metrics. */
const METRIC_ORDER = ['revenue', 'ebitda', 'cash', 'margin'];

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isForecastDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<ForecastRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function forecastRecords(dataset: Dataset | undefined): ForecastRecord[] {
  if (!isForecastDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.forecast === 'number' &&
      !Number.isNaN(record.forecast) &&
      typeof record.period === 'string' &&
      typeof record.metric === 'string' &&
      (record.unit === 'currency' || record.unit === 'percent'),
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

/** The value the page reasons about: actual once closed, else forecast. */
export function expectedValue(record: ForecastRecord): number {
  return record.actual !== null ? record.actual : record.forecast;
}

export type ForecastPoint = {
  period: string;
  label: string;
  isActual: boolean;
  actual: number | null;
  forecast: number;
  budget: number;
  low: number;
  high: number;
  expected: number;
};

export type ForecastMetric = {
  key: string;
  label: string;
  unit: ForecastUnit;
  isStock: boolean;
  points: ForecastPoint[];
  /** Full-year expected value: sum for flows, closing level for stocks. */
  total: number;
  budgetTotal: number;
  /** Signed gap to budget, positive = ahead of budget. */
  vsBudget: number;
  closingLow: number;
  closingHigh: number;
};

export type ForecastKpis = {
  revenue: number;
  ebitda: number;
  cash: number;
  margin: number;
  /** 1 − mean absolute percentage error on closed months; null without any. */
  accuracy: number | null;
  /** Expected revenue vs budgeted revenue, as a rate. */
  variance: number | null;
  actualMonths: number;
  forecastMonths: number;
};

export type WaterfallStep = {
  key: string;
  label: string;
  value: number;
  isTotal: boolean;
  start: number;
  end: number;
};

export type RollingPoint = { period: string; label: string; value: number };

export type ForecastView = {
  periods: { id: string; label: string }[];
  metrics: ForecastMetric[];
  kpis: ForecastKpis;
  /** Revenue, month by month — actual where closed, forecast beyond. */
  actualVsForecast: ForecastPoint[];
  /** Trailing twelve-month expected revenue at each month. */
  rollingForecast: RollingPoint[];
  /** EBITDA with its confidence band. */
  confidence: ForecastPoint[];
  /** Budget EBITDA bridged to forecast EBITDA. */
  waterfall: WaterfallStep[];
};

const EMPTY_KPIS: ForecastKpis = {
  revenue: 0,
  ebitda: 0,
  cash: 0,
  margin: 0,
  accuracy: null,
  variance: null,
  actualMonths: 0,
  forecastMonths: 0,
};

/** Trailing window for the rolling forecast. */
const ROLLING_MONTHS = 12;

function findMetric(metrics: ForecastMetric[], key: string): ForecastMetric | undefined {
  return metrics.find((metric) => metric.key === key);
}

export function buildForecast(records: ForecastRecord[]): ForecastView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods = periodIds.map((id) => ({ id, label: formatPeriodLabel(id) }));

  // Preserve first-seen metric order, then apply the canonical order.
  const metricKeys: string[] = [];
  for (const record of records) {
    if (!metricKeys.includes(record.metric)) {
      metricKeys.push(record.metric);
    }
  }
  metricKeys.sort((a, b) => {
    const rank = (key: string) => {
      const index = METRIC_ORDER.indexOf(key);
      return index === -1 ? METRIC_ORDER.length : index;
    };
    return rank(a) - rank(b);
  });

  const metrics: ForecastMetric[] = metricKeys.map((key) => {
    const forMetric = records.filter((r) => r.metric === key);
    const points: ForecastPoint[] = periodIds
      .map((period) => {
        const record = forMetric.find((r) => r.period === period);
        if (!record) {
          return null;
        }
        return {
          period,
          label: formatPeriodLabel(period),
          isActual: record.is_actual && record.actual !== null,
          actual: record.actual,
          forecast: record.forecast,
          budget: record.budget,
          low: record.low,
          high: record.high,
          expected: expectedValue(record),
        };
      })
      .filter((point): point is ForecastPoint => point !== null);

    const sample = forMetric[0];
    const isStock = Boolean(sample?.is_stock);
    const unit: ForecastUnit = sample?.unit ?? 'currency';
    const last = points[points.length - 1];

    // A stock carries its closing level; a rate is averaged; a flow accumulates.
    let total: number;
    let budgetTotal: number;
    if (isStock) {
      total = last?.expected ?? 0;
      budgetTotal = last?.budget ?? 0;
    } else if (unit === 'percent') {
      total =
        points.length > 0
          ? points.reduce((sum, point) => sum + point.expected, 0) / points.length
          : 0;
      budgetTotal =
        points.length > 0
          ? points.reduce((sum, point) => sum + point.budget, 0) / points.length
          : 0;
    } else {
      total = points.reduce((sum, point) => sum + point.expected, 0);
      budgetTotal = points.reduce((sum, point) => sum + point.budget, 0);
    }

    return {
      key,
      label: sample?.metric_label ?? key,
      unit,
      isStock,
      points,
      total,
      budgetTotal,
      vsBudget: total - budgetTotal,
      closingLow: last?.low ?? 0,
      closingHigh: last?.high ?? 0,
    };
  });

  const revenue = findMetric(metrics, 'revenue');
  const ebitda = findMetric(metrics, 'ebitda');
  const cash = findMetric(metrics, 'cash');

  // Accuracy reads the closed months of revenue: how far the forecast standing
  // at the time landed from what actually happened.
  const closed = (revenue?.points ?? []).filter(
    (point) => point.isActual && point.actual !== null && point.actual !== 0,
  );
  const accuracy =
    closed.length > 0
      ? 1 -
        closed.reduce(
          (sum, point) =>
            sum + Math.abs((point.actual as number) - point.forecast) /
              Math.abs(point.actual as number),
          0,
        ) /
          closed.length
      : null;

  const revenueTotal = revenue?.total ?? 0;
  const ebitdaTotal = ebitda?.total ?? 0;
  const revenueBudget = revenue?.budgetTotal ?? 0;

  const kpis: ForecastKpis =
    records.length === 0
      ? { ...EMPTY_KPIS }
      : {
          revenue: revenueTotal,
          ebitda: ebitdaTotal,
          cash: cash?.total ?? 0,
          margin: revenueTotal > 0 ? ebitdaTotal / revenueTotal : 0,
          accuracy,
          variance:
            revenueBudget !== 0 ? (revenueTotal - revenueBudget) / revenueBudget : null,
          actualMonths: (revenue?.points ?? []).filter((p) => p.isActual).length,
          forecastMonths: (revenue?.points ?? []).filter((p) => !p.isActual).length,
        };

  // --- rolling forecast: trailing twelve months of expected revenue.
  const revenuePoints = revenue?.points ?? [];
  const rollingForecast: RollingPoint[] = revenuePoints.map((point, index) => {
    const start = Math.max(0, index - ROLLING_MONTHS + 1);
    const window = revenuePoints.slice(start, index + 1);
    const months = window.length;
    const sum = window.reduce((total, entry) => total + entry.expected, 0);
    return {
      period: point.period,
      label: point.label,
      // Annualize while fewer than twelve months are available.
      value: months > 0 ? (sum * ROLLING_MONTHS) / months : 0,
    };
  });

  // --- waterfall: budget EBITDA bridged to forecast EBITDA.
  //
  // Splitting the gap into a revenue effect (extra revenue earning the budgeted
  // margin) and a margin effect (the whole forecast revenue earning a different
  // margin) is exact — the two terms sum to the EBITDA gap with no plug.
  const waterfall: WaterfallStep[] = [];
  if (revenue && ebitda && revenueBudget > 0 && revenueTotal > 0) {
    const budgetEbitda = ebitda.budgetTotal;
    const budgetMargin = budgetEbitda / revenueBudget;
    const forecastMargin = ebitdaTotal / revenueTotal;
    const revenueEffect = (revenueTotal - revenueBudget) * budgetMargin;
    const marginEffect = revenueTotal * (forecastMargin - budgetMargin);

    let running = budgetEbitda;
    waterfall.push({
      key: 'budget',
      label: 'Budget EBITDA',
      value: budgetEbitda,
      isTotal: true,
      start: 0,
      end: budgetEbitda,
    });
    for (const [key, label, value] of [
      ['revenue-effect', 'Revenue variance', revenueEffect],
      ['margin-effect', 'Margin variance', marginEffect],
    ] as const) {
      const start = running;
      running += value;
      waterfall.push({ key, label, value, isTotal: false, start, end: running });
    }
    waterfall.push({
      key: 'forecast',
      label: 'Forecast EBITDA',
      value: ebitdaTotal,
      isTotal: true,
      start: 0,
      end: ebitdaTotal,
    });
  }

  return {
    periods,
    metrics,
    kpis,
    actualVsForecast: revenuePoints,
    rollingForecast,
    confidence: ebitda?.points ?? [],
    waterfall,
  };
}
