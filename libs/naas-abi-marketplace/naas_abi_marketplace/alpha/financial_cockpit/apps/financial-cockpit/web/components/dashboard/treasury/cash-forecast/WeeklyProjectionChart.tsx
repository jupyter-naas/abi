'use client';

import type { WeekPoint } from '@/lib/treasury/cashForecast/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 16;

const ACTUAL_COLOR = 'var(--secondary)';
const FORECAST_COLOR = 'var(--primary)';
const TROUGH_COLOR = 'var(--recovery-danger)';
const NEGATIVE_COLOR = 'var(--recovery-danger)';

type WeeklyProjectionChartProps = {
  title: string;
  hint?: string;
  weeks: WeekPoint[];
  /** Marks the balance below which the position is uncomfortable. */
  threshold?: number;
  emptyMessage?: string;
};

/**
 * Closing cash week by week, with the lowest week called out.
 *
 * This is the chart the page exists for: a monthly view can close every month
 * comfortably while the balance dips inside one of them, and it is the dip that
 * decides whether the company needs a facility drawn.
 */
export function WeeklyProjectionChart({
  title,
  hint,
  weeks,
  threshold,
  emptyMessage = 'No projection for this perimeter.',
}: WeeklyProjectionChartProps) {
  const values = weeks.map((week) => week.closingCash);
  const rawMax = Math.max(0, ...values);
  const rawMin = Math.min(0, ...values);
  const span = rawMax - rawMin || Math.abs(rawMax) || 1;
  // Zero sits proportionally within the drawn range so negatives hang below it.
  const zeroPct = (rawMax / span) * 100;

  const troughIndex = values.reduce(
    (lowest, value, index) => (value < values[lowest] ? index : lowest),
    0,
  );
  const trough = weeks[troughIndex];

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        {trough ? (
          <span className="text-xs text-[var(--text-muted)]">
            Lowest{' '}
            <span
              className="font-semibold tabular-nums"
              style={{ color: TROUGH_COLOR }}
            >
              {compactCurrency.format(trough.closingCash)}
            </span>{' '}
            week of {trough.label}
          </span>
        ) : null}
      </div>

      {weeks.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="relative flex items-stretch gap-px"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {rawMin < 0 ? (
              <span
                className="pointer-events-none absolute inset-x-0 border-t border-[var(--border)]"
                style={{ top: `${zeroPct}%` }}
                aria-hidden
              />
            ) : null}
            {threshold !== undefined && threshold > rawMin && threshold < rawMax ? (
              <span
                className="pointer-events-none absolute inset-x-0 border-t border-dashed"
                style={{
                  top: `${((rawMax - threshold) / span) * 100}%`,
                  borderColor: TROUGH_COLOR,
                  opacity: 0.7,
                }}
                title={`Comfort threshold: ${compactCurrency.format(threshold)}`}
                aria-hidden
              />
            ) : null}

            {weeks.map((week, index) => {
              const value = week.closingCash;
              const heightPct = (Math.abs(value) / span) * 100;
              const topPct =
                value >= 0 ? zeroPct - heightPct : zeroPct;
              const color =
                index === troughIndex
                  ? TROUGH_COLOR
                  : value < 0
                    ? NEGATIVE_COLOR
                    : week.isActual
                      ? ACTUAL_COLOR
                      : FORECAST_COLOR;

              return (
                <div
                  key={week.week}
                  className="relative min-w-0 flex-1"
                  title={`Week to ${week.label}${
                    week.isActual ? ' (actual)' : ''
                  }: ${compactCurrency.format(value)}`}
                >
                  <span
                    className="absolute inset-x-0 rounded-sm"
                    style={{
                      top: `${topPct}%`,
                      height: `${Math.max(0.5, heightPct)}%`,
                      backgroundColor: color,
                      opacity: week.isActual ? 1 : 0.8,
                    }}
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-2 flex justify-between text-[10px] text-[var(--text-muted)]">
            <span>{weeks[0]?.label}</span>
            <span>{weeks[weeks.length - 1]?.label}</span>
          </div>

          <div className="mt-3 flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
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
              Projected
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: TROUGH_COLOR }}
                aria-hidden
              />
              Lowest point
            </span>
          </div>
        </>
      )}
    </div>
  );
}
