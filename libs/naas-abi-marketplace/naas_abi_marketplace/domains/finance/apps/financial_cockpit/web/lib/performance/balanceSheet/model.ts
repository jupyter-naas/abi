import type { Dataset } from '@/lib/types';

/**
 * Balance sheet engine. The dataset carries monthly period-end snapshots; a
 * scenario selection (year or month) narrows the records the section receives.
 * "As-of" = the latest snapshot in that window; the KPIs, composition and the
 * two balance columns read that snapshot, while the trend charts walk every
 * snapshot present.
 */

export type BalanceSheetSection = 'assets' | 'equity_liabilities';

export type BalanceSheetRecord = {
  period: string; // period-end ISO date, e.g. "2026-12-31"
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  section: BalanceSheetSection;
  group: string;
  group_label: string;
  category: string;
  amount: number;
  is_cash: boolean;
  is_debt: boolean;
  is_current: boolean;
};

/** Canonical top-to-bottom order of the balance sheet groups. */
const GROUP_ORDER = [
  'non_current_assets',
  'current_assets',
  'equity',
  'non_current_liabilities',
  'current_liabilities',
] as const;

const SECTION_ORDER: { id: BalanceSheetSection; label: string }[] = [
  { id: 'assets', label: 'Assets' },
  { id: 'equity_liabilities', label: 'Equity & Liabilities' },
];

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isBalanceSheetDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<BalanceSheetRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function balanceSheetRecords(
  dataset: Dataset | undefined,
): BalanceSheetRecord[] {
  if (!isBalanceSheetDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      typeof record.period === 'string' &&
      (record.section === 'assets' || record.section === 'equity_liabilities'),
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

export type BalanceSheetPeriod = { id: string; label: string };

export type BsAmounts = Record<string, number>;

export type BsCategoryRow = {
  key: string;
  label: string;
  amounts: BsAmounts;
  records: BalanceSheetRecord[];
};

export type BsGroupRow = {
  key: string;
  label: string;
  section: BalanceSheetSection;
  amounts: BsAmounts;
  categories: BsCategoryRow[];
};

export type BsSectionRow = {
  id: BalanceSheetSection;
  label: string;
  amounts: BsAmounts;
  groups: BsGroupRow[];
};

export type BalanceSheetKpis = {
  totalAssets: number;
  nonCurrentAssets: number;
  currentAssets: number;
  totalEquity: number;
  totalLiabilities: number;
  currentLiabilities: number;
  nonCurrentLiabilities: number;
  cash: number;
  grossDebt: number;
  netDebt: number;
  workingCapital: number;
  /** Current assets / current liabilities; null when there are no current liabilities. */
  currentRatio: number | null;
};

export type CompositionSlice = { key: string; label: string; value: number };

export type BalanceBar = { key: string; label: string; value: number };

export type TrendPoint = { period: string; label: string; value: number };

export type DebtTrendPoint = {
  period: string;
  label: string;
  grossDebt: number;
  netDebt: number;
  cash: number;
};

export type BalanceSheetStatement = {
  periods: BalanceSheetPeriod[];
  asOf: string | null;
  asOfLabel: string;
  sections: BsSectionRow[];
  kpis: BalanceSheetKpis;
  composition: CompositionSlice[];
  assetBars: BalanceBar[];
  financingBars: BalanceBar[];
  workingCapitalTrend: TrendPoint[];
  debtTrend: DebtTrendPoint[];
  isBalanced: boolean;
};

const EMPTY_KPIS: BalanceSheetKpis = {
  totalAssets: 0,
  nonCurrentAssets: 0,
  currentAssets: 0,
  totalEquity: 0,
  totalLiabilities: 0,
  currentLiabilities: 0,
  nonCurrentLiabilities: 0,
  cash: 0,
  grossDebt: 0,
  netDebt: 0,
  workingCapital: 0,
  currentRatio: null,
};

function add(amounts: BsAmounts, period: string, value: number): void {
  amounts[period] = (amounts[period] ?? 0) + value;
}

function sumWhere(
  records: BalanceSheetRecord[],
  predicate: (record: BalanceSheetRecord) => boolean,
): number {
  return records.reduce(
    (total, record) => (predicate(record) ? total + record.amount : total),
    0,
  );
}

function kpisForSnapshot(snapshot: BalanceSheetRecord[]): BalanceSheetKpis {
  if (snapshot.length === 0) {
    return { ...EMPTY_KPIS };
  }
  const nonCurrentAssets = sumWhere(snapshot, (r) => r.group === 'non_current_assets');
  const currentAssets = sumWhere(snapshot, (r) => r.group === 'current_assets');
  const totalEquity = sumWhere(snapshot, (r) => r.group === 'equity');
  const currentLiabilities = sumWhere(snapshot, (r) => r.group === 'current_liabilities');
  const nonCurrentLiabilities = sumWhere(
    snapshot,
    (r) => r.group === 'non_current_liabilities',
  );
  const cash = sumWhere(snapshot, (r) => r.is_cash);
  const grossDebt = sumWhere(snapshot, (r) => r.is_debt);
  const totalAssets = nonCurrentAssets + currentAssets;
  const totalLiabilities = currentLiabilities + nonCurrentLiabilities;

  return {
    totalAssets,
    nonCurrentAssets,
    currentAssets,
    totalEquity,
    totalLiabilities,
    currentLiabilities,
    nonCurrentLiabilities,
    cash,
    grossDebt,
    netDebt: grossDebt - cash,
    workingCapital: currentAssets - currentLiabilities,
    currentRatio: currentLiabilities > 0 ? currentAssets / currentLiabilities : null,
  };
}

export function buildBalanceSheet(
  records: BalanceSheetRecord[],
): BalanceSheetStatement {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const periods: BalanceSheetPeriod[] = periodIds.map((id) => ({
    id,
    label: formatPeriodLabel(id),
  }));
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  // --- hierarchical statement (section → group → category), amounts per period.
  const sections: BsSectionRow[] = SECTION_ORDER.map((section) => {
    const sectionRecords = records.filter((r) => r.section === section.id);
    const groupsInSection = GROUP_ORDER.filter((groupId) =>
      sectionRecords.some((r) => r.group === groupId),
    );

    const groups: BsGroupRow[] = groupsInSection.map((groupId) => {
      const groupRecords = sectionRecords.filter((r) => r.group === groupId);
      const groupLabel = groupRecords[0]?.group_label ?? groupId;

      // Preserve first-seen category order within the group.
      const categoryKeys: string[] = [];
      for (const record of groupRecords) {
        if (!categoryKeys.includes(record.category)) {
          categoryKeys.push(record.category);
        }
      }

      const categories: BsCategoryRow[] = categoryKeys.map((category) => {
        const categoryRecords = groupRecords.filter((r) => r.category === category);
        const amounts: BsAmounts = {};
        for (const record of categoryRecords) {
          add(amounts, record.period, record.amount);
        }
        return { key: category, label: category, amounts, records: categoryRecords };
      });

      const amounts: BsAmounts = {};
      for (const record of groupRecords) {
        add(amounts, record.period, record.amount);
      }
      return { key: groupId, label: groupLabel, section: section.id, amounts, categories };
    });

    const amounts: BsAmounts = {};
    for (const record of sectionRecords) {
      add(amounts, record.period, record.amount);
    }
    return { id: section.id, label: section.label, amounts, groups };
  });

  // --- as-of snapshot drives KPIs / composition / balance columns.
  const snapshot = asOf ? records.filter((r) => r.period === asOf) : [];
  const kpis = kpisForSnapshot(snapshot);

  const composition: CompositionSlice[] = snapshot
    .filter((r) => r.section === 'assets')
    .map((r) => ({ key: r.category, label: r.category, value: r.amount }))
    .sort((a, b) => b.value - a.value);

  const assetBars: BalanceBar[] = sections
    .find((s) => s.id === 'assets')
    ?.groups.map((group) => ({
      key: group.key,
      label: group.label,
      value: asOf ? (group.amounts[asOf] ?? 0) : 0,
    })) ?? [];

  const financingBars: BalanceBar[] = sections
    .find((s) => s.id === 'equity_liabilities')
    ?.groups.map((group) => ({
      key: group.key,
      label: group.label,
      value: asOf ? (group.amounts[asOf] ?? 0) : 0,
    })) ?? [];

  // --- trends across every snapshot in the window.
  const workingCapitalTrend: TrendPoint[] = [];
  const debtTrend: DebtTrendPoint[] = [];
  for (const period of periodIds) {
    const periodSnapshot = records.filter((r) => r.period === period);
    const snapshotKpis = kpisForSnapshot(periodSnapshot);
    const label = formatPeriodLabel(period);
    workingCapitalTrend.push({ period, label, value: snapshotKpis.workingCapital });
    debtTrend.push({
      period,
      label,
      grossDebt: snapshotKpis.grossDebt,
      netDebt: snapshotKpis.netDebt,
      cash: snapshotKpis.cash,
    });
  }

  const isBalanced =
    Math.abs(kpis.totalAssets - (kpis.totalEquity + kpis.totalLiabilities)) <
    Math.max(1, kpis.totalAssets * 1e-6);

  return {
    periods,
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    sections,
    kpis,
    composition,
    assetBars,
    financingBars,
    workingCapitalTrend,
    debtTrend,
    isBalanced,
  };
}
