'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  AGING_BUCKETS,
  AT_RISK_DAYS,
  buildReceivables,
  receivableRecords,
} from '@/lib/operations/receivables/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { AgingBarChart } from '@/components/dashboard/viz/AgingBarChart';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const daysFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'The open customer book at the latest month end: who owes what, how far past due it is, and how quickly the money is actually coming in.';

/** DSO above these thresholds is worth flagging, in days. */
const DSO_WARNING = 55;
const DSO_DANGER = 70;
/** Overdue above this share of the book is a collections problem. */
const OVERDUE_WARNING = 0.25;
const OVERDUE_DANGER = 0.4;
/** A collection rate below this is not keeping up with billing. */
const COLLECTION_TARGET = 0.97;

const LEDGER_COLUMNS: DataTableColumn[] = [
  { key: 'customer', label: 'Customer' },
  { key: 'segment', label: 'Segment' },
  { key: 'country', label: 'Country' },
  {
    key: 'outstanding',
    label: 'Outstanding',
    align: 'right',
    valueStyle: 'currency',
  },
  { key: 'current', label: 'Not yet due', align: 'right', valueStyle: 'currency' },
  ...AGING_BUCKETS.slice(1).map((bucket) => ({
    key: `bucket_${bucket.key}`,
    label: bucket.label,
    align: 'right' as const,
    valueStyle: 'currency' as const,
  })),
  {
    key: 'invoice_count',
    label: 'Open invoices',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  {
    key: 'average_days_late',
    label: 'Avg days late',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  {
    key: 'oldest_days_overdue',
    label: 'Oldest',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  { key: 'share', label: 'Share', align: 'right', valueStyle: 'percent' },
];

export function CustomersSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => receivableRecords(datasets.receivables),
    [datasets.receivables],
  );
  const view = useMemo(() => buildReceivables(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const ledgerRows = useMemo(
    () =>
      view.debtors.map((debtor) => ({
        customer: debtor.label,
        segment: debtor.segment,
        country: debtor.country,
        outstanding: debtor.outstanding,
        current: debtor.current,
        ...Object.fromEntries(
          AGING_BUCKETS.slice(1).map((bucket, index) => [
            `bucket_${bucket.key}`,
            debtor.buckets[index + 1],
          ]),
        ),
        invoice_count: debtor.invoiceCount,
        average_days_late: debtor.averageDaysLate ?? 0,
        oldest_days_overdue: debtor.oldestDaysOverdue ?? 0,
        share: debtor.share,
      })),
    [view.debtors],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Customers{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No receivables data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const overdueShare = kpis.overdueShare ?? 0;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Customers{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {view.asOfLabel} · {kpis.invoiceCount} open invoices across{' '}
          {kpis.customerCount} customers
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Accounts Receivable"
          value={kpis.receivables}
          valueStyle="currency"
          subtitle={`${kpis.invoiceCount} invoices open`}
          hint="Everything customers still owe at the latest month end — the balance sheet's Trade receivables line, invoice by invoice."
        />
        <KpiCard
          label="DSO"
          value={kpis.dso ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={0}
          displayValue={
            kpis.dso === null ? '—' : `${daysFormatter.format(kpis.dso)} d`
          }
          tone={
            kpis.dso === null
              ? 'default'
              : kpis.dso >= DSO_DANGER
                ? 'danger'
                : kpis.dso >= DSO_WARNING
                  ? 'warning'
                  : 'success'
          }
          subtitle="Days sales outstanding"
          hint="How many days of billing are sitting unpaid, measured on a three-month revenue window so seasonality does not distort it."
        />
        <KpiCard
          label="Overdue Amount"
          value={kpis.overdue}
          valueStyle="currency"
          tone={
            overdueShare >= OVERDUE_DANGER
              ? 'danger'
              : overdueShare >= OVERDUE_WARNING
                ? 'warning'
                : 'success'
          }
          subtitle={`${percentFormatter.format(overdueShare)} of the book`}
          hint="Open balance already past its due date — the part of the book that needs chasing."
        />
        <KpiCard
          label="Collection Rate"
          value={kpis.collectionRate ?? 0}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone={
            kpis.collectionRate === null
              ? 'default'
              : kpis.collectionRate >= COLLECTION_TARGET
                ? 'success'
                : 'warning'
          }
          subtitle={
            kpis.collectionEffectiveness !== null
              ? `CEI ${percentFormatter.format(kpis.collectionEffectiveness)}`
              : 'Collected over invoiced'
          }
          hint="Cash collected over the period against what was billed in it. Below 100% means the book is growing faster than it is being cleared. CEI measures the same collections against everything that could have been collected."
        />
        <KpiCard
          label="Overdue Invoices"
          value={kpis.overdueInvoices}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={kpis.overdueInvoices > 0 ? 'orange' : 'success'}
          subtitle={`of ${kpis.invoiceCount} open`}
          hint="How many separate invoices are past due — the workload behind the overdue amount."
        />
        <KpiCard
          label="Average Days Late"
          value={kpis.averageDaysLate ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={0}
          displayValue={
            kpis.averageDaysLate === null
              ? '—'
              : `${daysFormatter.format(kpis.averageDaysLate)} d`
          }
          tone={
            kpis.averageDaysLate === null
              ? 'default'
              : kpis.averageDaysLate >= 45
                ? 'danger'
                : kpis.averageDaysLate >= 20
                  ? 'warning'
                  : 'success'
          }
          subtitle={`${percentFormatter.format(
            kpis.receivables > 0 ? kpis.atRisk / kpis.receivables : 0,
          )} over ${AT_RISK_DAYS} days`}
          hint="Balance-weighted days past due across the overdue invoices, so a large late invoice counts for more than a small one."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AgingBarChart
          title="Aging Buckets"
          hint="The open book by days past due. A healthy ledger is heavily weighted to the leftmost bucket."
          buckets={view.aging}
          countNoun="invoice"
          totalLabel="Receivables"
        />
        <TrendChart
          title="DSO Trend"
          hint="Days sales outstanding month by month — the direction of travel matters more than the level."
          labels={view.trend.map((point) => point.label)}
          formatValue={(value) => `${daysFormatter.format(value)} d`}
          series={[
            {
              name: 'DSO',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.dso),
              fill: true,
            },
          ]}
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HorizontalBarChart
          title="Top Debtors"
          items={view.debtors.slice(0, 8).map((debtor) => ({
            label: debtor.label,
            amount: debtor.outstanding,
            count: debtor.invoiceCount,
          }))}
          visibleCount={5}
          countNoun="open invoice"
          emptyMessage="No open balance for this perimeter."
        />
        <TrendChart
          title="Collections Trend"
          hint="What was billed against what was banked each month. Collections trailing invoicing is what pushes DSO up."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Invoiced',
              color: 'var(--secondary)',
              values: view.trend.map((point) => point.invoiced),
            },
            {
              name: 'Collected',
              color: 'var(--recovery-success)',
              values: view.trend.map((point) => point.collected),
              fill: true,
            },
          ]}
        />
      </div>

      {/* ---- Customer ledger ---------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every customer with an open balance, split across the aging buckets."
        >
          Customer Ledger
        </PageTitle>
      </div>

      <DataTable
        records={ledgerRows}
        columns={LEDGER_COLUMNS}
        emptyMessage="No customer has an open balance for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search a customer…"
        summaryRow
        exportable
        exportFileName="customer-ledger"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Balances are a snapshot at {view.asOfLabel}; invoiced, collected and the
        collection rate accumulate across the selected period. Avg days late is
        weighted by outstanding amount and counts overdue invoices only, so a customer
        paying everything on time shows zero.
      </p>
    </div>
  );
}
