'use client';

import { useMemo } from 'react';

import type { ForecastPoint } from '@/lib/pilotage/forecast/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 16;

const LINE_COLOR = 'var(--primary)';
const BAND_COLOR = 'var(--primary)';
const ACTUAL_COLOR = 'var(--secondary)';

type ConfidenceRangeChartProps = {
  title: string;
  hint?: string;
  points: ForecastPoint[];
  emptyMessage?: string;
  formatValue?: (value: number) => string;
};

function clampPct(value: number): number {
  return Math.max(0, Math.min(100, value));
}

/**
 * Expected value as a line inside a shaded low–high band. The band widens with
 * the forecast horizon, so the chart shows not just where the year lands but
 * how confidently — and actuals are overlaid so closed months read as certain.
 */
export function ConfidenceRangeChart({
  title,
  hint,
  points,
  emptyMessage = 'No data for this perimeter.',
  formatValue = (value: number) => compactCurrency.format(value),
}: ConfidenceRangeChartProps) {
  const geometry = useMemo(() => {
    if (points.length === 0) {
      return null;
    }
    const values = points.flatMap((point) => [point.low, point.high, point.expected]);
    const rawMax = Math.max(...values, 0);
    const rawMin = Math.min(...values, 0);
    const pad = (rawMax - rawMin || Math.abs(rawMax) || 1) * 0.08;
    const yMax = rawMax + pad;
    const yMin = rawMin - pad;
    const span = yMax - yMin || 1;

    const count = points.length;
    const xPct = (index: number) => (count === 1 ? 50 : (index / (count - 1)) * 100);
    const yPct = (value: number) => clampPct(((yMax - value) / span) * 100);

    const highPath = points.map((p, i) => `${xPct(i)},${yPct(p.high)}`);
    const lowPath = [...points].reverse().map((p, i) => {
      const index = count - 1 - i;
      return `${xPct(index)},${yPct(p.low)}`;
    });
    const bandPath = `M${highPath.join(' L')} L${lowPath.join(' L')} Z`;

    const linePath = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${xPct(i)},${yPct(p.expected)}`)
      .join(' ');

    const actualPoints = points
      .map((p, i) =>
        p.isActual && p.actual !== null
          ? { x: xPct(i), y: yPct(p.actual), point: p }
          : null,
      )
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

    const firstForecast = points.findIndex((point) => !point.isActual);

    return {
      bandPath,
      linePath,
      actualPoints,
      splitPct: firstForecast > 0 ? xPct(firstForecast) : null,
      yTicks: [yMax, (yMax + yMin) / 2, yMin].map((value) => ({
        value,
        topPct: yPct(value),
      })),
    };
  }, [points]);

  const last = points[points.length - 1];

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        {last ? (
          <span className="text-xs text-[var(--text-muted)]">
            {last.label}:{' '}
            <span className="font-semibold tabular-nums text-[var(--text)]">
              {formatValue(last.low)} – {formatValue(last.high)}
            </span>
          </span>
        ) : null}
      </div>

      {!geometry ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div className="flex" style={{ height: `${CHART_HEIGHT_REM}rem` }}>
            <div className="relative w-14 shrink-0 pr-2" aria-hidden>
              {geometry.yTicks.map((tick) => (
                <span
                  key={tick.value}
                  className="absolute right-2 -translate-y-1/2 text-right text-[10px] tabular-nums text-[var(--text-muted)]"
                  style={{ top: `${tick.topPct}%` }}
                >
                  {formatValue(tick.value)}
                </span>
              ))}
            </div>

            <div className="relative h-full min-w-0 flex-1">
              {geometry.splitPct !== null ? (
                <div
                  className="pointer-events-none absolute inset-y-0 border-l border-dashed border-[var(--border)]"
                  style={{ left: `${geometry.splitPct}%` }}
                  aria-hidden
                />
              ) : null}

              <svg
                className="absolute inset-0 h-full w-full"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                aria-hidden
              >
                <path d={geometry.bandPath} fill={BAND_COLOR} opacity={0.16} />
                <path
                  d={geometry.linePath}
                  fill="none"
                  stroke={LINE_COLOR}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
              </svg>

              {geometry.actualPoints.map((entry) => (
                <span
                  key={entry.point.period}
                  className="pointer-events-none absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{
                    left: `${entry.x}%`,
                    top: `${entry.y}%`,
                    backgroundColor: ACTUAL_COLOR,
                  }}
                  title={`${entry.point.label}: ${formatValue(entry.point.actual ?? 0)}`}
                />
              ))}
            </div>
          </div>

          <div className="mt-2 ml-14 flex justify-between text-[10px] text-[var(--text-muted)]">
            <span>{points[0]?.label}</span>
            <span>{last?.label}</span>
          </div>

          <div className="mt-3 flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: LINE_COLOR }}
                aria-hidden
              />
              Expected
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: BAND_COLOR, opacity: 0.3 }}
                aria-hidden
              />
              Confidence range
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: ACTUAL_COLOR }}
                aria-hidden
              />
              Actual
            </span>
          </div>
        </>
      )}
    </div>
  );
}
