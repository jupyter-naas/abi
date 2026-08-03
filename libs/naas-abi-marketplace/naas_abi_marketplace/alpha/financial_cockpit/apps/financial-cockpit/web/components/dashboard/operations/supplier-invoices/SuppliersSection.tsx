'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  AGING_BUCKETS,
  FORECAST_DAYS,
  buildPayables,
  payableRecords,
} from '@/lib/operations/payables/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { AgingBarChart } from '@/components/dashboard/viz/AgingBarChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { PaymentCalendar } from '@/components/dashboard/operations/supplier-invoices/PaymentCalendar';
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
  'The open supplier book at the latest month end: who is owed what, when it falls due, and how much cash the next few weeks will absorb.';

/** DPO outside this band is worth flagging: too low burns cash, too high burns goodwill. */
const DPO_LOW = 30;
const DPO_HIGH = 65;
/** Overdue above this share of the book is a payment-discipline problem. */
const OVERDUE_WARNING = 0.1;
const OVERDUE_DANGER = 0.2;
/** A single supplier above this share of the book is a concentration risk. */
const CONCENTRATION_WARNING = 0.25;

const LEDGER_COLUMNS: DataTableColumn[] = [
  { key: 'supplier', label: 'Supplier' },
  { key: 'category', label: 'Category' },
  { key: 'country', label: 'Country' },
  { key: 'outstanding', label: 'Outstanding', align: 'right', valueStyle: 'currency' },
  { key: 'current', label: 'Not yet due', align: 'right', valueStyle: 'currency' },
  ...AGING_BUCKETS.slice(1).map((bucket) => ({
    key: `bucket_${bucket.key}`,
    label: bucket.label,
    align: 'right' as const,
    valueStyle: 'currency' as const,
  })),
  {
    key: 'bill_count',
    label: 'Open bills',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  {
    key: 'terms',
    label: 'Terms (d)',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  { key: 'next_due', label: 'Next due' },
  { key: 'share', label: 'Share', align: 'right', valueStyle: 'percent' },
];

export function SuppliersSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => payableRecords(datasets.payables),
    [datasets.payables],
  );
  const view = useMemo(() => buildPayables(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const ledgerRows = useMemo(
    () =>
      view.suppliers.map((supplier) => ({
        supplier: supplier.label,
        category: supplier.category,
        country: supplier.country,
        outstanding: supplier.outstanding,
        current: supplier.current,
        ...Object.fromEntries(
          AGING_BUCKETS.slice(1).map((bucket, index) => [
            `bucket_${bucket.key}`,
            supplier.buckets[index + 1],
          ]),
        ),
        bill_count: supplier.billCount,
        terms: supplier.paymentTerms,
        next_due: supplier.nextDue ?? '—',
        share: supplier.share,
      })),
    [view.suppliers],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Suppliers{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No payables data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const overdueShare = kpis.payables > 0 ? kpis.overdue / kpis.payables : 0;
  const topShare = view.suppliers[0]?.share ?? 0;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Suppliers{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {view.asOfLabel} · {kpis.billCount} open bills across{' '}
          {kpis.supplierCount} suppliers
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Accounts Payable"
          value={kpis.payables}
          valueStyle="currency"
          subtitle={`${kpis.billCount} bills open`}
          hint="Everything owed to suppliers at the latest month end — the balance sheet's Trade payables line, bill by bill."
        />
        <KpiCard
          label="DPO"
          value={kpis.dpo ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={0}
          displayValue={
            kpis.dpo === null ? '—' : `${daysFormatter.format(kpis.dpo)} d`
          }
          tone={
            kpis.dpo === null
              ? 'default'
              : kpis.dpo > DPO_HIGH
                ? 'warning'
                : kpis.dpo < DPO_LOW
                  ? 'orange'
                  : 'success'
          }
          subtitle="Days payable outstanding"
          hint="How long the company takes to pay, on a three-month purchases window. Paying too fast gives up free financing; paying too slowly costs supplier goodwill."
        />
        <KpiCard
          label="Due This Week"
          value={kpis.dueThisWeek}
          valueStyle="currency"
          tone={kpis.dueThisWeek > 0 ? 'orange' : 'success'}
          subtitle="Overdue included"
          hint="Cash needed within seven days of the month end, counting everything already past due as payable now."
        />
        <KpiCard
          label="Overdue Payments"
          value={kpis.overdue}
          valueStyle="currency"
          tone={
            overdueShare >= OVERDUE_DANGER
              ? 'danger'
              : overdueShare >= OVERDUE_WARNING
                ? 'warning'
                : 'success'
          }
          subtitle={`${kpis.overdueCount} bills · ${percentFormatter.format(
            overdueShare,
          )} of the book`}
          hint="Bills already past their due date. Unlike receivables, this one is entirely within the company's control."
        />
        <KpiCard
          label="Payment Forecast"
          value={kpis.paymentForecast}
          valueStyle="currency"
          tone="orange"
          subtitle={`Next ${FORECAST_DAYS} days`}
          hint="Total cash the payables book will absorb over the next month, overdue bills included."
        />
        <KpiCard
          label="Supplier Count"
          value={kpis.supplierCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={topShare >= CONCENTRATION_WARNING ? 'warning' : 'default'}
          subtitle={`Largest holds ${percentFormatter.format(topShare)}`}
          hint="How many suppliers carry an open balance. A book concentrated in one name is a supply risk as much as a payment one."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AgingBarChart
          title="Payable Aging"
          hint="The open book by days past due. Anything right of the first bucket is a bill the company has let slip."
          buckets={view.aging}
          countNoun="bill"
          totalLabel="Payables"
        />
        <PaymentCalendar
          title="Payment Calendar"
          hint="What leaves the bank week by week from the month end. The first column is everything already payable."
          weeks={view.calendar}
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CompositionDonut
          title="Supplier Concentration"
          hint="Share of the open book by supplier — a single dominant name is a negotiating position as much as a risk."
          slices={view.suppliers.slice(0, 8).map((supplier) => ({
            key: supplier.key,
            label: supplier.label,
            value: supplier.outstanding,
          }))}
          totalLabel="Total payables"
          emptyMessage="No open balance for this perimeter."
        />
        <TrendChart
          title="Payment Trend"
          hint="What was purchased against what was paid each month. Paying below purchases stretches the book and lifts DPO."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Purchased',
              color: 'var(--secondary)',
              values: view.trend.map((point) => point.purchased),
            },
            {
              name: 'Paid',
              color: 'var(--recovery-orange)',
              values: view.trend.map((point) => point.paid),
              fill: true,
            },
          ]}
        />
      </div>

      {/* ---- Supplier ledger ---------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every supplier with an open balance, split across the aging buckets."
        >
          Supplier Ledger
        </PageTitle>
      </div>

      <DataTable
        records={ledgerRows}
        columns={LEDGER_COLUMNS}
        emptyMessage="No supplier has an open balance for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search a supplier…"
        summaryRow
        exportable
        exportFileName="supplier-ledger"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Balances are a snapshot at {view.asOfLabel}; purchases, payments and DPO
        accumulate across the selected period. The payment calendar and &ldquo;due this
        week&rdquo; are measured from that same month end — the only &ldquo;today&rdquo;
        a historical snapshot has.
      </p>
    </div>
  );
}
