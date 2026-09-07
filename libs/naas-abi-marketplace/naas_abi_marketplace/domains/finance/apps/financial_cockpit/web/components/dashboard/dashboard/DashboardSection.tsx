'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  isDashboardDataset,
  kpiTrend,
  type DashboardDataset,
  type DashboardKpi,
} from '@/lib/data/dashboard';
import { recoveryToneForLabel, type RecoveryTone } from '@/lib/data/unpaidClients';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { AccountBarChart } from '@/components/dashboard/viz/AccountBarChart';
import { CashProjectionChart } from '@/components/dashboard/viz/CashProjectionChart';
import { CashBridgeChart } from '@/components/dashboard/viz/CashBridgeChart';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const RECOVERY_TONE_TEXT_CLASS: Record<RecoveryTone, string> = {
  success: 'text-[var(--recovery-success)]',
  warning: 'text-[var(--recovery-warning)]',
  orange: 'text-[var(--recovery-orange)]',
  danger: 'text-[var(--recovery-danger)]',
};

/** Same colour vocabulary as the receivables page. */
function renderRecoveryLabel(value: unknown) {
  const label = String(value);
  const tone = recoveryToneForLabel(label);
  return (
    <span
      className={`block truncate ${tone ? `font-medium ${RECOVERY_TONE_TEXT_CLASS[tone]}` : ''}`}
    >
      {label}
    </span>
  );
}

const SEVERITY_TONE: Record<string, RecoveryTone> = {
  High: 'danger',
  Medium: 'orange',
  Low: 'warning',
};

const STATUS_TONE: Record<string, RecoveryTone> = {
  'Past due': 'danger',
  'In progress': 'warning',
  Done: 'success',
};

function toneRenderer(tones: Record<string, RecoveryTone>) {
  return function renderToned(value: unknown) {
    const label = String(value);
    const tone = tones[label];
    return (
      <span
        className={`block truncate ${tone ? `font-medium ${RECOVERY_TONE_TEXT_CLASS[tone]}` : ''}`}
      >
        {label}
      </span>
    );
  };
}

const ANOMALY_COLUMNS: DataTableColumn[] = [
  { key: 'detected_on', label: 'Detected on' },
  { key: 'source', label: 'Source' },
  { key: 'description', label: 'Description' },
  { key: 'severity', label: 'Severity', renderValue: toneRenderer(SEVERITY_TONE) },
  {
    key: 'amount',
    label: 'Amount',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
];

const UPCOMING_PAYMENT_COLUMNS: DataTableColumn[] = [
  { key: 'due_date', label: 'Due date' },
  { key: 'supplier', label: 'Supplier' },
  { key: 'description', label: 'Description' },
  { key: 'category', label: 'Category' },
  {
    key: 'amount',
    label: 'Amount',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
];

const OVERDUE_INVOICE_COLUMNS: DataTableColumn[] = [
  { key: 'invoice_ref', label: 'Invoice no.' },
  { key: 'customer', label: 'Customer' },
  { key: 'due_date', label: 'Due date' },
  {
    key: 'days_overdue',
    label: 'Days overdue',
    align: 'right' as const,
    valueStyle: 'decimal' as const,
    maximumFractionDigits: 0,
  },
  {
    key: 'recovery_action_label',
    label: 'Collection status',
    renderValue: renderRecoveryLabel,
  },
  {
    key: 'remaining_amount_ttc',
    label: 'Outstanding incl. tax',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
];

const CLOSING_TASK_COLUMNS: DataTableColumn[] = [
  { key: 'task', label: 'Task' },
  { key: 'owner', label: 'Owner' },
  { key: 'due_date', label: 'Due date' },
  { key: 'status', label: 'Status', renderValue: toneRenderer(STATUS_TONE) },
  { key: 'period', label: 'Period' },
];

const currencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});

/** "Budget: 3 080 000 €" — the reference the card's trend is measured against. */
function budgetSubtitle(kpi: DashboardKpi): string | undefined {
  if (kpi.comparison === null || kpi.comparison === undefined) {
    return undefined;
  }
  return `Budget: ${currencyFormatter.format(kpi.comparison)}`;
}

function priorSubtitle(kpi: DashboardKpi, format: (value: number) => string) {
  if (kpi.comparison === null || kpi.comparison === undefined) {
    return undefined;
  }
  return `Prior period: ${format(kpi.comparison)}`;
}

function trendOrUndefined(kpi: DashboardKpi): number | undefined {
  return kpiTrend(kpi) ?? undefined;
}

export function DashboardSection({ entity, site, company, datasets }: SectionProps) {
  const dataset = datasets.overview;
  const data: DashboardDataset | null = isDashboardDataset(dataset) ? dataset : null;

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const anomalyRecords = useMemo(
    () => (data?.anomalies ?? []) as unknown as Record<string, unknown>[],
    [data],
  );
  const paymentRecords = useMemo(
    () => (data?.upcoming_payments ?? []) as unknown as Record<string, unknown>[],
    [data],
  );
  const overdueRecords = useMemo(
    () => (data?.overdue_invoices ?? []) as unknown as Record<string, unknown>[],
    [data],
  );
  const closingRecords = useMemo(
    () => (data?.closing_tasks ?? []) as unknown as Record<string, unknown>[],
    [data],
  );

  if (!data) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint="Company-level snapshot: headline KPIs, trends and the items that need attention today.">
            Dashboard{perimeterSuffix}
          </PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No dashboard data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = data;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={`Company-level snapshot: headline KPIs, trends and the items that need attention today — ${formatEntityName(entity.display_name)}`}>
          Dashboard{perimeterSuffix}
        </PageTitle>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Revenue"
          value={kpis.revenue.value}
          valueStyle="currency"
          tone="success"
          trend={trendOrUndefined(kpis.revenue)}
          subtitle={budgetSubtitle(kpis.revenue)}
          hint="Revenue booked year to date, compared with budget."
        />
        <KpiCard
          label="EBITDA"
          value={kpis.ebitda.value}
          valueStyle="currency"
          trend={trendOrUndefined(kpis.ebitda)}
          subtitle={budgetSubtitle(kpis.ebitda)}
          hint="Earnings before interest, tax, depreciation and amortisation."
        />
        <KpiCard
          label="Net Income"
          value={kpis.net_income.value}
          valueStyle="currency"
          trend={trendOrUndefined(kpis.net_income)}
          subtitle={budgetSubtitle(kpis.net_income)}
          hint="Bottom line after depreciation, financial result and tax."
        />
        <KpiCard
          label="Cash"
          value={kpis.cash.value}
          valueStyle="currency"
          trend={trendOrUndefined(kpis.cash)}
          subtitle={priorSubtitle(kpis.cash, (value) => currencyFormatter.format(value))}
          hint="Consolidated bank position at the extraction date."
        />
        <KpiCard
          label="Cash Runway"
          value={kpis.cash_runway_months.value}
          valueStyle="decimal"
          maximumFractionDigits={1}
          trend={trendOrUndefined(kpis.cash_runway_months)}
          subtitle={priorSubtitle(
            kpis.cash_runway_months,
            (value) => `${value.toFixed(1)} months`,
          )}
          hint="Months of cash left at the current net burn."
        />
        <KpiCard
          label="Working Capital"
          value={kpis.working_capital.value}
          valueStyle="currency"
          trend={trendOrUndefined(kpis.working_capital)}
          subtitle={priorSubtitle(kpis.working_capital, (value) =>
            currencyFormatter.format(value),
          )}
          hint="Current assets minus current liabilities."
        />
        <KpiCard
          label="DSO"
          value={kpis.dso_days.value}
          valueStyle="decimal"
          maximumFractionDigits={1}
          tone="warning"
          trend={trendOrUndefined(kpis.dso_days)}
          subtitle={priorSubtitle(kpis.dso_days, (value) => `${value.toFixed(1)} days`)}
          hint="Days sales outstanding — average time to collect a customer invoice."
        />
        <KpiCard
          label="DPO"
          value={kpis.dpo_days.value}
          valueStyle="decimal"
          maximumFractionDigits={1}
          trend={trendOrUndefined(kpis.dpo_days)}
          subtitle={priorSubtitle(kpis.dpo_days, (value) => `${value.toFixed(1)} days`)}
          hint="Days payable outstanding — average time taken to pay a supplier."
        />
        <KpiCard
          label="Current Forecast Accuracy"
          value={kpis.forecast_accuracy.value}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone="success"
          trend={trendOrUndefined(kpis.forecast_accuracy)}
          subtitle={priorSubtitle(
            kpis.forecast_accuracy,
            (value) => `${(value * 100).toFixed(1)} %`,
          )}
          hint="How close the latest forecast landed to the actuals."
        />
      </div>

      {/* ---- Visuals ------------------------------------------------------ */}
      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AccountBarChart
          title="Revenue trend"
          hint="Revenue booked per month over the current scenario."
          items={data.revenue_trend}
          visibleCount={7}
          emptyMessage="No revenue booked for this perimeter."
        />
        <AccountBarChart
          title="Budget vs Actual variance"
          hint="Actual minus budget per P&L line — bars to the right are favourable."
          items={data.budget_variance}
          variant="diverging"
          visibleCount={7}
          emptyMessage="No budget variance for this perimeter."
        />
      </div>

      <div className="mb-8">
        <PageTitle className="mb-4" hint="Projected cash balance at each upcoming month end.">
          Cash trend
        </PageTitle>
        {data.cash_trend.length > 1 ? (
          <CashProjectionChart
            points={data.cash_trend}
            initialPosition={data.cash_trend_opening}
            positionDate={data.cash_trend_start_date}
          />
        ) : (
          <div className="glass rounded-lg p-6">
            <p className="text-sm text-[var(--text-muted)]">
              No cash trend for this perimeter.
            </p>
          </div>
        )}
      </div>

      <div className="mb-8">
        <PageTitle className="mb-4" hint="How revenue converts into EBITDA and then into net income.">
          Revenue → EBITDA → Net income
        </PageTitle>
        {data.waterfall.length > 0 ? (
          <CashBridgeChart steps={data.waterfall} />
        ) : (
          <div className="glass rounded-lg p-6">
            <p className="text-sm text-[var(--text-muted)]">
              No income statement for this perimeter.
            </p>
          </div>
        )}
      </div>

      <div className="mb-8">
        <HorizontalBarChart
          title="Top alerts"
          items={data.top_alerts}
          visibleCount={5}
          countNoun="item"
          emptyMessage="No alert for this perimeter."
        />
      </div>

      {/* ---- Tables ------------------------------------------------------- */}
      <div className="mb-8">
        <PageTitle className="mb-6" hint="Unusual movements flagged on the latest data refresh.">
          Latest anomalies
        </PageTitle>
        <DataTable
          records={anomalyRecords}
          columns={ANOMALY_COLUMNS}
          defaultPageSize={5}
          exportFileName="dashboard-anomalies"
          emptyMessage="No anomaly detected for this perimeter."
        />
      </div>

      <div className="mb-8">
        <PageTitle className="mb-6" hint="Supplier invoices and payroll falling due next.">
          Upcoming payments
        </PageTitle>
        <DataTable
          records={paymentRecords}
          columns={UPCOMING_PAYMENT_COLUMNS}
          defaultPageSize={5}
          summaryRow
          exportFileName="dashboard-upcoming-payments"
          emptyMessage="No upcoming payment for this perimeter."
        />
      </div>

      <div className="mb-8">
        <PageTitle className="mb-6" hint="Customer invoices past their due date, with the collection step reached.">
          Overdue invoices
        </PageTitle>
        <DataTable
          records={overdueRecords}
          columns={OVERDUE_INVOICE_COLUMNS}
          defaultPageSize={5}
          summaryRow
          exportFileName="dashboard-overdue-invoices"
          emptyMessage="No overdue invoice for this perimeter."
        />
      </div>

      <div className="mb-8">
        <PageTitle className="mb-6" hint="Month-end close checklist and where each task stands.">
          Closing tasks
        </PageTitle>
        <DataTable
          records={closingRecords}
          columns={CLOSING_TASK_COLUMNS}
          defaultPageSize={5}
          exportFileName="dashboard-closing-tasks"
          emptyMessage="No closing task for this perimeter."
        />
      </div>
    </div>
  );
}
