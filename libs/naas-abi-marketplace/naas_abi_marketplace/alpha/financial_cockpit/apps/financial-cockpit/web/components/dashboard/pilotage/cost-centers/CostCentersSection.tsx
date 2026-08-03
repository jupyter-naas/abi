'use client';

import { Fragment, useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  buildCostCenters,
  costCenterRecords,
  type DivisionSummary,
} from '@/lib/pilotage/costCenters/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { HeatmapGrid } from '@/components/dashboard/viz/HeatmapGrid';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { Treemap } from '@/components/dashboard/pilotage/cost-centers/Treemap';
import { DepartmentRanking } from '@/components/dashboard/pilotage/cost-centers/DepartmentRanking';

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

const signedPercent = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
});

const integerFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 0,
});

const PAGE_HINT =
  'What each department spends against its budget, what it costs per head, and what it contributes back in revenue and margin.';

/** Overspend beyond this share of budget reads as a problem, not noise. */
const OVERSPEND_THRESHOLD = 0.05;

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-[var(--text)]';
}

/** Overspend is bad, underspend is good — the inverse of most metrics here. */
function varianceClassName(value: number): string {
  if (value > 0) {
    return 'text-red-500';
  }
  return value < 0 ? 'text-emerald-500' : 'text-[var(--text-muted)]';
}

export function CostCentersSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => costCenterRecords(datasets.cost_centers),
    [datasets.cost_centers],
  );
  const view = useMemo(() => buildCostCenters(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Cost Centers{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No cost center data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;
  const overspending = view.centers.filter(
    (center) => center.variancePct !== null && center.variancePct > OVERSPEND_THRESHOLD,
  ).length;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Cost Centers{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {view.centers.length} cost centers across {view.divisions.length} divisions ·{' '}
          {overspending} over budget by more than 5%
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Budget"
          value={kpis.budget}
          valueStyle="currency"
          subtitle="Approved plan for the period"
          hint="Total budgeted spend across every cost center in the selected period."
        />
        <KpiCard
          label="Actual Spend"
          value={kpis.actual}
          valueStyle="currency"
          subtitle={`${integerFormatter.format(kpis.headcount)} employees`}
          hint="Total spend actually incurred across every cost center."
        />
        <KpiCard
          label="Variance"
          value={kpis.variance}
          valueStyle="currency"
          tone={kpis.variance > 0 ? 'danger' : 'success'}
          subtitle={
            kpis.variancePct !== null
              ? `${signedPercent.format(kpis.variancePct)} vs budget`
              : undefined
          }
          hint="Actual minus budget. A positive figure is an overspend."
        />
        <KpiCard
          label="Cost per Employee"
          value={kpis.costPerEmployee ?? 0}
          valueStyle="currency"
          subtitle="Actual spend / headcount"
          hint="Average cost carried per employee across the whole organisation."
        />
        <KpiCard
          label="Revenue Contribution"
          value={kpis.revenueContribution}
          valueStyle="currency"
          tone="success"
          subtitle="From revenue-generating centers"
          hint="Revenue attributed to the cost centers that generate it. Support functions contribute none."
        />
        <KpiCard
          label="Margin Contribution"
          value={kpis.marginContribution}
          valueStyle="currency"
          tone={kpis.marginContribution >= 0 ? 'success' : 'danger'}
          subtitle="Contribution net of spend"
          hint="What each center's revenue contributes after covering its own cost — negative for support functions by construction."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Treemap
          title="Treemap"
          hint="Every cost center sized by spend and coloured by division — the largest tile is the largest cost."
          divisions={view.divisions}
        />
        <DepartmentRanking
          title="Department Ranking"
          hint="Cost centers ordered by spend, each against its own budget marker."
          centers={view.ranking}
        />
      </div>

      <div className="mb-6">
        {view.heatmap ? (
          <HeatmapGrid
            title="Heatmap"
            hint="Budget variance per cost center per month. Red is an overspend, green an underspend."
            rowLabels={view.heatmap.rowLabels}
            colLabels={view.heatmap.colLabels}
            cells={view.heatmap.cells}
            formatValue={(value) => signedPercent.format(value)}
            scale="diverging"
            goodDirection="negative"
            rowAxisLabel="Cost center"
            colAxisLabel="Month"
          />
        ) : null}
      </div>

      <div className="mb-8">
        <TrendChart
          title="Monthly Trend"
          hint="Company-wide budget against actual spend, month by month."
          labels={view.monthly.map((point) => point.label)}
          series={[
            {
              name: 'Actual',
              color: 'var(--primary)',
              values: view.monthly.map((point) => point.actual),
              fill: true,
            },
            {
              name: 'Budget',
              color: 'var(--secondary)',
              values: view.monthly.map((point) => point.budget),
            },
          ]}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every cost center by division, with its budget, spend, variance, headcount and contribution."
        >
          Cost Center Detail
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Cost center
              </th>
              {[
                'Budget',
                'Actual',
                'Variance',
                'Var %',
                'Headcount',
                'Cost / employee',
                'Revenue contrib.',
                'Margin contrib.',
              ].map((heading) => (
                <th
                  key={heading}
                  className="border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.divisions.map((division) => (
              <DivisionRows key={division.key} division={division} />
            ))}

            <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))]">
              <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
                Total
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.budget)}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.actual)}
              </td>
              <td
                className={`border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap ${varianceClassName(kpis.variance)}`}
              >
                {currencyFormatter.format(kpis.variance)}
              </td>
              <td
                className={`border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap ${varianceClassName(kpis.variance)}`}
              >
                {kpis.variancePct !== null ? signedPercent.format(kpis.variancePct) : '—'}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {integerFormatter.format(kpis.headcount)}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {kpis.costPerEmployee !== null
                  ? currencyFormatter.format(kpis.costPerEmployee)
                  : '—'}
              </td>
              <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
                {currencyFormatter.format(kpis.revenueContribution)}
              </td>
              <td
                className={`border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap ${amountClassName(kpis.marginContribution)}`}
              >
                {currencyFormatter.format(kpis.marginContribution)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Variance is actual minus budget, so a positive figure is an overspend and shows
        red. Headcount is the level at the end of the period, never a sum across months.
      </p>
    </div>
  );
}

function DivisionRows({ division }: { division: DivisionSummary }) {
  return (
    <Fragment>
      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {division.label}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap">
          {compactCurrency.format(division.budget)}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap">
          {compactCurrency.format(division.actual)}
        </td>
        <td
          className={`border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap ${varianceClassName(division.variance)}`}
        >
          {compactCurrency.format(division.variance)}
        </td>
        {Array.from({ length: 5 }, (_, index) => (
          <td
            key={`${division.key}-head-${index}`}
            className="border-l border-[var(--border)] px-3 py-2"
          />
        ))}
      </tr>

      {division.centers.map((center) => (
        <tr key={center.key} className="border-b border-[var(--border)]">
          <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 pl-6 text-sm">
            {center.label}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
            {currencyFormatter.format(center.budget)}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap">
            {currencyFormatter.format(center.actual)}
          </td>
          <td
            className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${varianceClassName(center.variance)}`}
          >
            {currencyFormatter.format(center.variance)}
          </td>
          <td
            className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${varianceClassName(center.variance)}`}
          >
            {center.variancePct !== null ? signedPercent.format(center.variancePct) : '—'}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap">
            {integerFormatter.format(center.headcount)}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap">
            {center.costPerEmployee !== null
              ? currencyFormatter.format(center.costPerEmployee)
              : '—'}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
            {center.revenueContribution > 0
              ? currencyFormatter.format(center.revenueContribution)
              : '—'}
          </td>
          <td
            className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${amountClassName(center.marginContribution)}`}
          >
            {currencyFormatter.format(center.marginContribution)}
          </td>
        </tr>
      ))}
    </Fragment>
  );
}
