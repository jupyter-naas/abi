'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  buildScenarioAnalysis,
  formatDriverValue,
  scenarioAnalysisRecords,
} from '@/lib/pilotage/scenarioAnalysis/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { WaterfallChart } from '@/components/dashboard/viz/WaterfallChart';
import { HeatmapGrid } from '@/components/dashboard/viz/HeatmapGrid';
import { ScenarioComparison } from '@/components/dashboard/pilotage/scenario-analysis/ScenarioComparison';
import { TornadoChart } from '@/components/dashboard/pilotage/scenario-analysis/TornadoChart';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const currencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const signedPercent = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
});

const PAGE_HINT =
  'How the year changes when the assumptions behind it move: named cases, the drivers that matter most, and the range they span.';

/** Risk score bands, in points out of 100. */
const RISK_WARNING = 15;
const RISK_DANGER = 30;

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-emerald-500';
}

export function ScenarioAnalysisSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => scenarioAnalysisRecords(datasets.scenario_analysis),
    [datasets.scenario_analysis],
  );
  const view = useMemo(() => buildScenarioAnalysis(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0 || !view.base) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Scenario Analysis{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No scenario data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis, base, sensitivity } = view;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Scenario Analysis{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {view.asOfLabel} · {view.cases.length} cases · base revenue{' '}
          {compactCurrency.format(base.revenue)}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Revenue Impact"
          value={kpis.revenueImpact}
          valueStyle="currency"
          tone={kpis.revenueImpact >= 0 ? 'success' : 'danger'}
          subtitle="Probability-weighted vs base"
          hint="Expected revenue across every case, weighted by probability, minus the base case."
        />
        <KpiCard
          label="EBITDA Impact"
          value={kpis.ebitdaImpact}
          valueStyle="currency"
          tone={kpis.ebitdaImpact >= 0 ? 'success' : 'danger'}
          subtitle="Probability-weighted vs base"
          hint="Same weighting applied to EBITDA — the number most exposed to the drivers."
        />
        <KpiCard
          label="Cash Impact"
          value={kpis.cashImpact}
          valueStyle="currency"
          tone={kpis.cashImpact >= 0 ? 'success' : 'danger'}
          subtitle="Probability-weighted vs base"
          hint="Expected year-end cash versus the base case, damped for partial conversion."
        />
        <KpiCard
          label="Margin Impact"
          value={kpis.marginImpact}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone={kpis.marginImpact >= 0 ? 'success' : 'danger'}
          subtitle="Percentage points vs base"
          hint="Expected EBITDA margin versus the base case."
        />
        <KpiCard
          label="Break-even"
          value={kpis.breakEven}
          valueStyle="currency"
          subtitle={`${percentFormatter.format(
            base.revenue > 0 ? kpis.breakEven / base.revenue : 0,
          )} of base revenue`}
          hint="Revenue needed to cover the current cost base — the point where EBITDA reaches zero."
        />
        <KpiCard
          label="Risk Score"
          value={kpis.riskScore}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.riskScore >= RISK_DANGER
              ? 'danger'
              : kpis.riskScore >= RISK_WARNING
                ? 'warning'
                : 'success'
          }
          subtitle="0 = no downside, 100 = severe"
          hint="Probability-weighted severity of the cases that land below base EBITDA."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ScenarioComparison
          title="Scenario Comparison"
          hint="Revenue and EBITDA under each case, best to worst. The outlined column is the base case."
          cases={view.cases}
        />
        <TornadoChart
          title="Tornado Chart"
          hint="How far EBITDA moves when each driver alone swings to its bounds — widest bar is the driver that matters most."
          drivers={view.drivers}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {sensitivity ? (
          <HeatmapGrid
            title="Sensitivity Matrix"
            hint="EBITDA at every combination of the two most material drivers."
            rowLabels={sensitivity.rowValues.map((value) =>
              formatDriverValue(value, sensitivity.rowUnit),
            )}
            colLabels={sensitivity.colValues.map((value) =>
              formatDriverValue(value, sensitivity.colUnit),
            )}
            cells={sensitivity.cells}
            formatValue={(value) => compactCurrency.format(value)}
            scale="diverging"
            goodDirection="positive"
            rowAxisLabel={sensitivity.rowLabel}
            colAxisLabel={sensitivity.colLabel}
          />
        ) : (
          <div className="glass rounded-lg p-6">
            <h3 className="type-title-5 mb-4">Sensitivity Matrix</h3>
            <p className="text-sm text-[var(--text-muted)]">
              No sensitivity grid for this perimeter.
            </p>
          </div>
        )}
        <WaterfallChart
          title="Waterfall"
          hint="Base EBITDA with every driver moved to its adverse bound at once — the compounding worst case."
          steps={view.waterfall}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="The assumption behind every driver under each case — the inputs that produce the numbers above."
        >
          Scenario Assumptions
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Driver
              </th>
              {view.scenarioColumns.map((column) => (
                <th
                  key={column.key}
                  className="border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.assumptions.map((row) => (
              <tr key={row.key} className="border-b border-[var(--border)]">
                <td
                  className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 text-sm"
                  title={row.hint}
                >
                  {row.label}
                </td>
                {view.scenarioColumns.map((column) => {
                  const value = row.values[column.key];
                  const isBase = column.key === base.key;
                  return (
                    <td
                      key={`${row.key}-${column.key}`}
                      className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${
                        isBase ? 'font-medium' : 'text-[var(--text-muted)]'
                      }`}
                    >
                      {value !== undefined ? formatDriverValue(value, row.unit) : '—'}
                    </td>
                  );
                })}
              </tr>
            ))}

            {/* Outcome rows tie the assumptions back to what they produce. */}
            <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]">
              <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
                Resulting outcome
              </td>
              {view.scenarioColumns.map((column) => (
                <td
                  key={`outcome-head-${column.key}`}
                  className="border-l border-[var(--border)] px-3 py-2"
                />
              ))}
            </tr>
            {(
              [
                ['Revenue', (key: string) => view.cases.find((c) => c.key === key)?.revenue],
                ['EBITDA', (key: string) => view.cases.find((c) => c.key === key)?.ebitda],
                ['Year-end cash', (key: string) => view.cases.find((c) => c.key === key)?.cash],
              ] as const
            ).map(([label, pick]) => (
              <tr key={label} className="border-b border-[var(--border)]">
                <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 pl-6 text-sm text-[var(--text-muted)]">
                  {label}
                </td>
                {view.scenarioColumns.map((column) => {
                  const value = pick(column.key) ?? 0;
                  return (
                    <td
                      key={`${label}-${column.key}`}
                      className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap"
                    >
                      {currencyFormatter.format(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="border-b border-[var(--border)]">
              <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 pl-6 text-sm text-[var(--text-muted)]">
                EBITDA vs base
              </td>
              {view.scenarioColumns.map((column) => {
                const entry = view.cases.find((c) => c.key === column.key);
                const delta = entry?.ebitdaDelta ?? 0;
                return (
                  <td
                    key={`delta-${column.key}`}
                    className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${
                      delta === 0 ? 'text-[var(--text-muted)]' : amountClassName(delta)
                    }`}
                  >
                    {delta === 0
                      ? '—'
                      : base.ebitda !== 0
                        ? signedPercent.format(delta / Math.abs(base.ebitda))
                        : compactCurrency.format(delta)}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        The base case is the current forecast carried through unchanged, so it matches
        the Forecast page. Impacts are probability-weighted across every case; the
        waterfall instead compounds all drivers at their adverse bound, which is
        deliberately more severe than any single case.
      </p>
    </div>
  );
}
