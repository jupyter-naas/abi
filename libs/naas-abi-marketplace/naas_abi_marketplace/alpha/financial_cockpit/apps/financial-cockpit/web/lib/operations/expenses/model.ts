import type { Dataset } from '@/lib/types';

/**
 * Expenses engine. Two record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `expense` — one expense line. A **flow**: aggregate across the window.
 * - `memo` — per-period context the lines cannot carry: the month's cost base,
 *   the controllable-expense total, and the prior month's total. The last one
 *   is what makes Expense Growth defined on a single-month window, since the
 *   server pre-filters records by scenario and the prior month is simply not
 *   in the data the section receives.
 *
 * The lines sum back to the cash flow's cost base times the overhead share, so
 * the totals here reconcile with Cost Centers and the P&L.
 */

export type ExpenseRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'expense' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  expense_ref: string;
  expense_date: string;
  category: string;
  category_label: string;
  department: string;
  department_label: string;
  division_label: string;
  vendor: string;
  requester: string;
  amount: number;
  payment_method: string;
  payment_method_label: string;
  status: string;
  status_label: string;
  has_receipt: boolean;
};

/** Categories called out as their own KPI card. */
export const HEADLINE_CATEGORIES = ['travel', 'software', 'marketing'] as const;

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isExpensesDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<ExpenseRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function expenseRecords(dataset: Dataset | undefined): ExpenseRecord[] {
  if (!isExpensesDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'expense' || record.kind === 'memo'),
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

export type CategorySummary = {
  key: string;
  label: string;
  amount: number;
  count: number;
  share: number;
  /** Average line value — a category of many small claims reads differently
   *  from one of a few large invoices. */
  averageLine: number;
};

export type DepartmentSummary = {
  key: string;
  label: string;
  divisionLabel: string;
  amount: number;
  count: number;
  share: number;
  /** Spend by category, keyed the same way as `categories`. */
  byCategory: { key: string; label: string; amount: number }[];
};

export type DivisionSpend = {
  key: string;
  label: string;
  amount: number;
  departments: { key: string; label: string; amount: number }[];
};

export type ExpenseTrendPoint = {
  period: string;
  label: string;
  amount: number;
  count: number;
};

export type ExpenseKpis = {
  total: number;
  count: number;
  averageExpense: number | null;
  /** Spend on each of `HEADLINE_CATEGORIES`, in that order. */
  headline: { key: string; label: string; amount: number; share: number }[];
  /** Closing month against the month before it. Null when there is no prior. */
  growth: number | null;
  /** Controllable expenses over the cost base — how much of the cost base is
   *  actually steerable. */
  costBaseShare: number | null;
  /** Lines still awaiting approval at the close of the window. */
  pendingAmount: number;
  pendingCount: number;
  /** Policy exceptions: settled or approved lines with no receipt attached. */
  missingReceipts: number;
};

export type ExpensesView = {
  asOf: string | null;
  asOfLabel: string;
  monthCount: number;
  kpis: ExpenseKpis;
  categories: CategorySummary[];
  departments: DepartmentSummary[];
  divisions: DivisionSpend[];
  trend: ExpenseTrendPoint[];
  /** Every expense line in the window, largest first. */
  lines: ExpenseRecord[];
};

const EMPTY_KPIS: ExpenseKpis = {
  total: 0,
  count: 0,
  averageExpense: null,
  headline: [],
  growth: null,
  costBaseShare: null,
  pendingAmount: 0,
  pendingCount: 0,
  missingReceipts: 0,
};

export function buildExpenses(records: ExpenseRecord[]): ExpensesView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const lines = records
    .filter((record) => record.kind === 'expense')
    .sort((a, b) => b.amount - a.amount);
  const memoRows = records.filter((record) => record.kind === 'memo');

  const total = lines.reduce((sum, line) => sum + line.amount, 0);

  const metricFor = (period: string, metric: string): number =>
    memoRows
      .filter((record) => record.period === period && record.metric === metric)
      .reduce((sum, record) => sum + record.amount, 0);

  // --- by category.
  const categoryKeys: string[] = [];
  for (const line of lines) {
    if (!categoryKeys.includes(line.category)) {
      categoryKeys.push(line.category);
    }
  }
  const categories: CategorySummary[] = categoryKeys
    .map((key) => {
      const inCategory = lines.filter((line) => line.category === key);
      const amount = inCategory.reduce((sum, line) => sum + line.amount, 0);
      return {
        key,
        label: inCategory[0].category_label,
        amount,
        count: inCategory.length,
        share: total > 0 ? amount / total : 0,
        averageLine: inCategory.length > 0 ? amount / inCategory.length : 0,
      };
    })
    .sort((a, b) => b.amount - a.amount);

  // --- by department, each broken down by category for the tooltip/detail.
  const departmentKeys: string[] = [];
  for (const line of lines) {
    if (!departmentKeys.includes(line.department)) {
      departmentKeys.push(line.department);
    }
  }
  const departments: DepartmentSummary[] = departmentKeys
    .map((key) => {
      const inDepartment = lines.filter((line) => line.department === key);
      const amount = inDepartment.reduce((sum, line) => sum + line.amount, 0);
      const byCategory = categoryKeys
        .map((categoryKey) => {
          const rows = inDepartment.filter((line) => line.category === categoryKey);
          return {
            key: categoryKey,
            label: rows[0]?.category_label ?? categoryKey,
            amount: rows.reduce((sum, line) => sum + line.amount, 0),
          };
        })
        .filter((entry) => entry.amount > 0)
        .sort((a, b) => b.amount - a.amount);
      return {
        key,
        label: inDepartment[0].department_label,
        divisionLabel: inDepartment[0].division_label,
        amount,
        count: inDepartment.length,
        share: total > 0 ? amount / total : 0,
        byCategory,
      };
    })
    .sort((a, b) => b.amount - a.amount);

  // --- divisions wrap departments, which is what the treemap nests.
  const divisionKeys: string[] = [];
  for (const department of departments) {
    if (!divisionKeys.includes(department.divisionLabel)) {
      divisionKeys.push(department.divisionLabel);
    }
  }
  const divisions: DivisionSpend[] = divisionKeys
    .map((label) => {
      const inDivision = departments.filter(
        (department) => department.divisionLabel === label,
      );
      return {
        key: label,
        label,
        amount: inDivision.reduce((sum, department) => sum + department.amount, 0),
        departments: inDivision.map((department) => ({
          key: department.key,
          label: department.label,
          amount: department.amount,
        })),
      };
    })
    .sort((a, b) => b.amount - a.amount);

  // --- monthly trend.
  const trend: ExpenseTrendPoint[] = periodIds.map((period) => {
    const inPeriod = lines.filter((line) => line.period === period);
    return {
      period,
      label: formatPeriodLabel(period),
      amount: inPeriod.reduce((sum, line) => sum + line.amount, 0),
      count: inPeriod.length,
    };
  });

  // Growth compares the closing month against the one before it. Inside a
  // multi-month window that prior month is on screen; on a single-month window
  // it is not, which is what the memo carries.
  const closingTotal = asOf ? metricFor(asOf, 'expenses') : 0;
  const priorTotal = asOf ? metricFor(asOf, 'prior_month_expenses') : 0;
  const growth =
    priorTotal > 0 && closingTotal > 0 ? closingTotal / priorTotal - 1 : null;

  const costBase = periodIds.reduce(
    (sum, period) => sum + metricFor(period, 'cost_base'),
    0,
  );

  const pending = lines.filter((line) => line.status === 'pending');

  const kpis: ExpenseKpis =
    lines.length === 0
      ? { ...EMPTY_KPIS }
      : {
          total,
          count: lines.length,
          averageExpense: total / lines.length,
          headline: HEADLINE_CATEGORIES.map((key) => {
            const category = categories.find((entry) => entry.key === key);
            return {
              key,
              label: category?.label ?? key,
              amount: category?.amount ?? 0,
              share: category?.share ?? 0,
            };
          }),
          growth,
          costBaseShare: costBase > 0 ? total / costBase : null,
          pendingAmount: pending.reduce((sum, line) => sum + line.amount, 0),
          pendingCount: pending.length,
          missingReceipts: lines.filter((line) => !line.has_receipt).length,
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    monthCount: periodIds.length,
    kpis,
    categories,
    departments,
    divisions,
    trend,
    lines,
  };
}
