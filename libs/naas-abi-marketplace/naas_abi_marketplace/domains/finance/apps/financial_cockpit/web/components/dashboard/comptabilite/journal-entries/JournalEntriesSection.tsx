'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  buildJournalEntries,
  journalEntryRecords,
} from '@/lib/comptabilite/journalEntries/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const integerFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 0,
});

const daysFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'Every adjustment keyed by hand into the selected period: what it was for, who prepared it, who validated it, and whether it made the close deadline.';

/** Above this share of entries still waiting, validation is the bottleneck. */
const PENDING_WARNING = 0.1;
/** Above this share posted after the deadline, the close is slipping. */
const LATE_WARNING = 0.2;

const ENTRY_COLUMNS: DataTableColumn[] = [
  { key: 'entry_ref', label: 'Entry' },
  { key: 'posted_date', label: 'Posted' },
  { key: 'label', label: 'Label' },
  { key: 'entry_type', label: 'Type' },
  { key: 'debit_account', label: 'Debit' },
  { key: 'credit_account', label: 'Credit' },
  { key: 'preparer', label: 'Prepared by' },
  { key: 'approver', label: 'Validated by' },
  { key: 'status', label: 'Status' },
  {
    key: 'days_late',
    label: 'Late (d)',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  { key: 'amount', label: 'Amount', align: 'right', valueStyle: 'currency' },
];

export function JournalEntriesSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => journalEntryRecords(datasets.journal_entries),
    [datasets.journal_entries],
  );
  const view = useMemo(() => buildJournalEntries(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const entryRows = useMemo(
    () =>
      view.entries.map((entry) => ({
        entry_ref: entry.entry_ref,
        posted_date: entry.posted_date,
        label: entry.label,
        entry_type: entry.entry_type_label,
        debit_account: `${entry.debit_account} — ${entry.debit_account_label}`,
        credit_account: `${entry.credit_account} — ${entry.credit_account_label}`,
        preparer: entry.preparer,
        approver: entry.approver || '—',
        status: entry.status_label,
        days_late: entry.days_late,
        amount: entry.amount,
      })),
    [view.entries],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Journal Entries{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No manual entries for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const pendingShare = kpis.entryCount > 0 ? kpis.pending / kpis.entryCount : 0;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Journal Entries{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {integerFormatter.format(kpis.entryCount)} manual entries from{' '}
          {kpis.preparerCount} preparers · through {view.asOfLabel}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Manual Entries"
          value={kpis.entryCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={
            kpis.manualShare !== null
              ? `${percentFormatter.format(kpis.manualShare)} of the ledger`
              : 'Keyed by hand'
          }
          hint="Entries a human keyed into the ledger over the window. Every other entry arrived from a source system already balanced."
        />
        <KpiCard
          label="Adjustments"
          value={kpis.byType.adjustment ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle="Corrections to posted figures"
          hint="Entries that restate something already booked — a reversal, a release, a correction against the source."
        />
        <KpiCard
          label="Plugs"
          value={kpis.byType.plug ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={(kpis.byType.plug ?? 0) > 0 ? 'warning' : 'success'}
          subtitle="Unexplained balancing entries"
          hint="Entries booked to force a balance rather than to record a transaction. A plug is always a question outstanding, whatever its size."
        />
        <KpiCard
          label="Reclassifications"
          value={kpis.byType.reclassification ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle="Moved between accounts"
          hint="Entries that move an amount from one account to another without changing the result — a cut-off or a mis-coding put right."
        />
        <KpiCard
          label="Pending Validation"
          value={kpis.pending}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.pending === 0
              ? 'success'
              : pendingShare > PENDING_WARNING
                ? 'warning'
                : 'default'
          }
          subtitle={
            kpis.approvalDays !== null
              ? `${daysFormatter.format(kpis.approvalDays)} d to validate on average`
              : 'Awaiting a reviewer'
          }
          hint="Entries posted but not yet signed off by a reviewer. They are already in the ledger — validation is the control, not the gate."
        />
        <KpiCard
          label="Late Entries"
          value={kpis.late}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.lateShare === null
              ? 'default'
              : kpis.lateShare > LATE_WARNING
                ? 'danger'
                : kpis.lateShare > 0
                  ? 'warning'
                  : 'success'
          }
          subtitle={
            kpis.lateShare !== null
              ? `${percentFormatter.format(kpis.lateShare)} past the deadline`
              : 'Past the close deadline'
          }
          hint="Entries keyed more than six days after the period end — past the window the close allows for adjustments, so they landed after the numbers had been read."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Entry Timeline"
          hint="Manual entries keyed each month, and how many of them missed the close deadline."
          labels={view.trend.map((point) => point.label)}
          formatValue={(value) => integerFormatter.format(value)}
          series={[
            {
              name: 'Entries',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.entries),
              fill: true,
            },
            {
              name: 'Late',
              color: 'var(--recovery-orange)',
              values: view.trend.map((point) => point.late),
            },
          ]}
        />
        <CompositionDonut
          title="Approval Status"
          hint="Where the window's entries stand with the reviewer. A locked period has nothing left pending — that is what locking it means."
          totalLabel="Entries"
          formatValue={(value) => integerFormatter.format(value)}
          slices={view.statuses.map((status) => ({
            key: status.key,
            label: status.label,
            value: status.count,
          }))}
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HorizontalBarChart
          title="Entry Type Distribution"
          items={view.types.map((type) => ({
            label: type.label,
            amount: type.amount,
            count: type.count,
          }))}
          visibleCount={5}
          countNoun="entry"
          emptyMessage="No manual entries for this perimeter."
        />
        <HorizontalBarChart
          title="User Activity"
          items={view.preparers.map((preparer) => ({
            label: preparer.label,
            amount: preparer.amount,
            count: preparer.count,
          }))}
          visibleCount={5}
          countNoun="entry"
          emptyMessage="No manual entries for this perimeter."
        />
      </div>

      {/* ---- Entries -------------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every manual entry in the selected period, largest first."
        >
          Journal Entries
        </PageTitle>
      </div>

      <DataTable
        records={entryRows}
        columns={ENTRY_COLUMNS}
        emptyMessage="No manual entries for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search an entry, account or preparer…"
        summaryRow
        exportable
        exportFileName="journal-entries"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Entry counts and amounts aggregate across the selected period. Type totals
        are counted per entry, so an entry belongs to exactly one of Adjustment,
        Plug, Reclassification, Accrual and Provision — the five sum to Manual
        Entries.
      </p>
    </div>
  );
}
