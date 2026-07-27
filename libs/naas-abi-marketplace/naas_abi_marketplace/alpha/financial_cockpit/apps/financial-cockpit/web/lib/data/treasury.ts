import type { Dataset } from '@/lib/types';
import type { ScenarioOption } from '@/lib/data/scenarios';

export type TreasuryItemType =
  | 'position'
  | 'upcoming_collection'
  | 'upcoming_disbursement'
  | 'credit_notes_to_refund';

export type TreasuryItem = {
  entity_id?: string;
  organization_slug?: string | null;
  company?: string | null;
  type: TreasuryItemType;
  type_label: string;
  label: string;
  categorie_2?: string | null;
  meta?: string | null;
  thirdparty?: string | null;
  bank_account?: string | null;
  date?: string | null;
  deadline?: string | null;
  amount: number;
  scenario?: string;
  scenario_year?: string;
  invoice_id?: string | null;
  invoice_ref?: string | null;
  pennylane_transactions_url?: string | null;
  pennylane_company_id?: number | null;
  /** Bank position file: credits (encaissements) over the period. */
  encaissement?: number | null;
  /** Bank position file: debits (décaissements) over the period. */
  decaissement?: number | null;
};

export type TreasuryDataset = Dataset<TreasuryItem> & {
  scenarios?: ScenarioOption[];
};

export const TYPE_LABELS: Record<TreasuryItemType, string> = {
  position: 'Position',
  upcoming_collection: 'Encaissement à venir',
  upcoming_disbursement: 'Décaissement à venir',
  credit_notes_to_refund: 'Avoir à rembourser',
};

/** Sign applied to each type when building the waterfall / net contribution. */
const TYPE_SIGN: Record<TreasuryItemType, 1 | -1> = {
  position: 1,
  upcoming_collection: 1,
  upcoming_disbursement: -1,
  credit_notes_to_refund: -1,
};

/** Bar colors, aligned with the platform palette. */
export const TYPE_COLOR: Record<TreasuryItemType, string> = {
  position: 'var(--primary)',
  upcoming_collection: 'var(--recovery-success)',
  upcoming_disbursement: 'var(--recovery-danger)',
  credit_notes_to_refund: 'var(--recovery-danger)',
};

export function isTreasuryDataset(
  dataset: Dataset | undefined,
): dataset is TreasuryDataset {
  return !!dataset && Array.isArray((dataset as Dataset).records);
}

export function treasuryItems(dataset: TreasuryDataset | undefined): TreasuryItem[] {
  return (dataset?.records ?? []) as TreasuryItem[];
}

export type TypeTotal = { amount: number; count: number };

export function sumByType(items: TreasuryItem[]): Record<TreasuryItemType, TypeTotal> {
  const totals: Record<TreasuryItemType, TypeTotal> = {
    position: { amount: 0, count: 0 },
    upcoming_collection: { amount: 0, count: 0 },
    upcoming_disbursement: { amount: 0, count: 0 },
    credit_notes_to_refund: { amount: 0, count: 0 },
  };
  for (const item of items) {
    const bucket = totals[item.type];
    if (!bucket) continue;
    bucket.amount += item.amount ?? 0;
    bucket.count += 1;
  }
  return totals;
}

export type BankFlows = { encaissement: number; decaissement: number };

/**
 * Realized bank flows over the period, summed from the position rows
 * (``credits`` = encaissements in, ``debits`` = décaissements out).
 */
export function sumBankFlows(items: TreasuryItem[]): BankFlows {
  const flows: BankFlows = { encaissement: 0, decaissement: 0 };
  for (const item of items) {
    if (item.type !== 'position') continue;
    flows.encaissement += item.encaissement ?? 0;
    flows.decaissement += item.decaissement ?? 0;
  }
  return flows;
}

export type CashBridgeStep = {
  key: string;
  /** Source item type, or undefined for the computed forecast anchor. */
  type?: TreasuryItemType;
  label: string;
  value: number;
  balance: number;
  kind: 'anchor' | 'inflow' | 'outflow';
};

/**
 * actual → forecast waterfall, computed from the line items:
 *   Position  + Encaissements à venir  − Décaissements à venir
 *             − Avoir à rembourser  = Solde Tréso prév.
 */
export function buildCashBridge(items: TreasuryItem[]): CashBridgeStep[] {
  const totals = sumByType(items);
  const position = totals.position.amount;
  const collection = totals.upcoming_collection.amount;
  const disburse = totals.upcoming_disbursement.amount;
  const credit = totals.credit_notes_to_refund.amount;

  const afterCollection = position + collection;
  const afterDisburse = afterCollection - disburse;
  const forecast = afterDisburse - credit;

  return [
    { key: 'position', type: 'position', label: TYPE_LABELS.position, value: position, balance: position, kind: 'anchor' },
    { key: 'upcoming_collection', type: 'upcoming_collection', label: TYPE_LABELS.upcoming_collection, value: collection, balance: afterCollection, kind: 'inflow' },
    { key: 'upcoming_disbursement', type: 'upcoming_disbursement', label: TYPE_LABELS.upcoming_disbursement, value: -disburse, balance: afterDisburse, kind: 'outflow' },
    { key: 'credit_notes_to_refund', type: 'credit_notes_to_refund', label: TYPE_LABELS.credit_notes_to_refund, value: -credit, balance: forecast, kind: 'outflow' },
    { key: 'forecast_position', label: 'Solde Tréso prév.', value: forecast, balance: forecast, kind: 'anchor' },
  ];
}

export type BreakdownDimension = 'bank_account' | 'thirdparty' | 'company';

export type AccountValue = {
  key: string;
  label: string;
  value: number;
};

/**
 * Drill-down for one bridge step: group its line items by a dimension and sum.
 * Position keeps its (signed) amount; flow amounts are magnitudes. Zero groups
 * are dropped. Sorted descending by value (highest first).
 */
export function breakdownForType(
  items: TreasuryItem[],
  type: TreasuryItemType,
  dimension: BreakdownDimension,
): AccountValue[] {
  const totals = new Map<string, number>();
  for (const item of items) {
    if (item.type !== type) continue;
    const raw = item[dimension];
    const label = raw && String(raw).trim() ? String(raw) : '—';
    totals.set(label, (totals.get(label) ?? 0) + (item.amount ?? 0));
  }
  return [...totals.entries()]
    .filter(([, value]) => value !== 0)
    .map(([label, value]) => ({ key: label, label, value }))
    .sort((a, b) => b.value - a.value);
}

/** Sign helper for callers that need the net contribution of a type. */
export function signedTypeTotal(items: TreasuryItem[], type: TreasuryItemType): number {
  return sumByType(items)[type].amount * TYPE_SIGN[type];
}

export type CashProjectionEntry = {
  type: TreasuryItemType;
  typeLabel: string;
  label: string;
  company: string | null;
  thirdparty: string | null;
  /** Raw échéance of the source line (table `deadline` column), if any. */
  deadline: string | null;
  /** Signed: + encaissement, − décaissement / avoir. */
  amount: number;
};

export type CashProjectionPoint = {
  /** ISO ``yyyy-mm-dd`` day. */
  date: string;
  /** Running projected cash balance at end of that day. */
  balance: number;
  /** Encaissements dated that day (positive). */
  inflow: number;
  /** Décaissements + avoirs dated that day (positive magnitude). */
  outflow: number;
  /** Individual movements dated that day (same rows as the detail table). */
  entries: CashProjectionEntry[];
};

function parseISODate(value?: string | null): Date | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function toISODate(day: Date): string {
  const year = day.getFullYear();
  const month = String(day.getMonth() + 1).padStart(2, '0');
  const date = String(day.getDate()).padStart(2, '0');
  return `${year}-${month}-${date}`;
}

/**
 * Daily projected-cash series from ``today`` to the latest échéance.
 *
 * Starts at the current bank position and, on each item's échéance (deadline),
 * applies its signed flow: encaissements add (+), décaissements / avoirs
 * subtract (−). Past-due flows collapse onto ``today``. One point per calendar
 * day so the x-axis covers every date up to the max deadline.
 */
export function buildCashProjection(
  items: TreasuryItem[],
  today: Date = new Date(),
): CashProjectionPoint[] {
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startingBalance = items
    .filter((item) => item.type === 'position')
    .reduce((total, item) => total + (item.amount ?? 0), 0);

  const flowsByDate = new Map<
    string,
    { inflow: number; outflow: number; entries: CashProjectionEntry[] }
  >();
  let maxDate = start;
  for (const item of items) {
    if (item.type === 'position') continue;
    const value = signedAmount(item); // + encaissement, − décaissement / avoir
    if (value === 0) continue;
    const rawDate = parseISODate(item.deadline ?? item.date);
    const when = !rawDate || rawDate < start ? start : rawDate;
    const key = toISODate(when);
    const bucket = flowsByDate.get(key) ?? { inflow: 0, outflow: 0, entries: [] };
    if (value >= 0) {
      bucket.inflow += value;
    } else {
      bucket.outflow += -value;
    }
    bucket.entries.push({
      type: item.type,
      typeLabel: item.type_label,
      label: item.label ?? '—',
      company: item.company ?? null,
      thirdparty: item.thirdparty ?? item.meta ?? null,
      deadline: item.deadline ?? null,
      amount: value,
    });
    flowsByDate.set(key, bucket);
    if (when > maxDate) {
      maxDate = when;
    }
  }

  const points: CashProjectionPoint[] = [];
  let balance = startingBalance;
  const cursor = new Date(start);
  while (cursor <= maxDate) {
    const key = toISODate(cursor);
    const flow = flowsByDate.get(key);
    const inflow = flow?.inflow ?? 0;
    const outflow = flow?.outflow ?? 0;
    balance += inflow - outflow;
    points.push({
      date: key,
      balance: Math.round(balance * 100) / 100,
      inflow,
      outflow,
      entries: flow?.entries ?? [],
    });
    cursor.setDate(cursor.getDate() + 1);
  }
  return points;
}

export type DayFlowsBreakdown = {
  /** That day's encaissements (positive amounts), descending. */
  encaissements: AccountValue[];
  /** That day's décaissements / avoirs (magnitudes), descending. */
  decaissements: AccountValue[];
};

/**
 * Drill-down for one projection day: split its movements into encaissements
 * and décaissements — mirrors the bridge-step drill-down.
 */
export function breakdownForDay(point: CashProjectionPoint): DayFlowsBreakdown {
  const encaissements: AccountValue[] = [];
  const decaissements: AccountValue[] = [];
  point.entries.forEach((entry, index) => {
    const label = entry.thirdparty ? `${entry.label} — ${entry.thirdparty}` : entry.label;
    const target = entry.amount >= 0 ? encaissements : decaissements;
    target.push({ key: `${label}-${index}`, label, value: Math.abs(entry.amount) });
  });
  const byMagnitude = (a: AccountValue, b: AccountValue) => b.value - a.value;
  encaissements.sort(byMagnitude);
  decaissements.sort(byMagnitude);
  return { encaissements, decaissements };
}

/**
 * A line's amount with the direction of its type applied: positive for
 * position / encaissement, negative for décaissement / avoir.
 */
export function signedAmount(item: TreasuryItem): number {
  return item.amount * TYPE_SIGN[item.type];
}
