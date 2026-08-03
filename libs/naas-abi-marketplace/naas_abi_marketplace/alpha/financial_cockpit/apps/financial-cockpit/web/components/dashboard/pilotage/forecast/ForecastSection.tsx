'use client';

import { Fragment, useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  buildForecast,
  forecastRecords,
  type ForecastMetric,
} from '@/lib/pilotage/forecast/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { WaterfallChart } from '@/components/dashboard/viz/WaterfallChart';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { ActualVsForecastChart } from '@/components/dashboard/pilotage/forecast/ActualVsForecastChart';
import { ConfidenceRangeChart } from '@/components/dashboard/pilotage/forecast/ConfidenceRangeChart';

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

const signedPercent = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
});

const PAGE_HINT =
  'Where the year lands: actuals for the months already closed, forecast for the rest, both read against the budget.';

/** Forecast accuracy at or above this reads as reliable. */
const GOOD_ACCURACY = 0.9;

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-[var(--text)]';
}

/** Currency metrics format as EUR; the margin metric formats as a rate. */
function formatMetric(value: number, metric: ForecastMetric): string {
  return metric.unit === 'percent'
    ? percentFormatter.format(value)
    : currencyFormatter.format(value);
}

export function ForecastSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => forecastRecords(datasets.forecast),
    [datasets.forecast],
  );
  const view = useMemo(() => buildForecast(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Forecast{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No forecast data for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Forecast{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {kpis.actualMonths} month{kpis.actualMonths === 1 ? '' : 's'} closed ·{' '}
          {kpis.forecastMonths} forecast
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Forecast Revenue"
          value={kpis.revenue}
          valueStyle="currency"
          subtitle={`Budget ${compactCurrency.format(
            view.metrics.find((m) => m.key === 'revenue')?.budgetTotal ?? 0,
          )}`}
          hint="Full-year revenue: actuals for closed months plus forecast for the rest."
        />
        <KpiCard
          label="Forecast EBITDA"
          value={kpis.ebitda}
          valueStyle="currency"
          tone={kpis.ebitda >= 0 ? 'success' : 'danger'}
          subtitle={`Budget ${compactCurrency.format(
            view.metrics.find((m) => m.key === 'ebitda')?.budgetTotal ?? 0,
          )}`}
          hint="Full-year EBITDA on the same actual-plus-forecast basis."
        />
        <KpiCard
          label="Forecast Cash"
          value={kpis.cash}
          valueStyle="currency"
          tone={kpis.cash >= 0 ? 'success' : 'danger'}
          subtitle="Closing balance at year end"
          hint="Cash expected at the end of the period — a closing level, not a sum."
        />
        <KpiCard
          label="Forecast Margin"
          value={kpis.margin}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone={kpis.margin >= 0.15 ? 'success' : kpis.margin >= 0 ? 'warning' : 'danger'}
          subtitle="Forecast EBITDA / forecast revenue"
          hint="Full-year EBITDA margin implied by the forecast."
        />
        <KpiCard
          label="Forecast Accuracy"
          value={kpis.accuracy ?? 0}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone={
            kpis.accuracy === null
              ? 'default'
              : kpis.accuracy >= GOOD_ACCURACY
                ? 'success'
                : 'warning'
          }
          subtitle="On revenue, months already closed"
          hint="One minus the mean absolute percentage error between what was forecast and what happened."
        />
        <KpiCard
          label="Forecast Variance"
          value={kpis.variance ?? 0}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={1}
          tone={
            kpis.variance === null
              ? 'default'
              : kpis.variance >= 0
                ? 'success'
                : 'danger'
          }
          subtitle="Forecast revenue vs budget"
          hint="How far the full-year revenue forecast sits above or below the budget."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ActualVsForecastChart
          title="Actual vs Forecast"
          hint="Revenue by month — solid where the month is closed, lighter where it is still a forecast."
          points={view.actualVsForecast}
        />
        <ConfidenceRangeChart
          title="Confidence Range"
          hint="Expected EBITDA inside its low–high band. The band widens the further out the forecast reaches."
          points={view.confidence}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Rolling Forecast"
          hint="Trailing twelve-month expected revenue at each month end — the run-rate view of where the year is heading."
          labels={view.rollingForecast.map((point) => point.label)}
          series={[
            {
              name: 'Rolling 12M revenue',
              color: 'var(--primary)',
              values: view.rollingForecast.map((point) => point.value),
              fill: true,
            },
          ]}
        />
        <WaterfallChart
          title="Forecast Waterfall"
          hint="Budget EBITDA bridged to forecast EBITDA: how much comes from selling more, and how much from a different margin."
          steps={view.waterfall}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="Every metric month by month, with the budget it was measured against and the confidence range around the forecast."
        >
          Forecast Details
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Month
              </th>
              {['Actual', 'Forecast', 'Budget', 'vs budget', 'Range'].map((heading) => (
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
            {view.metrics.map((metric) => (
              <MetricRows key={metric.key} metric={metric} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Months without an Actual are still open — their Forecast is the expected
        outcome. Cash is a closing balance, so its total is the year-end level rather
        than a sum; margin is averaged across the months.
      </p>
    </div>
  );
}

function MetricRows({ metric }: { metric: ForecastMetric }) {
  const totalLabel = metric.isStock
    ? 'Closing'
    : metric.unit === 'percent'
      ? 'Average'
      : 'Full year';

  return (
    <Fragment>
      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {metric.label}
        </td>
        {Array.from({ length: 5 }, (_, index) => (
          <td
            key={`${metric.key}-head-${index}`}
            className="border-l border-[var(--border)] px-3 py-2"
          />
        ))}
      </tr>

      {metric.points.map((point) => {
        const vsBudget = point.expected - point.budget;
        return (
          <tr key={`${metric.key}-${point.period}`} className="border-b border-[var(--border)]">
            <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1 pl-6 text-sm text-[var(--text-muted)]">
              {point.label}
              {point.isActual ? '' : ' ·'}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap">
              {point.actual !== null ? formatMetric(point.actual, metric) : '—'}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap">
              {formatMetric(point.forecast, metric)}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
              {formatMetric(point.budget, metric)}
            </td>
            <td
              className={`border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap ${amountClassName(vsBudget)}`}
            >
              {point.budget !== 0
                ? signedPercent.format(vsBudget / Math.abs(point.budget))
                : '—'}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right text-xs tabular-nums whitespace-nowrap text-[var(--text-muted)]">
              {formatMetric(point.low, metric)} – {formatMetric(point.high, metric)}
            </td>
          </tr>
        );
      })}

      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {totalLabel} — {metric.label}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2" />
        <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap">
          {formatMetric(metric.total, metric)}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap text-[var(--text-muted)]">
          {formatMetric(metric.budgetTotal, metric)}
        </td>
        <td
          className={`border-l border-[var(--border)] px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap ${amountClassName(metric.vsBudget)}`}
        >
          {metric.budgetTotal !== 0
            ? signedPercent.format(metric.vsBudget / Math.abs(metric.budgetTotal))
            : '—'}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2" />
      </tr>
    </Fragment>
  );
}
