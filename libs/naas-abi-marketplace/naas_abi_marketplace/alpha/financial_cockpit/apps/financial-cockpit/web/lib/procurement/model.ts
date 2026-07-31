import type { Dataset } from '@/lib/types';

/**
 * Procurement engine. Two record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `order` — one purchase order. A **flow**: aggregate across the window.
 * - `memo` — per-period aggregates: the cost base and the share of it that
 *   goes through a purchase order.
 *
 * An order carries the **date each pipeline milestone is reached**, not a
 * stage. The stage is derived here against the closing month of the window on
 * screen, because it depends on when you look: an order raised in July is in
 * flight on a July window and long since invoiced on a full-year one. Baking a
 * stage into the data would zero out Open Orders and Commitments on every past
 * month.
 */

export type ProcurementRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'order' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  po_ref: string;
  supplier: string;
  category: string;
  category_label: string;
  department: string;
  department_label: string;
  division_label: string;
  requester: string;
  approver: string;
  requested_date: string;
  approved_date: string;
  ordered_date: string;
  received_date: string;
  invoiced_date: string;
  approval_days: number | null;
  stall_days: number;
  amount: number;
  baseline_amount: number;
  savings: number;
  requires_dual_signature: boolean;
};

export type StageKey = 'requested' | 'approved' | 'ordered' | 'received' | 'invoiced';

/** The pipeline, in order. Each stage is reached only after the one before it. */
export const STAGES: { key: StageKey; label: string }[] = [
  { key: 'requested', label: 'Requested' },
  { key: 'approved', label: 'Approved' },
  { key: 'ordered', label: 'Ordered' },
  { key: 'received', label: 'Received' },
  { key: 'invoiced', label: 'Invoiced' },
];

/** An order is open until the goods are in. */
const OPEN_STAGES: StageKey[] = ['requested', 'approved', 'ordered'];
/** Money promised but not yet delivered. */
const COMMITTED_STAGES: StageKey[] = ['approved', 'ordered'];

/** Approval slower than this many days is worth flagging. */
export const APPROVAL_TARGET_DAYS = 5;

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isProcurementDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<ProcurementRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function procurementRecords(dataset: Dataset | undefined): ProcurementRecord[] {
  if (!isProcurementDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'order' || record.kind === 'memo'),
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

/**
 * Furthest stage the order has reached by `asOf`. ISO dates compare correctly
 * as strings, so no parsing is needed; an empty milestone never matches.
 */
export function stageAt(order: ProcurementRecord, asOf: string): StageKey {
  if (order.invoiced_date && order.invoiced_date <= asOf) return 'invoiced';
  if (order.received_date && order.received_date <= asOf) return 'received';
  if (order.ordered_date && order.ordered_date <= asOf) return 'ordered';
  if (order.approved_date && order.approved_date <= asOf) return 'approved';
  return 'requested';
}

export type PurchaseOrder = ProcurementRecord & {
  stage: StageKey;
  stageLabel: string;
  stageIndex: number;
  isOpen: boolean;
  isCommitted: boolean;
  /** Savings as a share of what the order would have cost unnegotiated. */
  savingsRate: number;
};

export type StageSummary = {
  key: StageKey;
  label: string;
  /** Orders sitting at this stage right now. */
  count: number;
  amount: number;
  /** Orders that have reached this stage or gone past it — the funnel. */
  reachedCount: number;
  reachedAmount: number;
  /** Share of all orders that got this far. */
  conversion: number;
};

export type CategorySpend = {
  key: string;
  label: string;
  amount: number;
  count: number;
  savings: number;
  share: number;
};

export type ProcurementTrendPoint = {
  period: string;
  label: string;
  amount: number;
  count: number;
  savings: number;
};

export type ProcurementKpis = {
  /** Orders raised across the window. */
  orderCount: number;
  /** Total value of those orders. */
  spend: number;
  /** Approved but not yet received, at the close of the window. */
  commitments: number;
  commitmentCount: number;
  /** Orders not yet received, at the close of the window. */
  openOrders: number;
  openValue: number;
  savings: number;
  /** Savings against the unnegotiated reference quote. */
  savingsRate: number | null;
  /** Mean days from request to approval, across approved orders. */
  approvalDays: number | null;
  /** Share of PO-covered spend in the month's cost base. */
  costBaseShare: number | null;
  supplierCount: number;
};

export type ProcurementView = {
  asOf: string | null;
  asOfLabel: string;
  kpis: ProcurementKpis;
  stages: StageSummary[];
  categories: CategorySpend[];
  suppliers: CategorySpend[];
  trend: ProcurementTrendPoint[];
  /** Every order in the window, largest first. */
  orders: PurchaseOrder[];
};

const EMPTY_KPIS: ProcurementKpis = {
  orderCount: 0,
  spend: 0,
  commitments: 0,
  commitmentCount: 0,
  openOrders: 0,
  openValue: 0,
  savings: 0,
  savingsRate: null,
  approvalDays: null,
  costBaseShare: null,
  supplierCount: 0,
};

/** Group flows by a key, summing amount / count / savings. */
function groupSpend(
  orders: PurchaseOrder[],
  keyOf: (order: PurchaseOrder) => string,
  labelOf: (order: PurchaseOrder) => string,
  total: number,
): CategorySpend[] {
  const keys: string[] = [];
  for (const order of orders) {
    const key = keyOf(order);
    if (!keys.includes(key)) {
      keys.push(key);
    }
  }
  return keys
    .map((key) => {
      const inGroup = orders.filter((order) => keyOf(order) === key);
      const amount = inGroup.reduce((sum, order) => sum + order.amount, 0);
      return {
        key,
        label: labelOf(inGroup[0]),
        amount,
        count: inGroup.length,
        savings: inGroup.reduce((sum, order) => sum + order.savings, 0),
        share: total > 0 ? amount / total : 0,
      };
    })
    .sort((a, b) => b.amount - a.amount);
}

export function buildProcurement(records: ProcurementRecord[]): ProcurementView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const memoRows = records.filter((record) => record.kind === 'memo');
  const stageLabels = new Map(STAGES.map((stage) => [stage.key, stage.label]));
  const stageOrder = STAGES.map((stage) => stage.key);

  const orders: PurchaseOrder[] = records
    .filter((record) => record.kind === 'order')
    .map((record) => {
      const stage = asOf ? stageAt(record, asOf) : 'requested';
      return {
        ...record,
        stage,
        stageLabel: stageLabels.get(stage) ?? stage,
        stageIndex: stageOrder.indexOf(stage),
        isOpen: OPEN_STAGES.includes(stage),
        isCommitted: COMMITTED_STAGES.includes(stage),
        savingsRate:
          record.baseline_amount > 0 ? record.savings / record.baseline_amount : 0,
      };
    })
    .sort((a, b) => b.amount - a.amount);

  const spend = orders.reduce((sum, order) => sum + order.amount, 0);
  const baseline = orders.reduce((sum, order) => sum + order.baseline_amount, 0);
  const savings = orders.reduce((sum, order) => sum + order.savings, 0);

  // --- pipeline and funnel: where the orders sit, and how many got this far.
  const stages: StageSummary[] = STAGES.map((stage, index) => {
    const atStage = orders.filter((order) => order.stage === stage.key);
    const reached = orders.filter((order) => order.stageIndex >= index);
    return {
      key: stage.key,
      label: stage.label,
      count: atStage.length,
      amount: atStage.reduce((sum, order) => sum + order.amount, 0),
      reachedCount: reached.length,
      reachedAmount: reached.reduce((sum, order) => sum + order.amount, 0),
      conversion: orders.length > 0 ? reached.length / orders.length : 0,
    };
  });

  const categories = groupSpend(
    orders,
    (order) => order.category,
    (order) => order.category_label,
    spend,
  );
  const suppliers = groupSpend(
    orders,
    (order) => order.supplier,
    (order) => order.supplier,
    spend,
  );

  const trend: ProcurementTrendPoint[] = periodIds.map((period) => {
    const inPeriod = orders.filter((order) => order.period === period);
    return {
      period,
      label: formatPeriodLabel(period),
      amount: inPeriod.reduce((sum, order) => sum + order.amount, 0),
      count: inPeriod.length,
      savings: inPeriod.reduce((sum, order) => sum + order.savings, 0),
    };
  });

  const costBase = periodIds.reduce(
    (sum, period) =>
      sum +
      memoRows
        .filter((record) => record.period === period && record.metric === 'cost_base')
        .reduce((total, record) => total + record.amount, 0),
    0,
  );

  // Approval time only counts orders that have actually been approved by the
  // close — averaging in the ones still waiting would understate it.
  const approved = orders.filter(
    (order) => order.stageIndex >= 1 && order.approval_days !== null,
  );
  const open = orders.filter((order) => order.isOpen);
  const committed = orders.filter((order) => order.isCommitted);

  const kpis: ProcurementKpis =
    orders.length === 0
      ? { ...EMPTY_KPIS }
      : {
          orderCount: orders.length,
          spend,
          commitments: committed.reduce((sum, order) => sum + order.amount, 0),
          commitmentCount: committed.length,
          openOrders: open.length,
          openValue: open.reduce((sum, order) => sum + order.amount, 0),
          savings,
          savingsRate: baseline > 0 ? savings / baseline : null,
          approvalDays:
            approved.length > 0
              ? approved.reduce((sum, order) => sum + (order.approval_days ?? 0), 0) /
                approved.length
              : null,
          costBaseShare: costBase > 0 ? spend / costBase : null,
          supplierCount: suppliers.length,
        };

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    kpis,
    stages,
    categories,
    suppliers,
    trend,
    orders,
  };
}
