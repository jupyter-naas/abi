'use client';

import { Fragment, useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  balanceSheetRecords,
  buildBalanceSheet,
  type BsGroupRow,
  type BsSectionRow,
} from '@/lib/performance/balanceSheet/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { AssetsLiabilitiesChart } from '@/components/dashboard/performance/balance-sheet/AssetsLiabilitiesChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';

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

function formatAmount(value: number): string {
  return currencyFormatter.format(value);
}

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-[var(--text)]';
}

export function BalanceSheetSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => balanceSheetRecords(datasets.balance_sheet),
    [datasets.balance_sheet],
  );
  const statement = useMemo(() => buildBalanceSheet(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const { kpis, periods } = statement;
  const equityRatio =
    kpis.totalAssets > 0 ? kpis.totalEquity / kpis.totalAssets : null;

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint="Financial position at the latest period end: what the company owns and how it is financed.">
            Balance Sheet{perimeterSuffix}
          </PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No balance sheet data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint="Financial position at the latest period end: what the company owns and how it is financed.">
          Balance Sheet{perimeterSuffix}
        </PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {statement.asOfLabel}
          {statement.isBalanced ? ' · Assets = Equity + Liabilities' : ''}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Total Assets"
          value={kpis.totalAssets}
          valueStyle="currency"
          subtitle={`Non-current ${compactCurrency.format(
            kpis.nonCurrentAssets,
          )} · Current ${compactCurrency.format(kpis.currentAssets)}`}
          hint="Everything the company owns at the latest period end."
        />
        <KpiCard
          label="Total Liabilities"
          value={kpis.totalLiabilities}
          valueStyle="currency"
          tone="danger"
          subtitle={`Current ${compactCurrency.format(
            kpis.currentLiabilities,
          )} · Long-term ${compactCurrency.format(kpis.nonCurrentLiabilities)}`}
          hint="All debts and payables owed to third parties (excludes equity)."
        />
        <KpiCard
          label="Equity"
          value={kpis.totalEquity}
          valueStyle="currency"
          tone="success"
          subtitle={
            equityRatio !== null
              ? `${percentFormatter.format(equityRatio)} equity ratio`
              : undefined
          }
          hint="Net worth attributable to shareholders (assets minus liabilities)."
        />
        <KpiCard
          label="Working Capital"
          value={kpis.workingCapital}
          valueStyle="currency"
          tone={kpis.workingCapital >= 0 ? 'success' : 'danger'}
          subtitle="Current assets − current liabilities"
          hint="Short-term liquidity buffer funding day-to-day operations."
        />
        <KpiCard
          label="Net Debt"
          value={kpis.netDebt}
          valueStyle="currency"
          tone={kpis.netDebt > 0 ? 'orange' : 'success'}
          subtitle={`Debt ${compactCurrency.format(
            kpis.grossDebt,
          )} − Cash ${compactCurrency.format(kpis.cash)}`}
          hint="Financial debt net of cash — negative means more cash than debt."
        />
        <KpiCard
          label="Current Ratio"
          value={kpis.currentRatio ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={2}
          tone={
            kpis.currentRatio === null
              ? 'default'
              : kpis.currentRatio >= 1
                ? 'success'
                : 'danger'
          }
          subtitle="Current assets / current liabilities"
          hint="Above 1.0 means current assets cover short-term liabilities."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AssetsLiabilitiesChart
          title="Assets vs Liabilities"
          hint="Both columns are equal by construction — the split shows how assets are financed."
          assets={statement.assetBars}
          financing={statement.financingBars}
        />
        <CompositionDonut
          title="Asset Composition"
          hint="Breakdown of total assets by category at the latest period end."
          slices={statement.composition}
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Working Capital Trend"
          hint="Current assets minus current liabilities at each period end."
          labels={statement.workingCapitalTrend.map((point) => point.label)}
          series={[
            {
              name: 'Working capital',
              color: 'var(--primary)',
              values: statement.workingCapitalTrend.map((point) => point.value),
              fill: true,
            },
          ]}
        />
        <TrendChart
          title="Debt Evolution"
          hint="Gross financial debt and net debt (debt minus cash) over time."
          labels={statement.debtTrend.map((point) => point.label)}
          series={[
            {
              name: 'Gross debt',
              color: 'var(--recovery-orange)',
              values: statement.debtTrend.map((point) => point.grossDebt),
              fill: true,
            },
            {
              name: 'Net debt',
              color: 'var(--secondary)',
              values: statement.debtTrend.map((point) => point.netDebt),
            },
          ]}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle className="mb-4" hint="Full balance sheet by section, group and line — one column per period end.">
          Balance Sheet Detail
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Line
              </th>
              {periods.map((period) => (
                <th
                  key={period.id}
                  className="border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap"
                >
                  {period.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {statement.sections.map((section) => (
              <SectionRows key={section.id} section={section} periodIds={periods.map((p) => p.id)} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GroupBlock({
  group,
  periodIds,
}: {
  group: BsGroupRow;
  periodIds: string[];
}) {
  return (
    <Fragment>
      <tr className="border-b border-[var(--border)]">
        <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 pl-6 text-sm font-medium">
          {group.label}
        </td>
        {periodIds.map((periodId) => {
          const value = group.amounts[periodId] ?? 0;
          return (
            <td
              key={`${group.key}-${periodId}`}
              className={`border-l border-[var(--border)] px-3 py-1.5 text-right font-medium whitespace-nowrap ${amountClassName(value)}`}
            >
              {formatAmount(value)}
            </td>
          );
        })}
      </tr>
      {group.categories.map((category) => (
        <tr key={category.key} className="border-b border-[var(--border)]">
          <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1 pl-12 text-sm text-[var(--text-muted)]">
            {category.label}
          </td>
          {periodIds.map((periodId) => {
            const value = category.amounts[periodId] ?? 0;
            return (
              <td
                key={`${category.key}-${periodId}`}
                className={`border-l border-[var(--border)] px-3 py-1 text-right whitespace-nowrap ${amountClassName(value)}`}
              >
                {formatAmount(value)}
              </td>
            );
          })}
        </tr>
      ))}
    </Fragment>
  );
}

function SectionRows({
  section,
  periodIds,
}: {
  section: BsSectionRow;
  periodIds: string[];
}) {
  const totalLabel = section.id === 'assets' ? 'Total Assets' : 'Total Equity & Liabilities';
  return (
    <Fragment>
      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {section.label}
        </td>
        {periodIds.map((periodId) => (
          <td
            key={`${section.id}-head-${periodId}`}
            className="border-l border-[var(--border)] px-3 py-2"
          />
        ))}
      </tr>
      {section.groups.map((group) => (
        <GroupBlock key={group.key} group={group} periodIds={periodIds} />
      ))}
      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {totalLabel}
        </td>
        {periodIds.map((periodId) => {
          const value = section.amounts[periodId] ?? 0;
          return (
            <td
              key={`${section.id}-total-${periodId}`}
              className={`border-l border-[var(--border)] px-3 py-2 text-right font-semibold whitespace-nowrap ${amountClassName(value)}`}
            >
              {formatAmount(value)}
            </td>
          );
        })}
      </tr>
    </Fragment>
  );
}
