import type { Dataset } from '@/lib/types';
import type { ScenarioOption } from '@/lib/data/scenarios';
import type {
  AccountValue,
  CashBridgeStep,
  CashProjectionPoint,
} from '@/lib/data/treasury';
import type { RecoveryBarItem } from '@/lib/data/unpaidClients';

/**
 * Executive dashboard model.
 *
 * The page is a read-only snapshot: every block below is precomputed upstream
 * and rendered with the components the other pages already use — `KpiCard`,
 * `AccountBarChart`, `CashProjectionChart`, `CashBridgeChart`,
 * `HorizontalBarChart` and `DataTable`. That is why the visual blocks reuse the
 * treasury / receivables payload types rather than introducing new shapes.
 */

/** One headline figure plus the reference it is compared against on the card. */
export type DashboardKpi = {
  value: number;
  /** Budget (P&L figures) or prior period (balance-sheet / ratio figures). */
  comparison?: number | null;
};

export type DashboardKpis = {
  revenue: DashboardKpi;
  ebitda: DashboardKpi;
  net_income: DashboardKpi;
  cash: DashboardKpi;
  /** Months of runway at the current burn. */
  cash_runway_months: DashboardKpi;
  working_capital: DashboardKpi;
  /** Days sales outstanding. */
  dso_days: DashboardKpi;
  /** Days payable outstanding. */
  dpo_days: DashboardKpi;
  /** Rate in [0, 1] — rendered as a percentage. */
  forecast_accuracy: DashboardKpi;
};

export type DashboardAnomaly = {
  detected_on: string;
  source: string;
  description: string;
  severity: string;
  amount: number;
};

export type DashboardUpcomingPayment = {
  due_date: string;
  supplier: string;
  description: string;
  category: string;
  amount: number;
};

export type DashboardOverdueInvoice = {
  invoice_ref: string;
  customer: string;
  due_date: string;
  days_overdue: number;
  /** One of the `RecoveryAction` values — coloured like the receivables page. */
  recovery_action_label: string;
  remaining_amount_ttc: number;
};

export type DashboardClosingTask = {
  task: string;
  owner: string;
  due_date: string;
  status: string;
  period: string;
};

export type DashboardDataset = Dataset & {
  scenarios?: ScenarioOption[];
  kpis: DashboardKpis;
  /** Monthly revenue bars. */
  revenue_trend: AccountValue[];
  /** Projected cash balance per point, oldest first. */
  cash_trend: CashProjectionPoint[];
  /** Cash balance the projection starts from. */
  cash_trend_opening: number;
  /** ISO date the opening balance was measured. */
  cash_trend_start_date: string | null;
  /** Revenue → EBITDA → Net income waterfall. */
  waterfall: CashBridgeStep[];
  /** Signed budget variance per P&L line (positive = favourable). */
  budget_variance: AccountValue[];
  top_alerts: RecoveryBarItem[];
  anomalies: DashboardAnomaly[];
  upcoming_payments: DashboardUpcomingPayment[];
  overdue_invoices: DashboardOverdueInvoice[];
  closing_tasks: DashboardClosingTask[];
};

export function isDashboardDataset(
  dataset: Dataset | undefined,
): dataset is DashboardDataset {
  return (
    dataset !== undefined &&
    'kpis' in dataset &&
    'waterfall' in dataset &&
    'revenue_trend' in dataset
  );
}

/**
 * Signed variation between a KPI and its comparison base, **as a percentage**
 * (12.5 → "+12,5 %") because that is what `KpiCard.trend` expects. Null when
 * there is nothing to compare against.
 */
export function kpiTrend(kpi: DashboardKpi): number | null {
  const base = kpi.comparison;
  if (base === null || base === undefined || base === 0) {
    return null;
  }
  return ((kpi.value - base) / Math.abs(base)) * 100;
}
