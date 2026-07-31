import type { Dataset } from '@/lib/types';

/**
 * Cash forecast engine. One record per week per case (base / upside /
 * downside). The base case is what the KPIs and the projection table read; the
 * other cases only feed the scenario comparison.
 *
 * The point of a weekly view is the trough: a company can close every month
 * comfortably and still run out mid-month, so Lowest Cash Point scans weeks,
 * not months.
 */

export type CashForecastRecord = {
  period: string; // month period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  week: string; // e.g. "2026-08-W3"
  week_end: string; // ISO date
  week_index: number; // 1-4 within the month
  case_key: string;
  case_label: string;
  is_base: boolean;
  description?: string;
  is_actual: boolean;
  inflow: number;
  outflow: number;
  net: number;
  closing_cash: number;
};

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** Weeks per month the generator emits — used to turn a burn rate into months. */
const WEEKS_PER_MONTH = 4;

export function isCashForecastDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<CashForecastRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function cashForecastRecords(
  dataset: Dataset | undefined,
): CashForecastRecord[] {
  if (!isCashForecastDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.closing_cash === 'number' &&
      !Number.isNaN(record.closing_cash) &&
      typeof record.week_end === 'string' &&
      typeof record.case_key === 'string',
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

/** "2026-08-19" → "19 Aug". */
export function formatWeekLabel(weekEnd: string): string {
  const [, month, day] = weekEnd.split('-');
  const index = Number(month) - 1;
  if (index < 0 || index > 11 || !day) {
    return weekEnd;
  }
  return `${Number(day)} ${MONTH_ABBR[index]}`;
}

export type WeekPoint = {
  week: string;
  weekEnd: string;
  label: string;
  period: string;
  isActual: boolean;
  inflow: number;
  outflow: number;
  net: number;
  openingCash: number;
  closingCash: number;
};

export type MonthPoint = {
  period: string;
  label: string;
  inflow: number;
  outflow: number;
  net: number;
  closingCash: number;
};

export type ForecastCase = {
  key: string;
  label: string;
  isBase: boolean;
  description?: string;
  points: WeekPoint[];
  closingCash: number;
  lowestPoint: number;
};

export type CashForecastKpis = {
  /** Lowest weekly closing balance across the window, and when it happens. */
  lowestCash: number;
  lowestCashLabel: string;
  /** Months of cash left at the current burn; null when cash-generative. */
  runway: number | null;
  /** Largest shortfall below zero; 0 when the balance never goes negative. */
  peakDeficit: number;
  expectedClosingCash: number;
  inflows: number;
  outflows: number;
  netChange: number;
};

export type CashForecastView = {
  cases: ForecastCase[];
  base: ForecastCase | null;
  weeks: WeekPoint[];
  months: MonthPoint[];
  kpis: CashForecastKpis;
  periods: { id: string; label: string }[];
};

const EMPTY_KPIS: CashForecastKpis = {
  lowestCash: 0,
  lowestCashLabel: '—',
  runway: null,
  peakDeficit: 0,
  expectedClosingCash: 0,
  inflows: 0,
  outflows: 0,
  netChange: 0,
};

function toWeekPoints(records: CashForecastRecord[]): WeekPoint[] {
  const sorted = [...records].sort((a, b) => a.week_end.localeCompare(b.week_end));
  return sorted.map((record, index) => ({
    week: record.week,
    weekEnd: record.week_end,
    label: formatWeekLabel(record.week_end),
    period: record.period,
    isActual: record.is_actual,
    inflow: record.inflow,
    outflow: record.outflow,
    net: record.net,
    // Opening is the previous week's close; the first week backs it out of its
    // own net so the projection table always balances.
    openingCash:
      index > 0 ? sorted[index - 1].closing_cash : record.closing_cash - record.net,
    closingCash: record.closing_cash,
  }));
}

export function buildCashForecast(records: CashForecastRecord[]): CashForecastView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods = periodIds.map((id) => ({ id, label: formatPeriodLabel(id) }));

  // Preserve first-seen case order, then float the base case to the middle of
  // the comparison by sorting on closing cash later.
  const caseKeys: string[] = [];
  for (const record of records) {
    if (!caseKeys.includes(record.case_key)) {
      caseKeys.push(record.case_key);
    }
  }

  const cases: ForecastCase[] = caseKeys.map((key) => {
    const forCase = records.filter((r) => r.case_key === key);
    const points = toWeekPoints(forCase);
    const sample = forCase[0];
    return {
      key,
      label: sample?.case_label ?? key,
      isBase: Boolean(sample?.is_base),
      description: sample?.description,
      points,
      closingCash: points[points.length - 1]?.closingCash ?? 0,
      lowestPoint: points.reduce(
        (min, point) => Math.min(min, point.closingCash),
        points[0]?.closingCash ?? 0,
      ),
    };
  });

  const base = cases.find((entry) => entry.isBase) ?? cases[0] ?? null;
  const weeks = base?.points ?? [];

  // --- monthly roll-up of the base case, for the headline curve.
  const months: MonthPoint[] = periodIds.map((period) => {
    const inMonth = weeks.filter((point) => point.period === period);
    return {
      period,
      label: formatPeriodLabel(period),
      inflow: inMonth.reduce((sum, point) => sum + point.inflow, 0),
      outflow: inMonth.reduce((sum, point) => sum + point.outflow, 0),
      net: inMonth.reduce((sum, point) => sum + point.net, 0),
      closingCash: inMonth[inMonth.length - 1]?.closingCash ?? 0,
    };
  });

  let kpis: CashForecastKpis = { ...EMPTY_KPIS };
  if (weeks.length > 0) {
    const lowest = weeks.reduce(
      (min, point) => (point.closingCash < min.closingCash ? point : min),
      weeks[0],
    );
    const inflows = weeks.reduce((sum, point) => sum + point.inflow, 0);
    const outflows = weeks.reduce((sum, point) => sum + point.outflow, 0);
    const netChange = inflows - outflows;
    const closing = weeks[weeks.length - 1].closingCash;

    // Runway only means something while cash is being consumed: with a positive
    // net the company is not running down its balance at all.
    const monthlyBurn = -(netChange / (weeks.length / WEEKS_PER_MONTH));
    const runway = monthlyBurn > 0 ? closing / monthlyBurn : null;

    kpis = {
      lowestCash: lowest.closingCash,
      lowestCashLabel: lowest.label,
      runway,
      peakDeficit: Math.min(0, lowest.closingCash),
      expectedClosingCash: closing,
      inflows,
      outflows,
      netChange,
    };
  }

  return { cases, base, weeks, months, kpis, periods };
}
