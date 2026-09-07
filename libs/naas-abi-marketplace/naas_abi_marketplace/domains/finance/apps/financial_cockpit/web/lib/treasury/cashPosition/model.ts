import type { Dataset } from '@/lib/types';

/**
 * Cash position engine. One record per bank account per month, plus `memo`
 * records (`account_type: "memo"`) carrying the short-term debt the balances
 * are netted against — those never appear in the accounts table.
 *
 * Balances are **stocks**: the KPIs, the distributions and the accounts table
 * all read the latest month in the selected window, never a sum across months.
 * Only the movement figures aggregate.
 */

export type CashAccountRecord = {
  period: string; // period-end ISO date, e.g. "2026-12-31"
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  account: string;
  account_label: string;
  bank: string;
  account_type: string;
  country: string;
  country_label: string;
  currency: string;
  reference: string;
  balance: number;
  restricted: number;
  available: number;
  movement: number;
};

const MEMO_TYPE = 'memo';
const MEMO_SHORT_TERM_DEBT = '_short_term_debt';

/** Human labels for the account types the generator emits. */
const TYPE_LABELS: Record<string, string> = {
  current: 'Current accounts',
  savings: 'Savings',
  escrow: 'Escrow',
  term_deposit: 'Term deposits',
};

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** Average days in a month, used to turn a monthly movement into a daily rate. */
const DAYS_PER_MONTH = 30.44;

export function isCashPositionDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<CashAccountRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function cashAccountRecords(
  dataset: Dataset | undefined,
): CashAccountRecord[] {
  if (!isCashPositionDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.balance === 'number' &&
      !Number.isNaN(record.balance) &&
      typeof record.period === 'string' &&
      typeof record.account === 'string',
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

export function accountTypeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type;
}

export type CashAccount = {
  key: string;
  label: string;
  bank: string;
  type: string;
  typeLabel: string;
  country: string;
  countryLabel: string;
  currency: string;
  reference: string;
  balance: number;
  restricted: number;
  available: number;
  movement: number;
};

export type CashShare = {
  key: string;
  label: string;
  value: number;
  /** Number of accounts behind the share — reused as the bar chart `count`. */
  count: number;
};

export type GeographicShare = CashShare & {
  currencies: string[];
};

export type CashPositionKpis = {
  balance: number;
  available: number;
  restricted: number;
  /** Balance net of short-term borrowings. */
  netCash: number;
  shortTermDebt: number;
  /** Average daily movement across the selected window. */
  dailyCashFlow: number;
  accountCount: number;
  bankCount: number;
};

export type CashTrendPoint = { period: string; label: string; balance: number; available: number };

export type CashPositionView = {
  periods: { id: string; label: string }[];
  asOf: string | null;
  asOfLabel: string;
  accounts: CashAccount[];
  kpis: CashPositionKpis;
  byType: CashShare[];
  byBank: CashShare[];
  byCountry: GeographicShare[];
  trend: CashTrendPoint[];
};

const EMPTY_KPIS: CashPositionKpis = {
  balance: 0,
  available: 0,
  restricted: 0,
  netCash: 0,
  shortTermDebt: 0,
  dailyCashFlow: 0,
  accountCount: 0,
  bankCount: 0,
};

/** Group a snapshot by one dimension, largest share first. */
function shareBy(
  snapshot: CashAccountRecord[],
  pick: (record: CashAccountRecord) => { key: string; label: string },
): CashShare[] {
  const groups = new Map<string, CashShare>();
  for (const record of snapshot) {
    const { key, label } = pick(record);
    const existing = groups.get(key);
    if (existing) {
      existing.value += record.balance;
      existing.count += 1;
    } else {
      groups.set(key, { key, label, value: record.balance, count: 1 });
    }
  }
  return [...groups.values()].sort((a, b) => b.value - a.value);
}

export function buildCashPosition(records: CashAccountRecord[]): CashPositionView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods = periodIds.map((id) => ({ id, label: formatPeriodLabel(id) }));
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const accountRecords = records.filter((r) => r.account_type !== MEMO_TYPE);
  const memoRecords = records.filter((r) => r.account_type === MEMO_TYPE);

  // --- as-of snapshot drives every balance figure.
  const snapshot = asOf ? accountRecords.filter((r) => r.period === asOf) : [];

  const accounts: CashAccount[] = snapshot
    .map((record) => ({
      key: record.account,
      label: record.account_label,
      bank: record.bank,
      type: record.account_type,
      typeLabel: accountTypeLabel(record.account_type),
      country: record.country,
      countryLabel: record.country_label,
      currency: record.currency,
      reference: record.reference,
      balance: record.balance,
      restricted: record.restricted,
      available: record.available,
      movement: record.movement,
    }))
    .sort((a, b) => b.balance - a.balance);

  const balance = accounts.reduce((sum, account) => sum + account.balance, 0);
  const restricted = accounts.reduce((sum, account) => sum + account.restricted, 0);
  const available = accounts.reduce((sum, account) => sum + account.available, 0);
  const shortTermDebt = asOf
    ? memoRecords
        .filter((r) => r.period === asOf && r.account === MEMO_SHORT_TERM_DEBT)
        .reduce((sum, record) => sum + record.balance, 0)
    : 0;

  // --- movement is a flow: average the monthly net across the window.
  //
  // The first month in the window has no prior snapshot to difference against,
  // so its movement is zero by construction and would drag the average down —
  // skip it.
  const movementPeriods = periodIds.slice(1);
  const totalMovement = accountRecords
    .filter((record) => movementPeriods.includes(record.period))
    .reduce((sum, record) => sum + record.movement, 0);
  const dailyCashFlow =
    movementPeriods.length > 0
      ? totalMovement / (movementPeriods.length * DAYS_PER_MONTH)
      : 0;

  const kpis: CashPositionKpis =
    accountRecords.length === 0
      ? { ...EMPTY_KPIS }
      : {
          balance,
          available,
          restricted,
          netCash: balance - shortTermDebt,
          shortTermDebt,
          dailyCashFlow,
          accountCount: accounts.length,
          bankCount: new Set(accounts.map((account) => account.bank)).size,
        };

  const byType = shareBy(snapshot, (record) => ({
    key: record.account_type,
    label: accountTypeLabel(record.account_type),
  }));
  const byBank = shareBy(snapshot, (record) => ({
    key: record.bank,
    label: record.bank,
  }));
  const byCountry: GeographicShare[] = shareBy(snapshot, (record) => ({
    key: record.country,
    label: record.country_label,
  })).map((share) => ({
    ...share,
    currencies: Array.from(
      new Set(
        snapshot
          .filter((record) => record.country === share.key)
          .map((record) => record.currency),
      ),
    ).sort(),
  }));

  // --- trend across every month in the window.
  const trend: CashTrendPoint[] = periodIds.map((period) => {
    const forPeriod = accountRecords.filter((record) => record.period === period);
    return {
      period,
      label: formatPeriodLabel(period),
      balance: forPeriod.reduce((sum, record) => sum + record.balance, 0),
      available: forPeriod.reduce((sum, record) => sum + record.available, 0),
    };
  });

  return {
    periods,
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    accounts,
    kpis,
    byType,
    byBank,
    byCountry,
    trend,
  };
}
