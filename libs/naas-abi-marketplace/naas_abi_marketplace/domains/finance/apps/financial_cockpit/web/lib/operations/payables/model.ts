import type { Dataset } from '@/lib/types';

/**
 * Accounts Payable engine. Two record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `bill` — one open supplier invoice, snapshotted at each month end. A
 *   **stock**: read the latest period in the window, never sum across periods.
 * - `memo` — per-period aggregates (purchased, paid, DPO).
 *
 * The bill book always sums back to the balance sheet's Trade payables line,
 * so Accounts Payable here equals the balance-sheet figure.
 *
 * "Due this week" and the payment calendar are measured from the **closing
 * month end of the window**, which is the only "today" a historical snapshot
 * has. Bills already past due land in week 0 — they are payable now.
 */

export type PayableRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'bill' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  supplier: string;
  supplier_name: string;
  category: string;
  country: string;
  bill_ref: string;
  received_date: string;
  due_date: string;
  payment_terms_days: number;
  amount: number;
  outstanding: number;
  /** Positive once past due; negative while still inside terms. */
  days_overdue: number;
  /** Days from the month end until due; negative once overdue. */
  days_to_due: number;
  /** 0 = payable now (overdue or due within the week), then one per week. */
  due_week: number;
  aging_bucket: string;
  aging_label: string;
  status: string;
  discount_pct: number;
  discount_available: boolean;
};

/** Aging buckets in display order. Mirrors the receivables book. */
export const AGING_BUCKETS = [
  { key: 'current', label: 'Not yet due' },
  { key: 'd1_30', label: '1–30 days' },
  { key: 'd31_60', label: '31–60 days' },
  { key: 'd61_90', label: '61–90 days' },
  { key: 'd90_plus', label: '90+ days' },
] as const;

/** Horizon of the payment calendar, in weeks past the month end. */
export const CALENDAR_WEEKS = 8;
/** Window the payment forecast covers, in days past the month end. */
export const FORECAST_DAYS = 30;

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isPayablesDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<PayableRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function payableRecords(dataset: Dataset | undefined): PayableRecord[] {
  if (!isPayablesDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'bill' || record.kind === 'memo'),
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

export type AgingBucket = {
  key: string;
  label: string;
  amount: number;
  count: number;
  share: number;
};

export type SupplierSummary = {
  key: string;
  label: string;
  category: string;
  country: string;
  outstanding: number;
  current: number;
  overdue: number;
  buckets: number[];
  billCount: number;
  averageDaysLate: number | null;
  /** Soonest due date across the supplier's open bills. */
  nextDue: string | null;
  paymentTerms: number;
  /** Early-payment discount still capturable on the open bills. */
  discountAtStake: number;
  share: number;
};

export type PaymentWeek = {
  week: number;
  label: string;
  amount: number;
  count: number;
  /** Bills already past due, which are payable immediately. */
  overdue: boolean;
};

export type PayablesTrendPoint = {
  period: string;
  label: string;
  purchased: number;
  paid: number;
  payables: number;
  dpo: number;
};

export type PayablesKpis = {
  /** Open balance at the close of the window. */
  payables: number;
  /** Days payable outstanding at the close, on a trailing purchases window. */
  dpo: number | null;
  /** Falls due within seven days of the close, plus anything already overdue. */
  dueThisWeek: number;
  overdue: number;
  overdueCount: number;
  /** Cash needed over the next `FORECAST_DAYS`, overdue included. */
  paymentForecast: number;
  supplierCount: number;
  billCount: number;
  /** Early-payment discount still available on the open book. */
  discountAtStake: number;
};

export type PayablesView = {
  asOf: string | null;
  asOfLabel: string;
  kpis: PayablesKpis;
  aging: AgingBucket[];
  suppliers: SupplierSummary[];
  calendar: PaymentWeek[];
  trend: PayablesTrendPoint[];
  openBills: PayableRecord[];
};

const EMPTY_KPIS: PayablesKpis = {
  payables: 0,
  dpo: null,
  dueThisWeek: 0,
  overdue: 0,
  overdueCount: 0,
  paymentForecast: 0,
  supplierCount: 0,
  billCount: 0,
  discountAtStake: 0,
};

function weightedDaysLate(bills: PayableRecord[]): number | null {
  const late = bills.filter((bill) => bill.days_overdue > 0);
  const weight = late.reduce((sum, bill) => sum + bill.outstanding, 0);
  if (weight <= 0) {
    return null;
  }
  return (
    late.reduce((sum, bill) => sum + bill.outstanding * bill.days_overdue, 0) / weight
  );
}

export function buildPayables(records: PayableRecord[]): PayablesView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const billRows = records.filter((record) => record.kind === 'bill');
  const memoRows = records.filter((record) => record.kind === 'memo');

  const openBills = billRows
    .filter((record) => record.period === asOf && record.outstanding > 0)
    .sort((a, b) => a.days_to_due - b.days_to_due);

  const payables = openBills.reduce((sum, bill) => sum + bill.outstanding, 0);

  // --- aging.
  const aging: AgingBucket[] = AGING_BUCKETS.map(({ key, label }) => {
    const inBucket = openBills.filter((bill) => bill.aging_bucket === key);
    const amount = inBucket.reduce((sum, bill) => sum + bill.outstanding, 0);
    return {
      key,
      label,
      amount,
      count: inBucket.length,
      share: payables > 0 ? amount / payables : 0,
    };
  });

  // --- payment calendar: what leaves the account, week by week.
  const calendar: PaymentWeek[] = Array.from({ length: CALENDAR_WEEKS + 1 }, (_, week) => {
    const inWeek = openBills.filter((bill) => bill.due_week === week);
    return {
      week,
      label: week === 0 ? 'Payable now' : `Week +${week}`,
      amount: inWeek.reduce((sum, bill) => sum + bill.outstanding, 0),
      count: inWeek.length,
      overdue: week === 0,
    };
  });

  // --- per-supplier ledger.
  const supplierKeys: string[] = [];
  for (const bill of openBills) {
    if (!supplierKeys.includes(bill.supplier)) {
      supplierKeys.push(bill.supplier);
    }
  }

  const suppliers: SupplierSummary[] = supplierKeys
    .map((key) => {
      const forSupplier = openBills.filter((bill) => bill.supplier === key);
      const outstanding = forSupplier.reduce((sum, bill) => sum + bill.outstanding, 0);
      const overdueBills = forSupplier.filter((bill) => bill.days_overdue > 0);
      const first = forSupplier[0];
      const dueDates = forSupplier
        .map((bill) => bill.due_date)
        .filter(Boolean)
        .sort();
      return {
        key,
        label: first.supplier_name,
        category: first.category,
        country: first.country,
        outstanding,
        current: outstanding - overdueBills.reduce((s, b) => s + b.outstanding, 0),
        overdue: overdueBills.reduce((sum, bill) => sum + bill.outstanding, 0),
        buckets: AGING_BUCKETS.map(({ key: bucketKey }) =>
          forSupplier
            .filter((bill) => bill.aging_bucket === bucketKey)
            .reduce((sum, bill) => sum + bill.outstanding, 0),
        ),
        billCount: forSupplier.length,
        averageDaysLate: weightedDaysLate(forSupplier),
        nextDue: dueDates[0] ?? null,
        paymentTerms: first.payment_terms_days,
        discountAtStake: forSupplier
          .filter((bill) => bill.discount_available)
          .reduce((sum, bill) => sum + bill.outstanding * bill.discount_pct, 0),
        share: payables > 0 ? outstanding / payables : 0,
      };
    })
    .sort((a, b) => b.outstanding - a.outstanding);

  // --- monthly flows and the DPO series.
  const metricFor = (period: string, metric: string): number =>
    memoRows
      .filter((record) => record.period === period && record.metric === metric)
      .reduce((sum, record) => sum + record.amount, 0);

  const trend: PayablesTrendPoint[] = periodIds.map((period) => ({
    period,
    label: formatPeriodLabel(period),
    purchased: metricFor(period, 'purchased'),
    paid: metricFor(period, 'paid'),
    payables: metricFor(period, 'payables'),
    dpo: metricFor(period, 'dpo'),
  }));

  const overdueBills = openBills.filter((bill) => bill.days_overdue > 0);
  const overdue = overdueBills.reduce((sum, bill) => sum + bill.outstanding, 0);

  const kpis: PayablesKpis =
    billRows.length === 0
      ? { ...EMPTY_KPIS }
      : {
          payables,
          dpo: asOf ? metricFor(asOf, 'dpo') || null : null,
          dueThisWeek: openBills
            .filter((bill) => bill.days_to_due <= 7)
            .reduce((sum, bill) => sum + bill.outstanding, 0),
          overdue,
          overdueCount: overdueBills.length,
          paymentForecast: openBills
            .filter((bill) => bill.days_to_due <= FORECAST_DAYS)
            .reduce((sum, bill) => sum + bill.outstanding, 0),
          supplierCount: suppliers.length,
          billCount: openBills.length,
          discountAtStake: openBills
            .filter((bill) => bill.discount_available)
            .reduce((sum, bill) => sum + bill.outstanding * bill.discount_pct, 0),
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    kpis,
    aging,
    suppliers,
    calendar,
    trend,
    openBills,
  };
}
