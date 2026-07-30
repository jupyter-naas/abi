import type { Dataset } from '@/lib/types';

/**
 * Cash flow engine. The dataset carries monthly movements split across three
 * activities plus `memo` lines (opening/closing cash and the period's P&L). A
 * scenario selection (year or month) narrows the records the section receives,
 * so everything below aggregates over exactly the selected window: the KPIs and
 * the waterfall span opening cash of the first month to closing cash of the
 * last, while the trends walk every month present.
 */

export type CashFlowActivity = 'operating' | 'investing' | 'financing' | 'memo';

export type CashFlowRecord = {
  period: string; // period-end ISO date, e.g. "2026-12-31"
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  activity: CashFlowActivity;
  activity_label: string;
  category: string;
  amount: number;
};

/** The three real activities, in statement order. `memo` is never displayed. */
const ACTIVITY_ORDER: { id: Exclude<CashFlowActivity, 'memo'>; label: string }[] = [
  { id: 'operating', label: 'Operating activities' },
  { id: 'investing', label: 'Investing activities' },
  { id: 'financing', label: 'Financing activities' },
];

const ACTIVITY_IDS = new Set<string>(ACTIVITY_ORDER.map((activity) => activity.id));

/** Memo categories the model reads by name. */
const OPENING_CASH = 'Opening cash';
const CLOSING_CASH = 'Closing cash';
const EBITDA = 'EBITDA';
/** Investing line treated as capex when deriving free cash flow. */
const CAPEX = 'Capital expenditure';

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isCashFlowDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<CashFlowRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function cashFlowRecords(dataset: Dataset | undefined): CashFlowRecord[] {
  if (!isCashFlowDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      typeof record.period === 'string' &&
      typeof record.category === 'string' &&
      (ACTIVITY_IDS.has(record.activity) || record.activity === 'memo'),
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

export type CashFlowPeriod = { id: string; label: string };

export type CfAmounts = Record<string, number>;

export type CfCategoryRow = {
  key: string;
  label: string;
  amounts: CfAmounts;
  total: number;
};

export type CfActivityRow = {
  id: Exclude<CashFlowActivity, 'memo'>;
  label: string;
  amounts: CfAmounts;
  total: number;
  categories: CfCategoryRow[];
};

export type CashFlowKpis = {
  operating: number;
  investing: number;
  financing: number;
  /** Operating cash flow plus capital expenditure (capex is negative). */
  freeCashFlow: number;
  openingCash: number;
  endingCash: number;
  netChange: number;
  /** Operating cash flow / EBITDA over the window; null when EBITDA <= 0. */
  cashConversion: number | null;
};

/** One step of the waterfall — `isTotal` steps are absolute, not deltas. */
export type WaterfallStep = {
  key: string;
  label: string;
  value: number;
  isTotal: boolean;
  /** Running balance after this step, used to place the floating bar. */
  start: number;
  end: number;
};

export type CashTrendPoint = {
  period: string;
  label: string;
  openingCash: number;
  endingCash: number;
  netChange: number;
};

export type ActivityTrendPoint = {
  period: string;
  label: string;
  operating: number;
  investing: number;
  financing: number;
};

export type CashSourceSlice = { key: string; label: string; value: number };

export type CashFlowStatement = {
  periods: CashFlowPeriod[];
  activities: CfActivityRow[];
  kpis: CashFlowKpis;
  waterfall: WaterfallStep[];
  cashTrend: CashTrendPoint[];
  activityTrend: ActivityTrendPoint[];
  sources: CashSourceSlice[];
  /** Opening + the three activities equals closing, within rounding. */
  isReconciled: boolean;
};

const EMPTY_KPIS: CashFlowKpis = {
  operating: 0,
  investing: 0,
  financing: 0,
  freeCashFlow: 0,
  openingCash: 0,
  endingCash: 0,
  netChange: 0,
  cashConversion: null,
};

function add(amounts: CfAmounts, period: string, value: number): void {
  amounts[period] = (amounts[period] ?? 0) + value;
}

function sumAmounts(amounts: CfAmounts): number {
  return Object.values(amounts).reduce((total, value) => total + value, 0);
}

function memoTotal(records: CashFlowRecord[], category: string): number {
  return records.reduce(
    (total, record) =>
      record.activity === 'memo' && record.category === category
        ? total + record.amount
        : total,
    0,
  );
}

/** Memo balances are point-in-time, so read the one snapshot rather than summing. */
function memoAt(
  records: CashFlowRecord[],
  category: string,
  period: string | null,
): number {
  if (!period) {
    return 0;
  }
  return records.reduce(
    (total, record) =>
      record.activity === 'memo' &&
      record.category === category &&
      record.period === period
        ? total + record.amount
        : total,
    0,
  );
}

export function buildCashFlow(records: CashFlowRecord[]): CashFlowStatement {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods: CashFlowPeriod[] = periodIds.map((id) => ({
    id,
    label: formatPeriodLabel(id),
  }));
  const first = periodIds[0] ?? null;
  const last = periodIds[periodIds.length - 1] ?? null;

  const movements = records.filter((r) => r.activity !== 'memo');

  // --- hierarchical statement (activity → category), amounts per period.
  const activities: CfActivityRow[] = ACTIVITY_ORDER.map((activity) => {
    const activityRecords = movements.filter((r) => r.activity === activity.id);

    // Preserve first-seen category order within the activity.
    const categoryKeys: string[] = [];
    for (const record of activityRecords) {
      if (!categoryKeys.includes(record.category)) {
        categoryKeys.push(record.category);
      }
    }

    const categories: CfCategoryRow[] = categoryKeys.map((category) => {
      const amounts: CfAmounts = {};
      for (const record of activityRecords) {
        if (record.category === category) {
          add(amounts, record.period, record.amount);
        }
      }
      return { key: category, label: category, amounts, total: sumAmounts(amounts) };
    });

    const amounts: CfAmounts = {};
    for (const record of activityRecords) {
      add(amounts, record.period, record.amount);
    }
    const label = activityRecords[0]?.activity_label ?? activity.label;
    return {
      id: activity.id,
      label,
      amounts,
      total: sumAmounts(amounts),
      categories,
    };
  });

  const byId = (id: Exclude<CashFlowActivity, 'memo'>) =>
    activities.find((activity) => activity.id === id);
  const operating = byId('operating')?.total ?? 0;
  const investing = byId('investing')?.total ?? 0;
  const financing = byId('financing')?.total ?? 0;

  const capex =
    byId('investing')?.categories.find((category) => category.key === CAPEX)?.total ?? 0;
  const ebitda = memoTotal(records, EBITDA);

  // Cash balances are stocks: take the opening of the first month and the
  // closing of the last, not the sum across the window.
  const openingCash = memoAt(records, OPENING_CASH, first);
  const endingCash = memoAt(records, CLOSING_CASH, last);

  const kpis: CashFlowKpis =
    records.length === 0
      ? { ...EMPTY_KPIS }
      : {
          operating,
          investing,
          financing,
          freeCashFlow: operating + capex,
          openingCash,
          endingCash,
          netChange: operating + investing + financing,
          cashConversion: ebitda > 0 ? operating / ebitda : null,
        };

  // --- waterfall: opening → the three activities → closing.
  const waterfall: WaterfallStep[] = [];
  if (records.length > 0) {
    let running = openingCash;
    waterfall.push({
      key: 'opening',
      label: 'Opening cash',
      value: openingCash,
      isTotal: true,
      start: 0,
      end: openingCash,
    });
    for (const activity of activities) {
      const start = running;
      running += activity.total;
      waterfall.push({
        key: activity.id,
        label: activity.label,
        value: activity.total,
        isTotal: false,
        start,
        end: running,
      });
    }
    waterfall.push({
      key: 'closing',
      label: 'Closing cash',
      value: endingCash,
      isTotal: true,
      start: 0,
      end: endingCash,
    });
  }

  // --- trends across every month in the window.
  const cashTrend: CashTrendPoint[] = [];
  const activityTrend: ActivityTrendPoint[] = [];
  for (const period of periodIds) {
    const label = formatPeriodLabel(period);
    const opening = memoAt(records, OPENING_CASH, period);
    const closing = memoAt(records, CLOSING_CASH, period);
    cashTrend.push({
      period,
      label,
      openingCash: opening,
      endingCash: closing,
      netChange: closing - opening,
    });
    activityTrend.push({
      period,
      label,
      operating: byId('operating')?.amounts[period] ?? 0,
      investing: byId('investing')?.amounts[period] ?? 0,
      financing: byId('financing')?.amounts[period] ?? 0,
    });
  }

  // --- where cash came from: every inflow line over the window, largest first.
  const sources: CashSourceSlice[] = activities
    .flatMap((activity) => activity.categories)
    .filter((category) => category.total > 0)
    .map((category) => ({
      key: category.key,
      label: category.label,
      value: category.total,
    }))
    .sort((a, b) => b.value - a.value);

  const isReconciled =
    Math.abs(openingCash + kpis.netChange - endingCash) <
    Math.max(1, Math.abs(endingCash) * 1e-6);

  return {
    periods,
    activities,
    kpis,
    waterfall,
    cashTrend,
    activityTrend,
    sources,
    isReconciled,
  };
}
