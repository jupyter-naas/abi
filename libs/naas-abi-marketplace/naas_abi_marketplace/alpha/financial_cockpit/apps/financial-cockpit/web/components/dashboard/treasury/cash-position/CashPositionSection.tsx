'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { buildCashPosition, cashAccountRecords } from '@/lib/treasury/cashPosition/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { GeographicDistribution } from '@/components/dashboard/treasury/cash-position/GeographicDistribution';

const currencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'Cash on hand at the latest month end: how much there is, how much of it can actually be spent, and where it sits.';

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-[var(--text)]';
}

function movementClassName(value: number): string {
  if (value > 0) {
    return 'text-emerald-500';
  }
  return value < 0 ? 'text-red-500' : 'text-[var(--text-muted)]';
}

export function CashPositionSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => cashAccountRecords(datasets.bank_accounts),
    [datasets.bank_accounts],
  );
  const view = useMemo(() => buildCashPosition(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Cash Position{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No cash position data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const restrictedShare = kpis.balance > 0 ? kpis.restricted / kpis.balance : 0;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Cash Position{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {view.asOfLabel} · {kpis.accountCount} accounts across{' '}
          {kpis.bankCount} banks
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Cash Balance"
          value={kpis.balance}
          valueStyle="currency"
          subtitle="Total across every account"
          hint="All cash and equivalents held at the latest month end."
        />
        <KpiCard
          label="Available Cash"
          value={kpis.available}
          valueStyle="currency"
          tone="success"
          subtitle={`${percentFormatter.format(
            kpis.balance > 0 ? kpis.available / kpis.balance : 0,
          )} of the balance`}
          hint="Cash that can actually be spent today — the balance net of restricted amounts."
        />
        <KpiCard
          label="Restricted Cash"
          value={kpis.restricted}
          valueStyle="currency"
          tone={restrictedShare > 0.25 ? 'warning' : 'default'}
          subtitle="Escrow, pledged and term-locked"
          hint="Cash held against guarantees, deposits or term commitments — not spendable today."
        />
        <KpiCard
          label="Net Cash"
          value={kpis.netCash}
          valueStyle="currency"
          tone={kpis.netCash >= 0 ? 'success' : 'danger'}
          subtitle={`After ${compactCurrency.format(
            kpis.shortTermDebt,
          )} short-term debt`}
          hint="Cash balance net of short-term borrowings — the true short-term position."
        />
        <KpiCard
          label="Daily Cash Flow"
          value={kpis.dailyCashFlow}
          valueStyle="currency"
          tone={kpis.dailyCashFlow >= 0 ? 'success' : 'danger'}
          subtitle="Average daily movement"
          hint="Net change in the cash balance per day, averaged across the selected period."
        />
        <KpiCard
          label="Bank Accounts"
          value={kpis.accountCount}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={`${kpis.bankCount} banking relationships`}
          hint="Number of accounts carrying a balance at the latest month end."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Cash Trend"
          hint="Total and available cash at each month end — the gap between them is what is locked up."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Total balance',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.balance),
              fill: true,
            },
            {
              name: 'Available',
              color: 'var(--recovery-success)',
              values: view.trend.map((point) => point.available),
            },
          ]}
        />
        <CompositionDonut
          title="Cash Distribution"
          hint="How the balance splits across account types at the latest month end."
          slices={view.byType}
          totalLabel="Total cash"
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HorizontalBarChart
          title="Bank Allocation"
          items={view.byBank.map((bank) => ({
            label: bank.label,
            amount: bank.value,
            count: bank.count,
          }))}
          countNoun="account"
          visibleCount={5}
          emptyMessage="No banks for this perimeter."
        />
        <GeographicDistribution
          title="Geographic Distribution"
          hint="Where the cash is held. Concentration matters — cash in one jurisdiction can be slower to mobilise."
          countries={view.byCountry}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every account at the latest month end, with what is available, what is restricted, and how it moved."
        >
          Bank Accounts
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Account
              </th>
              {[
                'Bank',
                'Type',
                'Country',
                'Currency',
                'Reference',
                'Balance',
                'Restricted',
                'Available',
                'Movement',
              ].map((heading) => (
                <th
                  key={heading}
                  className={`border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap ${
                    ['Balance', 'Restricted', 'Available', 'Movement'].includes(heading)
                      ? 'text-right'
                      : 'text-left'
                  }`}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.accounts.map((account) => (
              <tr key={account.key} className="border-b border-[var(--border)]">
                <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 text-sm font-medium">
                  {account.label}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap">
                  {account.bank}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-[var(--text-muted)]">
                  {account.typeLabel}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-[var(--text-muted)]">
                  {account.countryLabel}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-[var(--text-muted)]">
                  {account.currency}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-xs text-[var(--text-muted)]">
                  {account.reference}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap">
                  {currencyFormatter.format(account.balance)}
                </td>
                <td
                  className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${
                    account.restricted > 0
                      ? 'text-[var(--recovery-orange)]'
                      : 'text-[var(--text-muted)]'
                  }`}
                >
                  {account.restricted > 0
                    ? currencyFormatter.format(account.restricted)
                    : '—'}
                </td>
                <td
                  className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${amountClassName(account.available)}`}
                >
                  {currencyFormatter.format(account.available)}
                </td>
                <td
                  className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${movementClassName(account.movement)}`}
                >
                  {currencyFormatter.format(account.movement)}
                </td>
              </tr>
            ))}

            <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))]">
              <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
                Total
              </td>
              {Array.from({ length: 5 }, (_, index) => (
                <td
                  key={`total-pad-${index}`}
                  className="border-l border-[var(--border)] px-3 py-2"
                />
              ))}
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.balance)}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.restricted)}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.available)}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2" />
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Balances are a snapshot at {view.asOfLabel}, never a sum across months.
        Movement is the change since the previous month end.
      </p>
    </div>
  );
}
