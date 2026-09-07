'use client';

import { Fragment, useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  buildCashForecast,
  cashForecastRecords,
  type MonthPoint,
  type WeekPoint,
} from '@/lib/treasury/cashForecast/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { InflowsOutflowsChart } from '@/components/dashboard/treasury/cash-forecast/InflowsOutflowsChart';
import { WeeklyProjectionChart } from '@/components/dashboard/treasury/cash-forecast/WeeklyProjectionChart';

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

const PAGE_HINT =
  'Whether cash covers the period ahead: the weekly walk, the lowest point it reaches, and how far the balance stretches at the current burn.';

/** Colour per case, applied in the scenario comparison. */
const CASE_COLORS: Record<string, string> = {
  upside: 'var(--recovery-success)',
  base: 'var(--primary)',
  downside: 'var(--recovery-danger)',
};

/** Runway below this many months is worth flagging. */
const RUNWAY_WARNING = 12;
const RUNWAY_DANGER = 6;

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-[var(--text)]';
}

export function TreasurySection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => cashForecastRecords(datasets.cash_forecast),
    [datasets.cash_forecast],
  );
  const view = useMemo(() => buildCashForecast(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  if (records.length === 0 || !view.base) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Cash Forecast{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No cash forecast for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis, weeks, months } = view;
  const weekLabels = weeks.map((week) => week.label);

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Cash Forecast{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {weeks.length} weeks projected · lowest point {kpis.lowestCashLabel}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Lowest Cash Point"
          value={kpis.lowestCash}
          valueStyle="currency"
          tone={kpis.lowestCash < 0 ? 'danger' : 'success'}
          subtitle={`Week of ${kpis.lowestCashLabel}`}
          hint="The lowest weekly closing balance in the period — the moment the position is tightest."
        />
        <KpiCard
          label="Runway"
          value={kpis.runway ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={1}
          // Runway is undefined while the company generates cash — showing "0"
          // would read as "no runway left", the opposite of what is happening.
          displayValue={kpis.runway === null ? '∞' : undefined}
          tone={
            kpis.runway === null
              ? 'success'
              : kpis.runway <= RUNWAY_DANGER
                ? 'danger'
                : kpis.runway <= RUNWAY_WARNING
                  ? 'warning'
                  : 'success'
          }
          subtitle={
            kpis.runway === null
              ? 'Cash-generative — no burn'
              : 'Months of cash at current burn'
          }
          hint="How long the closing balance lasts at the average net burn. Not meaningful while the company generates cash."
        />
        <KpiCard
          label="Peak Deficit"
          value={kpis.peakDeficit}
          valueStyle="currency"
          tone={kpis.peakDeficit < 0 ? 'danger' : 'success'}
          subtitle={
            kpis.peakDeficit < 0 ? 'Financing needed' : 'Balance never goes negative'
          }
          hint="The largest shortfall below zero across the period — how much funding would be needed to bridge it."
        />
        <KpiCard
          label="Expected Closing Cash"
          value={kpis.expectedClosingCash}
          valueStyle="currency"
          tone={kpis.expectedClosingCash >= 0 ? 'success' : 'danger'}
          subtitle="Base case, end of period"
          hint="Cash at the end of the period under the base case."
        />
        <KpiCard
          label="Inflows"
          value={kpis.inflows}
          valueStyle="currency"
          tone="success"
          subtitle="Collections and receipts"
          hint="Total money coming in across the period."
        />
        <KpiCard
          label="Outflows"
          value={kpis.outflows}
          valueStyle="currency"
          tone="orange"
          subtitle={`Net ${compactCurrency.format(kpis.netChange)}`}
          hint="Total money going out across the period — payroll, suppliers, debt service and tax."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Cash Forecast"
          hint="Closing cash at each month end under the base case."
          labels={months.map((point) => point.label)}
          series={[
            {
              name: 'Closing cash',
              color: 'var(--primary)',
              values: months.map((point) => point.closingCash),
              fill: true,
            },
          ]}
        />
        <InflowsOutflowsChart
          title="Inflows vs Outflows"
          hint="Gross money in and out each month, with the net movement marked."
          bars={months.map((point) => ({
            key: point.period,
            label: point.label,
            inflow: point.inflow,
            outflow: point.outflow,
            net: point.net,
          }))}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <WeeklyProjectionChart
          title="Weekly Projection"
          hint="Closing cash week by week. A month can close comfortably while the balance dips inside it — this is where that shows."
          weeks={weeks}
        />
        <TrendChart
          title="Scenario Comparison"
          hint="Closing cash under each case. The cases diverge with the horizon: the near term is close to certain, the far term is not."
          labels={weekLabels}
          series={view.cases.map((entry) => ({
            name: entry.label,
            color: CASE_COLORS[entry.key] ?? 'var(--secondary)',
            values: entry.points.map((point) => point.closingCash),
            fill: entry.isBase,
          }))}
        />
      </div>

      {/* ---- Detail table ------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="The base-case walk week by week: what comes in, what goes out, and the balance it leaves."
        >
          Cash Projection
        </PageTitle>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Week to
              </th>
              {['Opening', 'Inflows', 'Outflows', 'Net', 'Closing'].map((heading) => (
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
            {months.map((month) => (
              <MonthRows
                key={month.period}
                month={month}
                weeks={weeks.filter((week) => week.period === month.period)}
                lowestWeek={kpis.lowestCashLabel}
              />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        The base case re-anchors on the monthly forecast, so each month&rsquo;s final
        week closes on the same figure the Forecast page shows. Weeks already closed
        are marked as actual.
      </p>
    </div>
  );
}

function MonthRows({
  month,
  weeks,
  lowestWeek,
}: {
  month: MonthPoint;
  weeks: WeekPoint[];
  lowestWeek: string;
}) {
  return (
    <Fragment>
      <tr className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]">
        <td className="sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
          {month.label}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2" />
        <td className="border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap">
          {compactCurrency.format(month.inflow)}
        </td>
        <td className="border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap">
          {compactCurrency.format(month.outflow)}
        </td>
        <td
          className={`border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap ${amountClassName(month.net)}`}
        >
          {compactCurrency.format(month.net)}
        </td>
        <td
          className={`border-l border-[var(--border)] px-3 py-2 text-right text-xs font-semibold tabular-nums whitespace-nowrap ${amountClassName(month.closingCash)}`}
        >
          {compactCurrency.format(month.closingCash)}
        </td>
      </tr>

      {weeks.map((week) => {
        const isLowest = week.label === lowestWeek;
        return (
          <tr
            key={week.week}
            className={`border-b border-[var(--border)]${
              isLowest
                ? ' bg-[color-mix(in_srgb,var(--recovery-danger)_8%,transparent)]'
                : ''
            }`}
          >
            <td className="sticky left-0 z-10 bg-[var(--surface)] px-3 py-1 pl-6 text-sm text-[var(--text-muted)]">
              {week.label}
              {week.isActual ? '' : ' ·'}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap text-[var(--text-muted)]">
              {currencyFormatter.format(week.openingCash)}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap text-emerald-500">
              {currencyFormatter.format(week.inflow)}
            </td>
            <td className="border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap text-red-500">
              {currencyFormatter.format(week.outflow)}
            </td>
            <td
              className={`border-l border-[var(--border)] px-3 py-1 text-right tabular-nums whitespace-nowrap ${amountClassName(week.net)}`}
            >
              {currencyFormatter.format(week.net)}
            </td>
            <td
              className={`border-l border-[var(--border)] px-3 py-1 text-right font-medium tabular-nums whitespace-nowrap ${amountClassName(week.closingCash)}`}
            >
              {currencyFormatter.format(week.closingCash)}
            </td>
          </tr>
        );
      })}
    </Fragment>
  );
}
