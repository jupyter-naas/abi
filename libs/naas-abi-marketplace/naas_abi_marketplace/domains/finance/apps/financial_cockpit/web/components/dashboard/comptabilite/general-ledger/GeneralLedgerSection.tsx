'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { buildGeneralLedger, ledgerRecords } from '@/lib/comptabilite/generalLedger/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { AccountBarChart } from '@/components/dashboard/viz/AccountBarChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { EntryVolumeChart } from '@/components/dashboard/comptabilite/general-ledger/EntryVolumeChart';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const integerFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'The double-entry record behind the selected period: every posting line, the journal it came from, the account it hit, and whether a human keyed it or a source system did.';

const LINE_COLUMNS: DataTableColumn[] = [
  { key: 'entry_date', label: 'Date' },
  { key: 'entry_ref', label: 'Entry' },
  { key: 'journal', label: 'Journal' },
  { key: 'account', label: 'Account' },
  { key: 'account_label', label: 'Account name' },
  { key: 'label', label: 'Label' },
  { key: 'third_party', label: 'Third party' },
  { key: 'debit', label: 'Debit', align: 'right', valueStyle: 'currency' },
  { key: 'credit', label: 'Credit', align: 'right', valueStyle: 'currency' },
  { key: 'source', label: 'Source' },
  { key: 'user', label: 'Posted by' },
];

export function GeneralLedgerSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => ledgerRecords(datasets.general_ledger),
    [datasets.general_ledger],
  );
  const view = useMemo(() => buildGeneralLedger(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const lineRows = useMemo(
    () =>
      view.lines.map((line) => ({
        entry_date: line.entry_date,
        entry_ref: line.entry_ref,
        journal: `${line.journal_code} — ${line.journal_label}`,
        account: line.account,
        account_label: line.account_label,
        label: line.label,
        third_party: line.third_party || '—',
        debit: line.debit,
        credit: line.credit,
        source: line.source === 'manual' ? 'Manual' : 'Imported',
        user: line.user,
      })),
    [view.lines],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>General Ledger{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No ledger data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>General Ledger{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {integerFormatter.format(kpis.entryCount)} entries across{' '}
          {view.journals.length} journals · ledger through {view.asOfLabel}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Journal Entries"
          value={kpis.entryCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={`Across ${kpis.periodCount} period${kpis.periodCount > 1 ? 's' : ''}`}
          hint="Balanced entries posted in the selected period. One entry may carry several lines — a sales invoice hits the customer, the revenue account and VAT."
        />
        <KpiCard
          label="Accounts"
          value={kpis.accountCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle="Movement on the chart of accounts"
          hint="Accounts that actually moved in the window. The chart of accounts is larger — this counts the ones carrying a posting."
        />
        <KpiCard
          label="Transactions"
          value={kpis.lineCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={`${integerFormatter.format(
            kpis.entryCount > 0 ? Math.round((kpis.lineCount / kpis.entryCount) * 10) / 10 : 0,
          )} lines per entry`}
          hint="Posting lines — the individual debits and credits. This is what the ledger table below lists."
        />
        <KpiCard
          label="Open Periods"
          value={kpis.openPeriods}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={kpis.openPeriods > 0 ? 'warning' : 'success'}
          subtitle={`${kpis.periodCount - kpis.openPeriods} locked`}
          hint="Months in the window whose books are not yet locked, so entries can still be posted to them. A locked period is final."
        />
        <KpiCard
          label="Manual Entries"
          value={kpis.manualEntries}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.manualShare !== null && kpis.manualShare > 0.15 ? 'warning' : 'default'
          }
          subtitle={
            kpis.manualShare !== null
              ? `${percentFormatter.format(kpis.manualShare)} of all entries`
              : 'Keyed by hand'
          }
          hint="Entries a human keyed rather than a source system fed. They are where judgement — and error — enters the ledger, which is why the Journal Entries page tracks them one by one."
        />
        <KpiCard
          label="Imported Entries"
          value={kpis.importedEntries}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle="From the source systems"
          hint="Entries fed in from billing, purchasing, payroll and the bank. They arrive already balanced and are not re-keyed."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EntryVolumeChart
          title="Entry Volume"
          hint="Entries posted each month, split between what the source systems fed in and what was keyed by hand."
          points={view.trend}
        />
        <AccountBarChart
          title="Activity by Account"
          hint="Total movement on each account — debits plus credits — so a busy clearing account shows up even when it nets to nothing."
          items={view.accounts.slice(0, 12).map((account) => ({
            key: account.key,
            label: account.label,
            value: account.amount,
          }))}
          visibleCount={5}
          color="var(--primary)"
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Monthly Trend"
          hint="Debits and credits posted each month. They track each other exactly — that is what a balanced ledger looks like."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Debit',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.debit),
              fill: true,
            },
            {
              name: 'Credit',
              color: 'var(--secondary)',
              values: view.trend.map((point) => point.credit),
            },
          ]}
        />
        <CompositionDonut
          title="Journal Distribution"
          hint="Value posted through each journal. Sales and purchases carry the volume; the miscellaneous journal is small but it is where the judgement calls live."
          totalLabel="Posted"
          slices={view.journals.map((journal) => ({
            key: journal.key,
            label: `${journal.code} — ${journal.label}`,
            value: journal.amount,
          }))}
        />
      </div>

      {/* ---- Ledger lines --------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every posting line in the selected period, most recent first."
        >
          General Ledger
        </PageTitle>
      </div>

      <DataTable
        records={lineRows}
        columns={LINE_COLUMNS}
        emptyMessage="No ledger lines for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search an entry, account or third party…"
        summaryRow
        exportable
        exportFileName="general-ledger"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Debits and credits both total{' '}
        {new Intl.NumberFormat('fr-FR', {
          style: 'currency',
          currency: 'EUR',
          maximumFractionDigits: 0,
        }).format(kpis.debit)}{' '}
        across the window
        {kpis.imbalance === 0
          ? ' — the ledger balances.'
          : `, a difference of ${kpis.imbalance.toFixed(2)} €.`}{' '}
        Filtering the table narrows the rows shown, not the balance stated here.
      </p>
    </div>
  );
}
