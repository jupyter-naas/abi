import type { Dataset } from '@/lib/types';

/**
 * General ledger engine. Two record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `line` — one posting line. A **flow**: aggregate across the window.
 * - `memo` — per-period aggregates: the month's revenue and cost base, and
 *   whether the period is still open.
 *
 * Everything on the page counts **lines** or the **entries** they belong to.
 * An entry is a set of lines sharing an `entry_ref`; it always balances, so
 * total debit equals total credit for any selection of whole entries — which
 * is what the Balance check on the page asserts.
 */

export type LedgerRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'line' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  entry_ref: string;
  line_no: number;
  entry_date: string;
  posted_date: string;
  journal: string;
  journal_code: string;
  journal_label: string;
  account: string;
  account_label: string;
  account_type: string;
  label: string;
  third_party: string;
  debit: number;
  credit: number;
  amount: number;
  source: string;
  user: string;
};

/** A ledger line is `manual` when a human keyed it, `imported` otherwise. */
export const MANUAL_SOURCE = 'manual';

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isLedgerDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<LedgerRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function ledgerRecords(dataset: Dataset | undefined): LedgerRecord[] {
  if (!isLedgerDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.debit === 'number' &&
      typeof record.credit === 'number' &&
      !Number.isNaN(record.debit) &&
      !Number.isNaN(record.credit) &&
      (record.kind === 'line' || record.kind === 'memo'),
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

export type AccountActivity = {
  key: string;
  label: string;
  /** Total movement on the account — debits plus credits. */
  amount: number;
  /** Signed net: debit-heavy accounts are positive. */
  net: number;
  count: number;
  type: string;
};

export type JournalActivity = {
  key: string;
  code: string;
  label: string;
  /** Entries posted to the journal. */
  entries: number;
  lines: number;
  amount: number;
};

export type LedgerTrendPoint = {
  period: string;
  label: string;
  entries: number;
  lines: number;
  manualEntries: number;
  importedEntries: number;
  debit: number;
  credit: number;
};

export type LedgerKpis = {
  entryCount: number;
  accountCount: number;
  /** Posting lines — the transactions the ledger actually holds. */
  lineCount: number;
  openPeriods: number;
  periodCount: number;
  manualEntries: number;
  importedEntries: number;
  /** Share of entries a human keyed. */
  manualShare: number | null;
  debit: number;
  credit: number;
  /** Debit − credit across the window. Zero on a balanced ledger. */
  imbalance: number;
};

export type LedgerView = {
  asOf: string | null;
  asOfLabel: string;
  kpis: LedgerKpis;
  accounts: AccountActivity[];
  journals: JournalActivity[];
  trend: LedgerTrendPoint[];
  /** Every posting line in the window, most recent first. */
  lines: LedgerRecord[];
};

const EMPTY_KPIS: LedgerKpis = {
  entryCount: 0,
  accountCount: 0,
  lineCount: 0,
  openPeriods: 0,
  periodCount: 0,
  manualEntries: 0,
  importedEntries: 0,
  manualShare: null,
  debit: 0,
  credit: 0,
  imbalance: 0,
};

export function buildGeneralLedger(records: LedgerRecord[]): LedgerView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const lines = records.filter((record) => record.kind === 'line');
  const memoRows = records.filter((record) => record.kind === 'memo');

  // --- accounts: total movement, so a contra account is not netted away.
  const accountMap = new Map<string, AccountActivity>();
  for (const line of lines) {
    const current = accountMap.get(line.account) ?? {
      key: line.account,
      label: `${line.account} — ${line.account_label}`,
      amount: 0,
      net: 0,
      count: 0,
      type: line.account_type,
    };
    current.amount += line.debit + line.credit;
    current.net += line.debit - line.credit;
    current.count += 1;
    accountMap.set(line.account, current);
  }
  const accounts = Array.from(accountMap.values()).sort((a, b) => b.amount - a.amount);

  // --- journals: entries are counted once, however many lines they carry.
  const journalMap = new Map<string, JournalActivity & { refs: Set<string> }>();
  for (const line of lines) {
    const current = journalMap.get(line.journal) ?? {
      key: line.journal,
      code: line.journal_code,
      label: line.journal_label,
      entries: 0,
      lines: 0,
      amount: 0,
      refs: new Set<string>(),
    };
    current.refs.add(line.entry_ref);
    current.lines += 1;
    current.amount += line.debit;
    journalMap.set(line.journal, current);
  }
  const journals: JournalActivity[] = Array.from(journalMap.values())
    .map(({ refs, ...journal }) => ({ ...journal, entries: refs.size }))
    .sort((a, b) => b.entries - a.entries);

  const trend: LedgerTrendPoint[] = periodIds.map((period) => {
    const inPeriod = lines.filter((line) => line.period === period);
    const refs = new Set(inPeriod.map((line) => line.entry_ref));
    const manualRefs = new Set(
      inPeriod
        .filter((line) => line.source === MANUAL_SOURCE)
        .map((line) => line.entry_ref),
    );
    return {
      period,
      label: formatPeriodLabel(period),
      entries: refs.size,
      lines: inPeriod.length,
      manualEntries: manualRefs.size,
      importedEntries: refs.size - manualRefs.size,
      debit: inPeriod.reduce((sum, line) => sum + line.debit, 0),
      credit: inPeriod.reduce((sum, line) => sum + line.credit, 0),
    };
  });

  const entryRefs = new Set(lines.map((line) => line.entry_ref));
  const manualRefs = new Set(
    lines.filter((line) => line.source === MANUAL_SOURCE).map((line) => line.entry_ref),
  );
  const debit = lines.reduce((sum, line) => sum + line.debit, 0);
  const credit = lines.reduce((sum, line) => sum + line.credit, 0);
  const openPeriods = memoRows.filter(
    (record) => record.metric === 'open_period' && record.amount > 0,
  ).length;

  const kpis: LedgerKpis =
    lines.length === 0
      ? { ...EMPTY_KPIS, periodCount: periodIds.length }
      : {
          entryCount: entryRefs.size,
          accountCount: accounts.length,
          lineCount: lines.length,
          openPeriods,
          periodCount: periodIds.length,
          manualEntries: manualRefs.size,
          importedEntries: entryRefs.size - manualRefs.size,
          manualShare: entryRefs.size > 0 ? manualRefs.size / entryRefs.size : null,
          debit,
          credit,
          // Rounded to the cent: the ledger balances, and float addition over
          // thousands of lines should not make it look like it does not.
          imbalance: Math.round((debit - credit) * 100) / 100,
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    kpis,
    accounts,
    journals,
    trend,
    lines: [...lines].sort((a, b) =>
      a.entry_date === b.entry_date
        ? a.entry_ref === b.entry_ref
          ? a.line_no - b.line_no
          : a.entry_ref < b.entry_ref
            ? 1
            : -1
        : a.entry_date < b.entry_date
          ? 1
          : -1,
    ),
  };
}
