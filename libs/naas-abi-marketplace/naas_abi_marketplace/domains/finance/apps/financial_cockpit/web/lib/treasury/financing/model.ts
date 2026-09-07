import type { Dataset } from '@/lib/types';

/**
 * Financing engine. One record per facility per month, plus `memo` records
 * (`instrument: "memo"`) carrying the asset base the Debt Ratio is measured
 * against — those never appear in the loans table.
 *
 * Outstanding balances and rates are **stocks** read from the latest month in
 * the window; interest, repayments and drawdowns are **flows** that aggregate
 * across it.
 */

export type LoanRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  loan: string;
  loan_label: string;
  lender: string;
  instrument: string;
  bucket: string;
  outstanding: number;
  rate: number;
  is_floating: boolean;
  reference_rate: number | null;
  interest: number;
  repayment: number;
  drawdown: number;
  origination: string;
  maturity: string;
  covenant: string;
  is_matured: boolean;
};

const MEMO_INSTRUMENT = 'memo';
const MEMO_TOTAL_ASSETS = '_total_assets';

/** Human labels for the instrument types the generator emits. */
const INSTRUMENT_LABELS: Record<string, string> = {
  term_loan: 'Term loan',
  revolving: 'Revolving',
  lease: 'Lease',
  bond: 'Bond',
  state_backed: 'State-backed',
};

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isFinancingDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<LoanRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function loanRecords(dataset: Dataset | undefined): LoanRecord[] {
  if (!isFinancingDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.outstanding === 'number' &&
      !Number.isNaN(record.outstanding) &&
      typeof record.period === 'string' &&
      typeof record.loan === 'string',
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

export function instrumentLabel(instrument: string): string {
  return INSTRUMENT_LABELS[instrument] ?? instrument;
}

export type Loan = {
  key: string;
  label: string;
  lender: string;
  instrument: string;
  instrumentLabel: string;
  bucket: string;
  outstanding: number;
  rate: number;
  isFloating: boolean;
  referenceRate: number | null;
  /** Interest charged over the whole window, not just the closing month. */
  interest: number;
  repayment: number;
  drawdown: number;
  origination: string;
  maturity: string;
  covenant: string;
  /** Years from the window's close to maturity; negative once matured. */
  yearsToMaturity: number | null;
};

export type LenderShare = {
  key: string;
  label: string;
  value: number;
  count: number;
};

export type MaturityBucket = {
  year: string;
  amount: number;
  loans: string[];
};

export type DebtTrendPoint = {
  period: string;
  label: string;
  longTerm: number;
  shortTerm: number;
  total: number;
  interest: number;
  averageRate: number;
};

export type FinancingKpis = {
  outstanding: number;
  /** Interest charged across the window. */
  interestExpense: number;
  /** Balance-weighted rate at the close of the window. */
  averageRate: number | null;
  nextMaturity: string | null;
  nextMaturityLabel: string;
  nextMaturityAmount: number;
  /** Repayments plus interest across the window. */
  debtService: number;
  /** Outstanding debt over total assets. */
  debtRatio: number | null;
  loanCount: number;
};

export type FinancingView = {
  periods: { id: string; label: string }[];
  asOf: string | null;
  asOfLabel: string;
  loans: Loan[];
  kpis: FinancingKpis;
  byLender: LenderShare[];
  maturities: MaturityBucket[];
  trend: DebtTrendPoint[];
  /** Earliest origination and latest maturity, for the timeline axis. */
  timelineStart: string | null;
  timelineEnd: string | null;
};

const EMPTY_KPIS: FinancingKpis = {
  outstanding: 0,
  interestExpense: 0,
  averageRate: null,
  nextMaturity: null,
  nextMaturityLabel: '—',
  nextMaturityAmount: 0,
  debtService: 0,
  debtRatio: null,
  loanCount: 0,
};

const MS_PER_YEAR = 365.25 * 24 * 60 * 60 * 1000;

function yearsBetween(from: string, to: string): number | null {
  if (!from || !to) {
    return null;
  }
  const start = Date.parse(from);
  const end = Date.parse(to);
  if (Number.isNaN(start) || Number.isNaN(end)) {
    return null;
  }
  return (end - start) / MS_PER_YEAR;
}

export function buildFinancing(records: LoanRecord[]): FinancingView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods = periodIds.map((id) => ({ id, label: formatPeriodLabel(id) }));
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const loanRows = records.filter((r) => r.instrument !== MEMO_INSTRUMENT);
  const memoRows = records.filter((r) => r.instrument === MEMO_INSTRUMENT);

  // --- one row per facility: balance as of the close, flows across the window.
  const loanKeys: string[] = [];
  for (const record of loanRows) {
    if (!loanKeys.includes(record.loan)) {
      loanKeys.push(record.loan);
    }
  }

  const loans: Loan[] = loanKeys
    .map((key) => {
      const forLoan = loanRows.filter((r) => r.loan === key);
      const closing = forLoan.find((r) => r.period === asOf) ?? forLoan[forLoan.length - 1];
      return {
        key,
        label: closing.loan_label,
        lender: closing.lender,
        instrument: closing.instrument,
        instrumentLabel: instrumentLabel(closing.instrument),
        bucket: closing.bucket,
        outstanding: closing.outstanding,
        rate: closing.rate,
        isFloating: closing.is_floating,
        referenceRate: closing.reference_rate,
        interest: forLoan.reduce((sum, record) => sum + record.interest, 0),
        repayment: forLoan.reduce((sum, record) => sum + record.repayment, 0),
        drawdown: forLoan.reduce((sum, record) => sum + record.drawdown, 0),
        origination: closing.origination,
        maturity: closing.maturity,
        covenant: closing.covenant,
        yearsToMaturity: asOf ? yearsBetween(asOf, closing.maturity) : null,
      };
    })
    .sort((a, b) => b.outstanding - a.outstanding);

  const live = loans.filter((loan) => loan.outstanding > 0);
  const outstanding = live.reduce((sum, loan) => sum + loan.outstanding, 0);
  const interestExpense = loans.reduce((sum, loan) => sum + loan.interest, 0);
  const repayments = loans.reduce((sum, loan) => sum + loan.repayment, 0);
  const totalAssets = asOf
    ? memoRows
        .filter((r) => r.period === asOf && r.loan === MEMO_TOTAL_ASSETS)
        .reduce((sum, record) => sum + record.outstanding, 0)
    : 0;

  // Next repayment wall: the soonest maturity still carrying a balance.
  const upcoming = [...live]
    .filter((loan) => Boolean(loan.maturity))
    .sort((a, b) => a.maturity.localeCompare(b.maturity))[0];

  const kpis: FinancingKpis =
    loanRows.length === 0
      ? { ...EMPTY_KPIS }
      : {
          outstanding,
          interestExpense,
          averageRate:
            outstanding > 0
              ? live.reduce((sum, loan) => sum + loan.outstanding * loan.rate, 0) /
                outstanding
              : null,
          nextMaturity: upcoming?.maturity ?? null,
          nextMaturityLabel: upcoming ? formatPeriodLabel(upcoming.maturity) : '—',
          nextMaturityAmount: upcoming?.outstanding ?? 0,
          debtService: repayments + interestExpense,
          debtRatio: totalAssets > 0 ? outstanding / totalAssets : null,
          loanCount: live.length,
        };

  // --- concentration by lender.
  const lenderGroups = new Map<string, LenderShare>();
  for (const loan of live) {
    const existing = lenderGroups.get(loan.lender);
    if (existing) {
      existing.value += loan.outstanding;
      existing.count += 1;
    } else {
      lenderGroups.set(loan.lender, {
        key: loan.lender,
        label: loan.lender,
        value: loan.outstanding,
        count: 1,
      });
    }
  }
  const byLender = [...lenderGroups.values()].sort((a, b) => b.value - a.value);

  // --- repayment wall: what falls due in each calendar year.
  const maturityGroups = new Map<string, MaturityBucket>();
  for (const loan of live) {
    const year = loan.maturity.slice(0, 4);
    if (!year) {
      continue;
    }
    const existing = maturityGroups.get(year);
    if (existing) {
      existing.amount += loan.outstanding;
      existing.loans.push(loan.label);
    } else {
      maturityGroups.set(year, {
        year,
        amount: loan.outstanding,
        loans: [loan.label],
      });
    }
  }
  const maturities = [...maturityGroups.values()].sort((a, b) =>
    a.year.localeCompare(b.year),
  );

  // --- trend across every month in the window.
  const trend: DebtTrendPoint[] = periodIds.map((period) => {
    const forPeriod = loanRows.filter((record) => record.period === period);
    const longTerm = forPeriod
      .filter((record) => record.bucket === 'long')
      .reduce((sum, record) => sum + record.outstanding, 0);
    const shortTerm = forPeriod
      .filter((record) => record.bucket === 'short')
      .reduce((sum, record) => sum + record.outstanding, 0);
    const total = longTerm + shortTerm;
    const weighted = forPeriod.reduce(
      (sum, record) => sum + record.outstanding * record.rate,
      0,
    );
    return {
      period,
      label: formatPeriodLabel(period),
      longTerm,
      shortTerm,
      total,
      interest: forPeriod.reduce((sum, record) => sum + record.interest, 0),
      averageRate: total > 0 ? weighted / total : 0,
    };
  });

  const originations = loans.map((loan) => loan.origination).filter(Boolean).sort();
  const maturityDates = loans.map((loan) => loan.maturity).filter(Boolean).sort();

  return {
    periods,
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    loans,
    kpis,
    byLender,
    maturities,
    trend,
    timelineStart: originations[0] ?? null,
    timelineEnd: maturityDates[maturityDates.length - 1] ?? null,
  };
}
