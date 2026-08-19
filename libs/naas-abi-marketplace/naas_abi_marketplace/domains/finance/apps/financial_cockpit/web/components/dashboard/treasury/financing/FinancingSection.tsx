'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { buildFinancing, loanRecords } from '@/lib/treasury/financing/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { DebtMaturityTimeline } from '@/components/dashboard/treasury/financing/DebtMaturityTimeline';

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

const rateFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'The debt book at the latest month end: who lent what, on what terms, when it falls due and what it costs to carry.';

/** Debt above this share of assets is worth flagging. */
const LEVERAGE_WARNING = 0.4;
const LEVERAGE_DANGER = 0.6;
/** A maturity inside this many years is a near-term refinancing question. */
const NEAR_MATURITY_YEARS = 1;

export function FinancingSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(() => loanRecords(datasets.loans), [datasets.loans]);
  const view = useMemo(() => buildFinancing(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Financing{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No financing data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const live = view.loans.filter((loan) => loan.outstanding > 0);
  const floatingShare =
    kpis.outstanding > 0
      ? live
          .filter((loan) => loan.isFloating)
          .reduce((sum, loan) => sum + loan.outstanding, 0) / kpis.outstanding
      : 0;
  const nextMaturityYears = live.find(
    (loan) => loan.maturity === kpis.nextMaturity,
  )?.yearsToMaturity;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Financing{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {view.asOfLabel} · {kpis.loanCount} facilities ·{' '}
          {percentFormatter.format(floatingShare)} floating rate
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Outstanding Debt"
          value={kpis.outstanding}
          valueStyle="currency"
          subtitle={`Across ${kpis.loanCount} facilities`}
          hint="Total principal still owed at the latest month end."
        />
        <KpiCard
          label="Interest Expense"
          value={kpis.interestExpense}
          valueStyle="currency"
          tone="orange"
          subtitle="Charged over the period"
          hint="Interest accrued across the selected period — a flow, not a balance."
        />
        <KpiCard
          label="Average Interest Rate"
          value={kpis.averageRate ?? 0}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={2}
          subtitle="Balance-weighted"
          hint="Weighted by outstanding balance, so the largest facilities dominate."
        />
        <KpiCard
          label="Next Maturity"
          value={kpis.nextMaturityAmount}
          valueStyle="currency"
          tone={
            nextMaturityYears !== null &&
            nextMaturityYears !== undefined &&
            nextMaturityYears < NEAR_MATURITY_YEARS
              ? 'warning'
              : 'default'
          }
          subtitle={
            kpis.nextMaturity ? `Due ${kpis.nextMaturityLabel}` : 'No maturity scheduled'
          }
          hint="The soonest facility to fall due, and how much has to be repaid or refinanced."
        />
        <KpiCard
          label="Debt Service"
          value={kpis.debtService}
          valueStyle="currency"
          tone="orange"
          subtitle="Repayments plus interest"
          hint="Total cash absorbed by the debt book across the period."
        />
        <KpiCard
          label="Debt Ratio"
          value={kpis.debtRatio ?? 0}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone={
            kpis.debtRatio === null
              ? 'default'
              : kpis.debtRatio >= LEVERAGE_DANGER
                ? 'danger'
                : kpis.debtRatio >= LEVERAGE_WARNING
                  ? 'warning'
                  : 'success'
          }
          subtitle="Debt / total assets"
          hint="Financial debt measured against the asset base it funds."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6">
        <DebtMaturityTimeline
          title="Debt Maturity Timeline"
          hint="Each facility from origination to maturity, with the repayment wall by year underneath."
          loans={view.loans}
          maturities={view.maturities}
          start={view.timelineStart}
          end={view.timelineEnd}
          asOf={view.asOf}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CompositionDonut
          title="Debt by Lender"
          hint="Concentration across lenders — a single dominant lender is a refinancing risk of its own."
          slices={view.byLender}
          totalLabel="Total debt"
          emptyMessage="No outstanding debt for this perimeter."
        />
        <TrendChart
          title="Interest Trend"
          hint="Interest charged each month, and the balance-weighted average rate behind it."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Interest',
              color: 'var(--recovery-orange)',
              values: view.trend.map((point) => point.interest),
              fill: true,
            },
          ]}
        />
      </div>

      <div className="mb-8">
        <TrendChart
          title="Debt Evolution"
          hint="Long-term and short-term borrowings over time — the shape of the deleveraging."
          labels={view.trend.map((point) => point.label)}
          series={[
            {
              name: 'Total debt',
              color: 'var(--primary)',
              values: view.trend.map((point) => point.total),
              fill: true,
            },
            {
              name: 'Long-term',
              color: 'var(--secondary)',
              values: view.trend.map((point) => point.longTerm),
            },
            {
              name: 'Short-term',
              color: 'var(--recovery-orange)',
              values: view.trend.map((point) => point.shortTerm),
            },
          ]}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every facility with its lender, terms, cost and covenant."
        >
          Loans
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Facility
              </th>
              {[
                'Lender',
                'Instrument',
                'Outstanding',
                'Rate',
                'Interest',
                'Repaid',
                'Origination',
                'Maturity',
                'Covenant',
              ].map((heading) => (
                <th
                  key={heading}
                  className={`border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap ${
                    ['Outstanding', 'Rate', 'Interest', 'Repaid'].includes(heading)
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
            {view.loans.map((loan) => (
              <tr
                key={loan.key}
                className={`border-b border-[var(--border)]${
                  loan.outstanding === 0 ? ' opacity-60' : ''
                }`}
              >
                <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 text-sm font-medium">
                  {loan.label}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap">
                  {loan.lender}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-[var(--text-muted)]">
                  {loan.instrumentLabel}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap">
                  {loan.outstanding > 0
                    ? currencyFormatter.format(loan.outstanding)
                    : 'Repaid'}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap">
                  {rateFormatter.format(loan.rate)}
                  {loan.isFloating ? (
                    <span
                      className="ml-1 text-[10px] text-[var(--recovery-orange)]"
                      title={
                        loan.referenceRate !== null
                          ? `Floating over ${rateFormatter.format(loan.referenceRate)} reference`
                          : 'Floating rate'
                      }
                    >
                      FL
                    </span>
                  ) : null}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
                  {compactCurrency.format(loan.interest)}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
                  {loan.repayment > 0 ? compactCurrency.format(loan.repayment) : '—'}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-[var(--text-muted)]">
                  {loan.origination}
                </td>
                <td className="border-l border-[var(--border)] px-3 py-1.5 whitespace-nowrap">
                  {loan.maturity}
                </td>
                <td
                  className="border-l border-[var(--border)] px-3 py-1.5 max-w-[14rem] truncate text-xs text-[var(--text-muted)]"
                  title={loan.covenant}
                >
                  {loan.covenant}
                </td>
              </tr>
            ))}

            <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))]">
              <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
                Total
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2" />
              <td className="border-l border-[var(--border)] px-3 py-2" />
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.outstanding)}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {kpis.averageRate !== null ? rateFormatter.format(kpis.averageRate) : '—'}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {compactCurrency.format(kpis.interestExpense)}
              </td>
              {Array.from({ length: 4 }, (_, index) => (
                <td
                  key={`total-pad-${index}`}
                  className="border-l border-[var(--border)] px-3 py-2"
                />
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Outstanding balances and rates are a snapshot at {view.asOfLabel}; interest and
        repayments accumulate across the selected period. Facilities marked{' '}
        <span className="text-[var(--recovery-orange)]">FL</span> reprice with the
        reference rate, so their cost moves with the market.
      </p>
    </div>
  );
}
