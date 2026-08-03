'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  APPROVAL_TARGET_DAYS,
  buildProcurement,
  procurementRecords,
} from '@/lib/operations/procurement/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { ApprovalFunnel } from '@/components/dashboard/operations/procurement/ApprovalFunnel';
import { PurchasePipeline } from '@/components/dashboard/operations/procurement/PurchasePipeline';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const daysFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'The purchase-order book for the selected period: what was committed, who approved it and how long that took, and what was negotiated off the reference quote.';

/** Savings below this share of the reference quote is weak negotiating. */
const SAVINGS_TARGET = 0.03;

const ORDER_COLUMNS: DataTableColumn[] = [
  { key: 'po_ref', label: 'PO' },
  { key: 'supplier', label: 'Supplier' },
  { key: 'category', label: 'Category' },
  { key: 'department', label: 'Department' },
  { key: 'requester', label: 'Requested by' },
  { key: 'approver', label: 'Approved by' },
  { key: 'requested_date', label: 'Requested' },
  {
    key: 'approval_days',
    label: 'Approval (d)',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  { key: 'stage', label: 'Stage' },
  { key: 'amount', label: 'Amount', align: 'right', valueStyle: 'currency' },
  { key: 'baseline', label: 'Reference quote', align: 'right', valueStyle: 'currency' },
  { key: 'savings', label: 'Savings', align: 'right', valueStyle: 'currency' },
];

export function ProcurementSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => procurementRecords(datasets.purchase_orders),
    [datasets.purchase_orders],
  );
  const view = useMemo(() => buildProcurement(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const orderRows = useMemo(
    () =>
      view.orders.map((order) => ({
        po_ref: order.po_ref,
        supplier: order.supplier,
        category: order.category_label,
        department: order.department_label,
        requester: order.requester,
        approver: order.stageIndex >= 1 ? order.approver : '—',
        requested_date: order.requested_date,
        approval_days: order.approval_days ?? 0,
        stage: order.stageLabel,
        amount: order.amount,
        baseline: order.baseline_amount,
        savings: order.savings,
      })),
    [view.orders],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Procurement{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No procurement data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Procurement{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {kpis.orderCount} orders across {kpis.supplierCount} suppliers · pipeline as
          of {view.asOfLabel}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Purchase Orders"
          value={kpis.orderCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={`${kpis.supplierCount} suppliers`}
          hint="Orders raised across the selected period, whatever stage they have since reached."
        />
        <KpiCard
          label="Commitments"
          value={kpis.commitments}
          valueStyle="currency"
          tone="orange"
          subtitle={`${kpis.commitmentCount} approved, not received`}
          hint="Money promised but not yet delivered: orders past approval and not yet received at the close of the window. This is spend already locked in, ahead of any invoice."
        />
        <KpiCard
          label="Open Orders"
          value={kpis.openOrders}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={kpis.openOrders > 0 ? 'warning' : 'success'}
          subtitle={`${percentFormatter.format(
            kpis.orderCount > 0 ? kpis.openOrders / kpis.orderCount : 0,
          )} of the book still in flight`}
          hint="Orders not yet received at the close of the window — anything still sitting in approval, or ordered and awaiting delivery."
        />
        <KpiCard
          label="Savings"
          value={kpis.savings}
          valueStyle="currency"
          tone={
            kpis.savingsRate === null
              ? 'default'
              : kpis.savingsRate >= SAVINGS_TARGET
                ? 'success'
                : 'warning'
          }
          subtitle={
            kpis.savingsRate !== null
              ? `${percentFormatter.format(kpis.savingsRate)} off reference`
              : 'Against reference quotes'
          }
          hint="What was negotiated off the reference quote across the orders raised. A savings figure only means something next to the baseline it is measured from."
        />
        <KpiCard
          label="Approval Time"
          value={kpis.approvalDays ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={1}
          displayValue={
            kpis.approvalDays === null
              ? '—'
              : `${daysFormatter.format(kpis.approvalDays)} d`
          }
          tone={
            kpis.approvalDays === null
              ? 'default'
              : kpis.approvalDays > APPROVAL_TARGET_DAYS * 2
                ? 'danger'
                : kpis.approvalDays > APPROVAL_TARGET_DAYS
                  ? 'warning'
                  : 'success'
          }
          subtitle={`Target ${APPROVAL_TARGET_DAYS} d`}
          hint="Mean days from request to approval, across the orders actually approved by the close. Orders above the dual-signature threshold take materially longer."
        />
        <KpiCard
          label="Procurement Spend"
          value={kpis.spend}
          valueStyle="currency"
          subtitle={
            kpis.costBaseShare !== null
              ? `${percentFormatter.format(kpis.costBaseShare)} of the cost base`
              : 'Across the period'
          }
          hint="Total value of the orders raised. The rest of the cost base — payroll, rent and the like — never sees a purchase order."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PurchasePipeline
          title="Purchase Pipeline"
          hint="Where the order book stands right now: each order counted once, at the stage it has reached."
          stages={view.stages}
        />
        <ApprovalFunnel
          title="Approval Funnel"
          hint="How far the orders raised in this period have got. Each band counts everything that cleared that step or went past it."
          stages={view.stages}
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HorizontalBarChart
          title="Spend by Category"
          items={view.categories.map((category) => ({
            label: category.label,
            amount: category.amount,
            count: category.count,
          }))}
          visibleCount={5}
          countNoun="order"
          emptyMessage="No purchase orders for this perimeter."
        />
        <TrendChart
          title="Monthly Purchases"
          hint="Order value raised each month, with the negotiated savings underneath it."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Ordered',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.amount),
              fill: true,
            },
            {
              name: 'Savings',
              color: 'var(--recovery-success)',
              values: view.trend.map((point) => point.savings),
            },
          ]}
        />
      </div>

      {/* ---- Purchase orders ----------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every order raised in the selected period, largest first."
        >
          Purchase Orders
        </PageTitle>
      </div>

      <DataTable
        records={orderRows}
        columns={ORDER_COLUMNS}
        emptyMessage="No purchase orders for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search a PO, supplier or requester…"
        summaryRow
        exportable
        exportFileName="purchase-orders"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Order counts, spend and savings aggregate across the selected period; the
        pipeline, commitments and open orders are read as of {view.asOfLabel}, so the
        same order shows as in flight on its own month and as invoiced on a full year.
      </p>
    </div>
  );
}
