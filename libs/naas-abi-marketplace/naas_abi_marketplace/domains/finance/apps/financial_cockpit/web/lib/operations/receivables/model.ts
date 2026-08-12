import type { Dataset } from '@/lib/types';

/**
 * Accounts Receivable engine. Two record kinds share the dataset behind a
 * `kind` discriminator:
 *
 * - `invoice` — one open customer invoice, snapshotted at each month end. A
 *   **stock**: read the latest period in the window, never sum across periods
 *   or the same invoice is counted once per month it stayed open.
 * - `memo` — per-period aggregates the invoice rows cannot carry (invoiced,
 *   collected, DSO). A **flow**, except `dso` and `receivables` which are
 *   as-of readings.
 *
 * The invoice book always sums back to the balance sheet's Trade receivables
 * line, so Accounts Receivable here equals the balance-sheet figure.
 */

export type ReceivableRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'invoice' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  customer: string;
  customer_name: string;
  segment: string;
  country: string;
  invoice_ref: string;
  issue_date: string;
  due_date: string;
  payment_terms_days: number;
  amount: number;
  outstanding: number;
  /** Positive once past due; negative while still inside terms. */
  days_overdue: number;
  aging_bucket: string;
  aging_label: string;
  status: string;
  is_disputed: boolean;
};

/** Aging buckets in display order. Keys match the generator. */
export const AGING_BUCKETS = [
  { key: 'current', label: 'Not yet due' },
  { key: 'd1_30', label: '1–30 days' },
  { key: 'd31_60', label: '31–60 days' },
  { key: 'd61_90', label: '61–90 days' },
  { key: 'd90_plus', label: '90+ days' },
] as const;

/** Past this many days late, a balance is treated as at risk. */
export const AT_RISK_DAYS = 90;

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isReceivablesDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<ReceivableRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function receivableRecords(dataset: Dataset | undefined): ReceivableRecord[] {
  if (!isReceivablesDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'invoice' || record.kind === 'memo'),
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
  /** Share of the total open balance. */
  share: number;
};

export type DebtorSummary = {
  key: string;
  label: string;
  segment: string;
  country: string;
  outstanding: number;
  /** Open balance inside terms. */
  current: number;
  overdue: number;
  /** Open balance by aging bucket key, in `AGING_BUCKETS` order. */
  buckets: number[];
  invoiceCount: number;
  /** Balance-weighted days past due across the overdue invoices only. */
  averageDaysLate: number | null;
  /** Furthest past due of any open invoice; null when nothing is late. */
  oldestDaysOverdue: number | null;
  disputed: number;
  share: number;
};

export type ReceivablesTrendPoint = {
  period: string;
  label: string;
  invoiced: number;
  collected: number;
  receivables: number;
  dso: number;
};

export type ReceivablesKpis = {
  /** Open balance at the close of the window. */
  receivables: number;
  /** Days sales outstanding at the close, on a trailing revenue window. */
  dso: number | null;
  overdue: number;
  /** Overdue as a share of the open balance. */
  overdueShare: number | null;
  /** Collected over invoiced, across the window. */
  collectionRate: number | null;
  /** Collection Effectiveness Index across the window — see the generator. */
  collectionEffectiveness: number | null;
  overdueInvoices: number;
  /** Balance-weighted days past due, overdue invoices only. */
  averageDaysLate: number | null;
  invoiceCount: number;
  customerCount: number;
  /** Open balance more than `AT_RISK_DAYS` past due. */
  atRisk: number;
};

export type ReceivablesView = {
  asOf: string | null;
  asOfLabel: string;
  kpis: ReceivablesKpis;
  aging: AgingBucket[];
  debtors: DebtorSummary[];
  trend: ReceivablesTrendPoint[];
  /** Open invoices at the close of the window, largest first. */
  openInvoices: ReceivableRecord[];
};

const EMPTY_KPIS: ReceivablesKpis = {
  receivables: 0,
  dso: null,
  overdue: 0,
  overdueShare: null,
  collectionRate: null,
  collectionEffectiveness: null,
  overdueInvoices: 0,
  averageDaysLate: null,
  invoiceCount: 0,
  customerCount: 0,
  atRisk: 0,
};

/** Balance-weighted mean, so a large late invoice counts for more than a small one. */
function weightedDaysLate(invoices: ReceivableRecord[]): number | null {
  const late = invoices.filter((invoice) => invoice.days_overdue > 0);
  const weight = late.reduce((sum, invoice) => sum + invoice.outstanding, 0);
  if (weight <= 0) {
    return null;
  }
  return (
    late.reduce((sum, invoice) => sum + invoice.outstanding * invoice.days_overdue, 0) /
    weight
  );
}

export function buildReceivables(records: ReceivableRecord[]): ReceivablesView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const invoiceRows = records.filter((record) => record.kind === 'invoice');
  const memoRows = records.filter((record) => record.kind === 'memo');

  // Stock: only the closing month's snapshot is the open book.
  const openInvoices = invoiceRows
    .filter((record) => record.period === asOf && record.outstanding > 0)
    .sort((a, b) => b.outstanding - a.outstanding);

  const receivables = openInvoices.reduce(
    (sum, invoice) => sum + invoice.outstanding,
    0,
  );

  // --- aging.
  const aging: AgingBucket[] = AGING_BUCKETS.map(({ key, label }) => {
    const inBucket = openInvoices.filter((invoice) => invoice.aging_bucket === key);
    const amount = inBucket.reduce((sum, invoice) => sum + invoice.outstanding, 0);
    return {
      key,
      label,
      amount,
      count: inBucket.length,
      share: receivables > 0 ? amount / receivables : 0,
    };
  });

  // --- per-customer ledger.
  const debtorKeys: string[] = [];
  for (const invoice of openInvoices) {
    if (!debtorKeys.includes(invoice.customer)) {
      debtorKeys.push(invoice.customer);
    }
  }

  const debtors: DebtorSummary[] = debtorKeys
    .map((key) => {
      const forCustomer = openInvoices.filter((invoice) => invoice.customer === key);
      const outstanding = forCustomer.reduce(
        (sum, invoice) => sum + invoice.outstanding,
        0,
      );
      const overdueInvoices = forCustomer.filter((invoice) => invoice.days_overdue > 0);
      const first = forCustomer[0];
      return {
        key,
        label: first.customer_name,
        segment: first.segment,
        country: first.country,
        outstanding,
        current: outstanding - overdueInvoices.reduce((s, i) => s + i.outstanding, 0),
        overdue: overdueInvoices.reduce((sum, invoice) => sum + invoice.outstanding, 0),
        buckets: AGING_BUCKETS.map(({ key: bucketKey }) =>
          forCustomer
            .filter((invoice) => invoice.aging_bucket === bucketKey)
            .reduce((sum, invoice) => sum + invoice.outstanding, 0),
        ),
        invoiceCount: forCustomer.length,
        averageDaysLate: weightedDaysLate(forCustomer),
        oldestDaysOverdue:
          overdueInvoices.length > 0
            ? Math.max(...overdueInvoices.map((invoice) => invoice.days_overdue))
            : null,
        disputed: forCustomer
          .filter((invoice) => invoice.is_disputed)
          .reduce((sum, invoice) => sum + invoice.outstanding, 0),
        share: receivables > 0 ? outstanding / receivables : 0,
      };
    })
    .sort((a, b) => b.outstanding - a.outstanding);

  // --- monthly flows and the DSO series.
  const metricFor = (period: string, metric: string): number =>
    memoRows
      .filter((record) => record.period === period && record.metric === metric)
      .reduce((sum, record) => sum + record.amount, 0);

  const trend: ReceivablesTrendPoint[] = periodIds.map((period) => ({
    period,
    label: formatPeriodLabel(period),
    invoiced: metricFor(period, 'invoiced'),
    collected: metricFor(period, 'collected'),
    receivables: metricFor(period, 'receivables'),
    dso: metricFor(period, 'dso'),
  }));

  const totalInvoiced = trend.reduce((sum, point) => sum + point.invoiced, 0);
  const totalCollected = trend.reduce((sum, point) => sum + point.collected, 0);
  const totalCollectible = periodIds.reduce(
    (sum, period) => sum + metricFor(period, 'collectible'),
    0,
  );

  const overdueRows = openInvoices.filter((invoice) => invoice.days_overdue > 0);
  const overdue = overdueRows.reduce((sum, invoice) => sum + invoice.outstanding, 0);

  const kpis: ReceivablesKpis =
    invoiceRows.length === 0
      ? { ...EMPTY_KPIS }
      : {
          receivables,
          dso: asOf ? metricFor(asOf, 'dso') || null : null,
          overdue,
          overdueShare: receivables > 0 ? overdue / receivables : null,
          collectionRate: totalInvoiced > 0 ? totalCollected / totalInvoiced : null,
          collectionEffectiveness:
            totalCollectible > 0 ? totalCollected / totalCollectible : null,
          overdueInvoices: overdueRows.length,
          averageDaysLate: weightedDaysLate(openInvoices),
          invoiceCount: openInvoices.length,
          customerCount: debtors.length,
          atRisk: openInvoices
            .filter((invoice) => invoice.days_overdue > AT_RISK_DAYS)
            .reduce((sum, invoice) => sum + invoice.outstanding, 0),
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    kpis,
    aging,
    debtors,
    trend,
    openInvoices,
  };
}
