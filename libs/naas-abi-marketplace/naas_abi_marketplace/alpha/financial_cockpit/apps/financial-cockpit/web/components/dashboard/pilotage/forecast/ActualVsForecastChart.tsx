'use client';

import type { ForecastPoint } from '@/lib/pilotage/forecast/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 16;

const ACTUAL_COLOR = 'var(--primary)';
const FORECAST_COLOR = 'color-mix(in srgb, var(--primary) 45%, var(--surface))';
const BUDGET_COLOR = 'var(--text-muted)';

type ActualVsForecastChartProps = {
  title: string;
  hint?: string;
  points: ForecastPoint[];
  emptyMessage?: string;
  formatValue?: (value: number) => string;
};

/**
 * One bar per month — solid where the month is closed (actual), hollow where it
 * is still a forecast — with the budget drawn as a tick so the reader can see
 * plan versus expectation at a glance.
 */
export function ActualVsForecastChart({
  title,
  hint,
  points,
  emptyMessage = 'No data for this perimeter.',
  formatValue = (value: number) => compactCurrency.format(value),
}: ActualVsForecastChartProps) {
  const max = points.reduce(
    (acc, point) => Math.max(acc, point.expected, point.budget),
    0,
  );
  const scale = max * 1.1 || 1;
  const firstForecast = points.findIndex((point) => !point.isActual);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        <div className="flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: ACTUAL_COLOR }}
              aria-hidden
            />
            Actual
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: FORECAST_COLOR }}
              aria-hidden
            />
            Forecast
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-0.5 w-3"
              style={{ backgroundColor: BUDGET_COLOR }}
              aria-hidden
            />
            Budget
          </span>
        </div>
      </div>

      {points.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="relative flex items-end gap-1 sm:gap-1.5"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {/* Marks where actuals stop and the forecast takes over. */}
            {firstForecast > 0 ? (
              <div
                className="pointer-events-none absolute inset-y-0 border-l border-dashed border-[var(--border)]"
                style={{ left: `${(firstForecast / points.length) * 100}%` }}
                aria-hidden
              />
            ) : null}

            {points.map((point) => {
              const heightPct = Math.max(0.5, (point.expected / scale) * 100);
              const budgetPct = Math.max(0, (point.budget / scale) * 100);
              return (
                <div
                  key={point.period}
                  className="relative flex h-full min-w-0 flex-1 flex-col justify-end"
                  title={`${point.label} — ${
                    point.isActual ? 'actual' : 'forecast'
                  } ${formatValue(point.expected)} · budget ${formatValue(point.budget)}`}
                >
                  <div
                    className="w-full rounded-t-sm"
                    style={{
                      height: `${heightPct}%`,
                      backgroundColor: point.isActual ? ACTUAL_COLOR : FORECAST_COLOR,
                    }}
                  />
                  <span
                    className="absolute inset-x-0 h-0.5"
                    style={{ bottom: `${budgetPct}%`, backgroundColor: BUDGET_COLOR }}
                    aria-hidden
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-2 flex gap-1 sm:gap-1.5">
            {points.map((point, index) => (
              <span
                key={`label-${point.period}`}
                className="min-w-0 flex-1 truncate text-center text-[10px] text-[var(--text-muted)]"
              >
                {/* Only every other label on dense series. */}
                {points.length > 8 && index % 2 === 1 ? '' : point.label.split(' ')[0]}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
