import {
  budgetBucket,
  signedBudgetAmount,
  type PnlAdjustment,
  type PnlBudgetRow,
} from '@/lib/pnl/model';

export const PNL_SCENARIO_BUD = 'BUD' as const;
export const PNL_SCENARIO_ADJUST = 'ADJUST' as const;

export type BudgetScenario = typeof PNL_SCENARIO_BUD | typeof PNL_SCENARIO_ADJUST;

export type BudgetLineEntry = {
  key: string;
  scenario: BudgetScenario;
  organization_slug: string;
  company: string;
  famille_2: string;
  categorie_2: string;
  categorie_3: string;
  thirdparty: string;
  month: string;
  amount: number;
  user: string;
  date_edited: string;
  budgetRowId?: string;
  adjustmentId?: string;
};

export type BudgetOverviewRow = {
  key: string;
  scenario: BudgetScenario;
  famille_2: string;
  categorie_2: string;
  thirdparty: string;
  months: number[];
  total: number;
};

export const MONTH_LABELS = [
  'Janv',
  'Févr',
  'Mars',
  'Avr',
  'Mai',
  'Juin',
  'Juil',
  'Août',
  'Sept',
  'Oct',
  'Nov',
  'Déc',
] as const;

function monthIndex(month: string): number | null {
  const match = /^(\d{4})-(\d{2})$/.exec(month.trim());
  if (!match) {
    return null;
  }
  const index = Number(match[2]) - 1;
  return index >= 0 && index < 12 ? index : null;
}

function companyLabel(
  organizationSlug: string,
  companyBySlug: ReadonlyMap<string, string>,
): string {
  return companyBySlug.get(organizationSlug) ?? organizationSlug;
}

export function budgetRowsToEntries(
  rows: PnlBudgetRow[],
  companyBySlug: ReadonlyMap<string, string>,
  year: string,
): BudgetLineEntry[] {
  const entries: BudgetLineEntry[] = [];
  for (const row of rows) {
    if (row.year !== year) {
      continue;
    }
    const bucket = budgetBucket(row.famille_2);
    row.months.forEach((rawAmount, index) => {
      if (!rawAmount) {
        return;
      }
      const month = `${year}-${String(index + 1).padStart(2, '0')}`;
      entries.push({
        key: `bud:${row.id}:${index}`,
        scenario: PNL_SCENARIO_BUD,
        organization_slug: row.organization_slug,
        company: companyLabel(row.organization_slug, companyBySlug),
        famille_2: row.famille_2,
        categorie_2: row.categorie_2,
        categorie_3: '',
        thirdparty: row.thirdparty,
        month,
        amount: signedBudgetAmount(bucket, rawAmount),
        user: row.user,
        date_edited: row.date_edited,
        budgetRowId: row.id,
      });
    });
  }
  return entries;
}

export function adjustmentsToEntries(
  adjustments: PnlAdjustment[],
  year: string,
): BudgetLineEntry[] {
  return adjustments
    .filter((row) => row.month.startsWith(`${year}-`))
    .map((row) => ({
      key: `adj:${row.id}`,
      scenario: PNL_SCENARIO_ADJUST,
      organization_slug: row.organization_slug,
      company: row.company,
      famille_2: row.famille_2,
      categorie_2: row.categorie_2,
      categorie_3: row.categorie_3,
      thirdparty: row.thirdparty,
      month: row.month,
      amount: row.amount,
      user: row.user,
      date_edited: row.date_edited,
      adjustmentId: row.id,
    }));
}

export function buildBudgetOverview(entries: BudgetLineEntry[]): BudgetOverviewRow[] {
  const grouped = new Map<string, BudgetOverviewRow>();

  for (const entry of entries) {
    const groupKey = [
      entry.scenario,
      entry.famille_2,
      entry.categorie_2,
      entry.thirdparty,
    ].join('\0');
    let row = grouped.get(groupKey);
    if (!row) {
      row = {
        key: groupKey,
        scenario: entry.scenario,
        famille_2: entry.famille_2,
        categorie_2: entry.categorie_2,
        thirdparty: entry.thirdparty,
        months: Array.from({ length: 12 }, () => 0),
        total: 0,
      };
      grouped.set(groupKey, row);
    }
    const index = monthIndex(entry.month);
    if (index === null) {
      continue;
    }
    row.months[index] += entry.amount;
    row.total += entry.amount;
  }

  return [...grouped.values()].sort((a, b) => {
    const left = `${a.scenario}|${a.famille_2}|${a.categorie_2}|${a.thirdparty}`;
    const right = `${b.scenario}|${b.famille_2}|${b.categorie_2}|${b.thirdparty}`;
    return left.localeCompare(right, 'fr');
  });
}

export function monthlyTotals(rows: BudgetOverviewRow[]): { months: number[]; total: number } {
  const months = Array.from({ length: 12 }, () => 0);
  let total = 0;
  for (const row of rows) {
    row.months.forEach((value, index) => {
      months[index] += value;
    });
    total += row.total;
  }
  return { months, total };
}

export function applyBudgetLineEntry(
  rows: PnlBudgetRow[],
  entry: Pick<
    BudgetLineEntry,
    'organization_slug' | 'famille_2' | 'categorie_2' | 'thirdparty' | 'month' | 'amount'
  >,
): PnlBudgetRow {
  const year = entry.month.slice(0, 4);
  const index = monthIndex(entry.month);
  if (!year || index === null) {
    throw new Error('Invalid budget month');
  }

  const storedAmount = Math.abs(entry.amount);

  const existing = rows.find(
    (row) =>
      row.organization_slug === entry.organization_slug &&
      row.famille_2 === entry.famille_2 &&
      row.categorie_2 === entry.categorie_2 &&
      row.thirdparty === entry.thirdparty &&
      row.year === year,
  );

  const months = existing ? [...existing.months] : Array.from({ length: 12 }, () => 0);
  months[index] = storedAmount;

  return {
    id: existing?.id ?? '',
    organization_slug: entry.organization_slug,
    famille_2: entry.famille_2,
    categorie_2: entry.categorie_2,
    thirdparty: entry.thirdparty,
    year,
    months,
    user: existing?.user ?? '',
    date_edited: existing?.date_edited ?? '',
  };
}

export function clearBudgetMonth(
  rows: PnlBudgetRow[],
  entry: Pick<BudgetLineEntry, 'budgetRowId' | 'month'>,
): PnlBudgetRow | null {
  if (!entry.budgetRowId) {
    return null;
  }
  const existing = rows.find((row) => row.id === entry.budgetRowId);
  if (!existing) {
    return null;
  }
  const index = monthIndex(entry.month);
  if (index === null) {
    return null;
  }
  const months = [...existing.months];
  months[index] = 0;
  return { ...existing, months };
}
