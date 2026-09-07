'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { buildExpenses, expenseRecords } from '@/lib/operations/expenses/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { Treemap } from '@/components/dashboard/viz/Treemap';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'Controllable overhead — the discretionary spend a controller actually steers, as opposed to payroll and cost of sales — by category, department and vendor.';

/** Month-over-month growth past these is worth flagging. */
const GROWTH_WARNING = 0.08;
const GROWTH_DANGER = 0.2;

const DETAIL_COLUMNS: DataTableColumn[] = [
  { key: 'expense_ref', label: 'Reference' },
  { key: 'expense_date', label: 'Date' },
  { key: 'category', label: 'Category' },
  { key: 'department', label: 'Department' },
  { key: 'vendor', label: 'Vendor' },
  { key: 'requester', label: 'Requester' },
  { key: 'method', label: 'Payment method' },
  { key: 'status', label: 'Status' },
  { key: 'receipt', label: 'Receipt' },
  { key: 'amount', label: 'Amount', align: 'right', valueStyle: 'currency' },
];

export function ExpensesSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => expenseRecords(datasets.expenses),
    [datasets.expenses],
  );
  const view = useMemo(() => buildExpenses(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const detailRows = useMemo(
    () =>
      view.lines.map((line) => ({
        expense_ref: line.expense_ref,
        expense_date: line.expense_date,
        category: line.category_label,
        department: line.department_label,
        vendor: line.vendor,
        requester: line.requester,
        method: line.payment_method_label,
        status: line.status_label,
        receipt: line.has_receipt ? 'Attached' : 'Missing',
        amount: line.amount,
      })),
    [view.lines],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Expenses{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No expense data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const [travel, software, marketing] = kpis.headline;
  // A single-month window is better named than counted.
  const spanLabel =
    view.monthCount === 1 ? view.asOfLabel : `${view.monthCount} months`;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Expenses{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {kpis.count} lines · {spanLabel}
          {kpis.costBaseShare !== null
            ? ` · ${percentFormatter.format(kpis.costBaseShare)} of the cost base`
            : ''}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Total Expenses"
          value={kpis.total}
          valueStyle="currency"
          subtitle={`${kpis.count} lines · ${spanLabel}`}
          hint="Controllable overhead across the selected period. Payroll and cost of sales sit outside this page — see Cost Centers for the full cost base."
        />
        <KpiCard
          label="Average Expense"
          value={kpis.averageExpense ?? 0}
          valueStyle="currency"
          subtitle={`${kpis.count} lines`}
          hint="Mean value of an expense line. A falling average with a rising total means more small claims, not bigger ones."
        />
        <KpiCard
          label={travel?.label ?? 'Travel'}
          value={travel?.amount ?? 0}
          valueStyle="currency"
          subtitle={`${percentFormatter.format(travel?.share ?? 0)} of spend`}
          hint="Travel and accommodation — the most seasonal line on the page, and usually the first one cut."
        />
        <KpiCard
          label={software?.label ?? 'Software'}
          value={software?.amount ?? 0}
          valueStyle="currency"
          subtitle={`${percentFormatter.format(software?.share ?? 0)} of spend`}
          hint="Software and subscriptions. Recurring by nature, so growth here is structural rather than one-off."
        />
        <KpiCard
          label={marketing?.label ?? 'Marketing'}
          value={marketing?.amount ?? 0}
          valueStyle="currency"
          subtitle={`${percentFormatter.format(marketing?.share ?? 0)} of spend`}
          hint="Marketing and advertising — discretionary, and the line most often used to hit a margin target."
        />
        <KpiCard
          label="Expense Growth"
          value={kpis.growth ?? 0}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          displayValue={kpis.growth === null ? '—' : undefined}
          tone={
            kpis.growth === null
              ? 'default'
              : kpis.growth >= GROWTH_DANGER
                ? 'danger'
                : kpis.growth >= GROWTH_WARNING
                  ? 'warning'
                  : kpis.growth < 0
                    ? 'success'
                    : 'default'
          }
          subtitle={`${view.asOfLabel} vs prior month`}
          hint="The closing month against the one before it. Positive means overhead grew — read it next to the monthly trend, which shows whether that is a spike or a level shift."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6">
        <Treemap
          title="Expense Treemap"
          hint="Every euro of controllable overhead, nested by division and department. Tile area is spend, so the biggest tile is the biggest cost."
          groups={view.divisions.map((division) => ({
            key: division.key,
            label: division.label,
            value: division.amount,
            leaves: division.departments.map((department) => ({
              key: department.key,
              label: department.label,
              value: department.amount,
            })),
          }))}
          emptyMessage="No expenses for this perimeter."
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Monthly Trend"
          hint="Controllable overhead month by month. The dips are August and the peaks are trade-show season."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Expenses',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.amount),
              fill: true,
            },
          ]}
        />
        <CompositionDonut
          title="Category Breakdown"
          hint="Where the overhead goes. The mix moves more slowly than the total, so a shift here is a change of policy."
          slices={view.categories.map((category) => ({
            key: category.key,
            label: category.label,
            value: category.amount,
          }))}
          totalLabel="Total expenses"
          emptyMessage="No expenses for this perimeter."
        />
      </div>

      <div className="mb-8">
        <HorizontalBarChart
          title="Top Departments"
          items={view.departments.slice(0, 8).map((department) => ({
            label: `${department.label} · ${department.divisionLabel}`,
            amount: department.amount,
            count: department.count,
          }))}
          visibleCount={5}
          countNoun="line"
          emptyMessage="No expenses for this perimeter."
        />
      </div>

      {/* ---- Expense detail ------------------------------------------------ */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every expense line in the selected period, largest first."
        >
          Expense Detail
        </PageTitle>
      </div>

      <DataTable
        records={detailRows}
        columns={DETAIL_COLUMNS}
        emptyMessage="No expense lines for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search a vendor, category or requester…"
        summaryRow
        exportable
        exportFileName="expense-detail"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        {kpis.pendingCount > 0 ? (
          <>
            {kpis.pendingCount} line{kpis.pendingCount === 1 ? '' : 's'} still awaiting
            approval.{' '}
          </>
        ) : null}
        {kpis.missingReceipts > 0 ? (
          <>
            {kpis.missingReceipts} line{kpis.missingReceipts === 1 ? '' : 's'} have no
            receipt attached — the usual policy exception.{' '}
          </>
        ) : null}
        Totals aggregate across the selected period; the growth KPI compares the
        closing month against the one before it.
      </p>
    </div>
  );
}
