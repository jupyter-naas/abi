'use client';

import { Fragment, useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  buildFinancialRatios,
  financialRatioRecords,
  findRatio,
  formatRatioValue,
  type RatioGroup,
  type RatioSummary,
} from '@/lib/performance/financialRatios/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { BenchmarkChart } from '@/components/dashboard/performance/financial-ratios/BenchmarkChart';
import { RatioRadar } from '@/components/dashboard/performance/financial-ratios/RatioRadar';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'Profitability, returns, leverage and liquidity at the latest period end, each read against its industry benchmark.';

/** KPI cards, in the order the page presents them. */
const KPI_KEYS = [
  'gross_margin',
  'ebitda_margin',
  'roe',
  'roa',
  'debt_ratio',
  'quick_ratio',
] as const;

/** Ratios plotted on the trend chart — percent-based only, so one axis works. */
const TREND_KEYS = ['gross_margin', 'ebitda_margin', 'roe', 'roa'] as const;

const TREND_COLORS = [
  'var(--primary)',
  'var(--secondary)',
  'var(--recovery-success)',
  'var(--recovery-orange)',
];

function toneFor(ratio: RatioSummary): 'success' | 'warning' | 'danger' {
  if (ratio.status !== 'below') {
    return ratio.vsTarget >= 0 ? 'success' : 'warning';
  }
  return 'danger';
}

/**
 * "vs benchmark" caption. The direction word is the *literal* numeric one —
 * for Debt Ratio, sitting below the benchmark is good, and saying "above"
 * because the card is green would misread the number. Goodness is carried by
 * the card tone instead.
 */
function benchmarkSubtitle(ratio: RatioSummary): string {
  const gap = formatRatioValue(Math.abs(ratio.value - ratio.benchmark), ratio.unit);
  const benchmark = formatRatioValue(ratio.benchmark, ratio.unit);
  if (ratio.status === 'on') {
    return `At benchmark (${benchmark})`;
  }
  const direction = ratio.value > ratio.benchmark ? 'above' : 'below';
  return `${gap} ${direction} benchmark (${benchmark})`;
}

export function FinancialRatiosSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => financialRatioRecords(datasets.financial_ratios),
    [datasets.financial_ratios],
  );
  const view = useMemo(() => buildFinancialRatios(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Financial Ratios{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No financial ratio data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const kpiRatios = KPI_KEYS.map((key) => findRatio(view, key)).filter(
    (ratio): ratio is RatioSummary => ratio !== undefined,
  );
  const trendRatios = TREND_KEYS.map((key) => findRatio(view, key)).filter(
    (ratio): ratio is RatioSummary => ratio !== undefined,
  );
  const trendLabels = trendRatios[0]?.trend.map((point) => point.label) ?? [];

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Financial Ratios{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          As of {view.asOfLabel} · {view.aboveBenchmark} of {view.ratios.length} ratios
          at or above benchmark
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {kpiRatios.map((ratio) => (
          <KpiCard
            key={ratio.key}
            label={ratio.label}
            value={ratio.value}
            valueStyle={ratio.unit === 'percent' ? 'percent' : 'decimal'}
            percentInput={ratio.unit === 'percent' ? 'rate' : undefined}
            maximumFractionDigits={ratio.unit === 'percent' ? 1 : 2}
            tone={toneFor(ratio)}
            subtitle={benchmarkSubtitle(ratio)}
            hint={ratio.hint}
          />
        ))}
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6">
        <TrendChart
          title="Ratio Trends"
          hint="Margins and returns over time. Percent-based ratios only, so they share one axis."
          labels={trendLabels}
          series={trendRatios.map((ratio, index) => ({
            name: ratio.label,
            color: TREND_COLORS[index % TREND_COLORS.length],
            values: ratio.trend.map((point) => point.value),
            fill: index === 0,
          }))}
          formatValue={(value) => percentFormatter.format(value)}
          emptyMessage="No ratio history for this perimeter."
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BenchmarkChart
          title="Benchmark Comparison"
          hint="Each ratio against its industry benchmark. Rows are scaled independently — compare the bar to its own marker, not across rows."
          ratios={view.ratios}
        />
        <RatioRadar
          title="Financial Health Radar"
          hint="Every ratio normalized to its benchmark (1,00 x = at benchmark), so mixed units share one shape."
          ratios={view.ratios}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every ratio by family, with its benchmark, internal target and movement over the period."
        >
          Financial Ratios
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Ratio
              </th>
              {['Value', 'Benchmark', 'vs benchmark', 'Target', 'Change', 'Status'].map(
                (heading) => (
                  <th
                    key={heading}
                    className="border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap"
                  >
                    {heading}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {view.groups.map((group) => (
              <GroupRows key={group.key} group={group} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Benchmarks are indicative industry medians. &ldquo;vs benchmark&rdquo; and
        &ldquo;Change&rdquo; are signed so a positive figure is always favourable —
        for Debt Ratio, where lower is better, the sign is inverted accordingly.
      </p>
    </div>
  );
}

/**
 * Phrased as goodness, not numeric direction: "Ahead" means better than the
 * benchmark, which for Debt Ratio means a *lower* value.
 */
const STATUS_LABELS: Record<RatioSummary['status'], string> = {
  above: 'Ahead',
  on: 'At benchmark',
  below: 'Behind',
};

const STATUS_COLORS: Record<RatioSummary['status'], string> = {
  above: 'var(--recovery-success)',
  on: 'var(--text-muted)',
  below: 'var(--recovery-danger)',
};

function signedRatio(value: number, unit: RatioSummary['unit']): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${formatRatioValue(Math.abs(value), unit)}`;
}

function signedClassName(value: number): string {
  if (value > 0) {
    return 'text-emerald-500';
  }
  return value < 0 ? 'text-red-500' : 'text-[var(--text-muted)]';
}

function GroupRows({ group }: { group: RatioGroup }) {
  return (
    <Fragment>
      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {group.label}
        </td>
        {Array.from({ length: 6 }, (_, index) => (
          <td
            key={`${group.key}-head-${index}`}
            className="border-l border-[var(--border)] px-3 py-2"
          />
        ))}
      </tr>
      {group.ratios.map((ratio) => (
        <tr key={ratio.key} className="border-b border-[var(--border)]">
          <td
            className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 pl-6 text-sm"
            title={ratio.hint}
          >
            {ratio.label}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap">
            {formatRatioValue(ratio.value, ratio.unit)}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
            {formatRatioValue(ratio.benchmark, ratio.unit)}
          </td>
          <td
            className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${signedClassName(ratio.vsBenchmark)}`}
          >
            {signedRatio(ratio.vsBenchmark, ratio.unit)}
          </td>
          <td className="border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
            {formatRatioValue(ratio.target, ratio.unit)}
          </td>
          <td
            className={`border-l border-[var(--border)] px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${signedClassName(ratio.change)}`}
          >
            {signedRatio(ratio.change, ratio.unit)}
          </td>
          <td
            className="border-l border-[var(--border)] px-3 py-1.5 text-right text-xs font-semibold whitespace-nowrap"
            style={{ color: STATUS_COLORS[ratio.status] }}
          >
            {STATUS_LABELS[ratio.status]}
          </td>
        </tr>
      ))}
    </Fragment>
  );
}
