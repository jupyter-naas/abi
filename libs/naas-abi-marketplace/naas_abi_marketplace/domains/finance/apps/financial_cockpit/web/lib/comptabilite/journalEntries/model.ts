import type { Dataset } from '@/lib/types';

/**
 * Journal entries engine. Two record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `entry` — one manual journal entry. A **flow**: aggregate across the window.
 * - `memo`  — per-period aggregates: `ledger_entries`, the total the general
 *   ledger posted that month, which gives the manual share a denominator.
 *
 * Every row here is a manual entry taken from the ledger, so the entry count
 * equals the General Ledger page's Manual Entries by construction.
 */

export type JournalEntryRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'entry' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  entry_ref: string;
  entry_date: string;
  posted_date: string;
  journal: string;
  journal_label: string;
  label: string;
  entry_type: string;
  entry_type_label: string;
  debit_account: string;
  debit_account_label: string;
  credit_account: string;
  credit_account_label: string;
  line_count: number;
  amount: number;
  preparer: string;
  approver: string;
  status: string;
  status_label: string;
  approved_date: string;
  approval_days: number | null;
  deadline_date: string;
  is_late: boolean;
  days_late: number;
  is_open_period: boolean;
};

export type EntryTypeKey =
  | 'adjustment'
  | 'plug'
  | 'reclassification'
  | 'accrual'
  | 'provision';

/** The adjustment taxonomy, in the order the page reports it. */
export const ENTRY_TYPES: { key: EntryTypeKey; label: string }[] = [
  { key: 'adjustment', label: 'Adjustment' },
  { key: 'plug', label: 'Plug' },
  { key: 'reclassification', label: 'Reclassification' },
  { key: 'accrual', label: 'Accrual' },
  { key: 'provision', label: 'Provision' },
];

export type StatusKey = 'approved' | 'pending' | 'rejected';

export const STATUSES: { key: StatusKey; label: string }[] = [
  { key: 'approved', label: 'Approved' },
  { key: 'pending', label: 'Pending validation' },
  { key: 'rejected', label: 'Rejected' },
];

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isJournalEntryDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<JournalEntryRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function journalEntryRecords(
  dataset: Dataset | undefined,
): JournalEntryRecord[] {
  if (!isJournalEntryDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'entry' || record.kind === 'memo'),
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

export type EntryGroup = {
  key: string;
  label: string;
  amount: number;
  count: number;
  share: number;
};

export type EntryTrendPoint = {
  period: string;
  label: string;
  entries: number;
  late: number;
  pending: number;
  amount: number;
};

export type JournalEntryKpis = {
  entryCount: number;
  amount: number;
  /** Counts per adjustment type, keyed by `EntryTypeKey`. */
  byType: Record<string, number>;
  pending: number;
  rejected: number;
  late: number;
  /** Share of entries posted after the close deadline. */
  lateShare: number | null;
  /** Mean days from posting to validation, across settled entries. */
  approvalDays: number | null;
  /** Share of the ledger's entries that were keyed by hand. */
  manualShare: number | null;
  preparerCount: number;
};

export type JournalEntryView = {
  asOf: string | null;
  asOfLabel: string;
  kpis: JournalEntryKpis;
  types: EntryGroup[];
  statuses: EntryGroup[];
  preparers: EntryGroup[];
  trend: EntryTrendPoint[];
  /** Every entry in the window, largest first. */
  entries: JournalEntryRecord[];
};

const EMPTY_KPIS: JournalEntryKpis = {
  entryCount: 0,
  amount: 0,
  byType: {},
  pending: 0,
  rejected: 0,
  late: 0,
  lateShare: null,
  approvalDays: null,
  manualShare: null,
  preparerCount: 0,
};

/** Group entries by a key, summing amounts and counting rows. */
function groupEntries(
  entries: JournalEntryRecord[],
  keyOf: (entry: JournalEntryRecord) => string,
  labelOf: (entry: JournalEntryRecord) => string,
  total: number,
): EntryGroup[] {
  const keys: string[] = [];
  for (const entry of entries) {
    const key = keyOf(entry);
    if (!keys.includes(key)) {
      keys.push(key);
    }
  }
  return keys
    .map((key) => {
      const inGroup = entries.filter((entry) => keyOf(entry) === key);
      const amount = inGroup.reduce((sum, entry) => sum + entry.amount, 0);
      return {
        key,
        label: labelOf(inGroup[0]),
        amount,
        count: inGroup.length,
        share: total > 0 ? amount / total : 0,
      };
    })
    .sort((a, b) => b.amount - a.amount);
}

export function buildJournalEntries(
  records: JournalEntryRecord[],
): JournalEntryView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const entries = records
    .filter((record) => record.kind === 'entry')
    .sort((a, b) => b.amount - a.amount);
  const memoRows = records.filter((record) => record.kind === 'memo');

  const amount = entries.reduce((sum, entry) => sum + entry.amount, 0);

  const types = groupEntries(
    entries,
    (entry) => entry.entry_type,
    (entry) => entry.entry_type_label,
    amount,
  );
  const statuses = groupEntries(
    entries,
    (entry) => entry.status,
    (entry) => entry.status_label,
    amount,
  );
  const preparers = groupEntries(
    entries,
    (entry) => entry.preparer,
    (entry) => entry.preparer,
    amount,
  );

  const trend: EntryTrendPoint[] = periodIds.map((period) => {
    const inPeriod = entries.filter((entry) => entry.period === period);
    return {
      period,
      label: formatPeriodLabel(period),
      entries: inPeriod.length,
      late: inPeriod.filter((entry) => entry.is_late).length,
      pending: inPeriod.filter((entry) => entry.status === 'pending').length,
      amount: inPeriod.reduce((sum, entry) => sum + entry.amount, 0),
    };
  });

  const byType: Record<string, number> = {};
  for (const type of ENTRY_TYPES) {
    byType[type.key] = entries.filter((entry) => entry.entry_type === type.key).length;
  }

  // Approval time only counts entries a reviewer has actually settled —
  // averaging in the ones still waiting would understate it.
  const settled = entries.filter(
    (entry) => entry.status !== 'pending' && entry.approval_days !== null,
  );
  const ledgerEntries = memoRows
    .filter((record) => record.metric === 'ledger_entries')
    .reduce((sum, record) => sum + record.amount, 0);

  const kpis: JournalEntryKpis =
    entries.length === 0
      ? { ...EMPTY_KPIS }
      : {
          entryCount: entries.length,
          amount,
          byType,
          pending: entries.filter((entry) => entry.status === 'pending').length,
          rejected: entries.filter((entry) => entry.status === 'rejected').length,
          late: entries.filter((entry) => entry.is_late).length,
          lateShare: entries.filter((entry) => entry.is_late).length / entries.length,
          approvalDays:
            settled.length > 0
              ? settled.reduce((sum, entry) => sum + (entry.approval_days ?? 0), 0) /
                settled.length
              : null,
          manualShare: ledgerEntries > 0 ? entries.length / ledgerEntries : null,
          preparerCount: preparers.length,
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    kpis,
    types,
    statuses,
    preparers,
    trend,
    entries,
  };
}
