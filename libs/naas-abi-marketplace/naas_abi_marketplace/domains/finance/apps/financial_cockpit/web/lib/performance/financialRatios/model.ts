import type { Dataset } from '@/lib/types';

/**
 * Financial ratio engine. The dataset carries one record per ratio per monthly
 * period, already expressed as a value plus the industry `benchmark` and the
 * internal `target` it should be read against. A scenario selection (year or
 * month) narrows the records the section receives.
 *
 * "As-of" = the latest period in that window; the KPIs, the benchmark bars and
 * the radar read that snapshot, while the trend chart walks every period.
 */

export type RatioUnit = 'percent' | 'ratio';

export type FinancialRatioRecord = {
  period: string; // period-end ISO date, e.g. "2026-12-31"
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  category: string;
  category_label: string;
  ratio_key: string;
  ratio_label: string;
  /** Percent ratios are stored as a rate (0.62 = 62 %). */
  value: number;
  unit: RatioUnit;
  benchmark: number;
  target: number;
  higher_is_better: boolean;
  hint?: string;
};

/** Canonical top-to-bottom order of the ratio groups. */
const CATEGORY_ORDER = ['profitability', 'returns', 'leverage', 'liquidity'];

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/**
 * Radar scores are clamped to this multiple of the benchmark so one runaway
 * ratio cannot flatten every other axis.
 */
const RADAR_MAX_SCORE = 2;

export function isFinancialRatioDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<FinancialRatioRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function financialRatioRecords(
  dataset: Dataset | undefined,
): FinancialRatioRecord[] {
  if (!isFinancialRatioDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.value === 'number' &&
      !Number.isNaN(record.value) &&
      typeof record.period === 'string' &&
      typeof record.ratio_key === 'string' &&
      (record.unit === 'percent' || record.unit === 'ratio'),
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

/** Percent ratios are rates; everything else reads as a multiple ("1,98 x"). */
export function formatRatioValue(value: number, unit: RatioUnit): string {
  if (unit === 'percent') {
    return new Intl.NumberFormat('fr-FR', {
      style: 'percent',
      maximumFractionDigits: 1,
    }).format(value);
  }
  return `${new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)} x`;
}

export type RatioPeriod = { id: string; label: string };

export type RatioTrendPoint = { period: string; label: string; value: number };

export type RatioStatus = 'above' | 'on' | 'below';

export type RatioSummary = {
  key: string;
  label: string;
  category: string;
  categoryLabel: string;
  unit: RatioUnit;
  value: number;
  benchmark: number;
  target: number;
  higherIsBetter: boolean;
  hint?: string;
  /** Signed gap to the benchmark, oriented so positive is always good. */
  vsBenchmark: number;
  /** Signed gap to the internal target, oriented so positive is always good. */
  vsTarget: number;
  status: RatioStatus;
  /** value / benchmark, flipped for lower-is-better ratios; 1 = at benchmark. */
  score: number;
  trend: RatioTrendPoint[];
  /** Change over the window (latest minus earliest), oriented so positive is good. */
  change: number;
};

export type RatioGroup = {
  key: string;
  label: string;
  ratios: RatioSummary[];
};

export type FinancialRatiosView = {
  periods: RatioPeriod[];
  asOf: string | null;
  asOfLabel: string;
  ratios: RatioSummary[];
  groups: RatioGroup[];
  /** How many ratios sit at or above their benchmark. */
  aboveBenchmark: number;
  /** Mean radar score across every ratio; 1 = exactly at benchmark. */
  overallScore: number;
};

/** Within a hair of the benchmark reads as "on", not above or below. */
const ON_BENCHMARK_TOLERANCE = 0.005;

function statusFor(vsBenchmark: number): RatioStatus {
  if (Math.abs(vsBenchmark) <= ON_BENCHMARK_TOLERANCE) {
    return 'on';
  }
  return vsBenchmark > 0 ? 'above' : 'below';
}

function scoreFor(record: FinancialRatioRecord): number {
  const { value, benchmark, higher_is_better: higherIsBetter } = record;
  if (benchmark === 0) {
    return 1;
  }
  const raw = higherIsBetter ? value / benchmark : benchmark / value;
  if (!Number.isFinite(raw) || raw < 0) {
    return 0;
  }
  return Math.min(RADAR_MAX_SCORE, raw);
}

export function buildFinancialRatios(
  records: FinancialRatioRecord[],
): FinancialRatiosView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods: RatioPeriod[] = periodIds.map((id) => ({
    id,
    label: formatPeriodLabel(id),
  }));
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  // Preserve first-seen ratio order, then sort by the canonical category order.
  const ratioKeys: string[] = [];
  for (const record of records) {
    if (!ratioKeys.includes(record.ratio_key)) {
      ratioKeys.push(record.ratio_key);
    }
  }

  const ratios: RatioSummary[] = [];
  for (const key of ratioKeys) {
    const forRatio = records.filter((r) => r.ratio_key === key);
    const snapshot = forRatio.find((r) => r.period === asOf) ?? forRatio[0];
    if (!snapshot) {
      continue;
    }

    const trend: RatioTrendPoint[] = periodIds
      .map((period) => {
        const point = forRatio.find((r) => r.period === period);
        return point
          ? { period, label: formatPeriodLabel(period), value: point.value }
          : null;
      })
      .filter((point): point is RatioTrendPoint => point !== null);

    const orient = snapshot.higher_is_better ? 1 : -1;
    const vsBenchmark = (snapshot.value - snapshot.benchmark) * orient;
    const first = trend[0]?.value ?? snapshot.value;
    const lastPoint = trend[trend.length - 1]?.value ?? snapshot.value;

    ratios.push({
      key,
      label: snapshot.ratio_label,
      category: snapshot.category,
      categoryLabel: snapshot.category_label,
      unit: snapshot.unit,
      value: snapshot.value,
      benchmark: snapshot.benchmark,
      target: snapshot.target,
      higherIsBetter: snapshot.higher_is_better,
      hint: snapshot.hint,
      vsBenchmark,
      vsTarget: (snapshot.value - snapshot.target) * orient,
      status: statusFor(vsBenchmark),
      score: scoreFor(snapshot),
      trend,
      change: (lastPoint - first) * orient,
    });
  }

  ratios.sort((a, b) => {
    const rank = (category: string) => {
      const index = CATEGORY_ORDER.indexOf(category);
      return index === -1 ? CATEGORY_ORDER.length : index;
    };
    return rank(a.category) - rank(b.category);
  });

  const groupKeys: string[] = [];
  for (const ratio of ratios) {
    if (!groupKeys.includes(ratio.category)) {
      groupKeys.push(ratio.category);
    }
  }
  const groups: RatioGroup[] = groupKeys.map((key) => {
    const inGroup = ratios.filter((ratio) => ratio.category === key);
    return { key, label: inGroup[0]?.categoryLabel ?? key, ratios: inGroup };
  });

  const aboveBenchmark = ratios.filter((ratio) => ratio.status !== 'below').length;
  const overallScore =
    ratios.length > 0
      ? ratios.reduce((total, ratio) => total + ratio.score, 0) / ratios.length
      : 0;

  return {
    periods,
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    ratios,
    groups,
    aboveBenchmark,
    overallScore,
  };
}

/** Look up one ratio by key — used by the section to place named KPI cards. */
export function findRatio(
  view: FinancialRatiosView,
  key: string,
): RatioSummary | undefined {
  return view.ratios.find((ratio) => ratio.key === key);
}
