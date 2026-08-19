'use client';

import { useMemo } from 'react';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 15;

export type TrendSeries = {
  name: string;
  color: string;
  values: number[];
  /** Draw a soft area under the line (first/primary series only). */
  fill?: boolean;
};

type TrendChartProps = {
  title: string;
  hint?: string;
  labels: string[];
  series: TrendSeries[];
  emptyMessage?: string;
  /**
   * Formats the axis ticks and legend values. Defaults to compact EUR — pass a
   * percent/decimal formatter for non-currency series (e.g. financial ratios).
   */
  formatValue?: (value: number) => string;
};

/** Round a rough step up to a "nice" 1/2/5 × 10ⁿ value. */
function niceStep(rough: number): number {
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  const normalized = rough / power;
  const nice = normalized >= 5 ? 10 : normalized >= 2 ? 5 : normalized >= 1 ? 2 : 1;
  return nice * power;
}

function clampPct(value: number): number {
  return Math.max(0, Math.min(100, value));
}

export function TrendChart({
  title,
  hint,
  labels,
  series,
  emptyMessage = 'No data for this perimeter.',
  formatValue = (value: number) => compactCurrency.format(value),
}: TrendChartProps) {
  const geometry = useMemo(() => {
    const allValues = series.flatMap((entry) => entry.values);
    if (allValues.length === 0 || labels.length === 0) {
      return null;
    }
    const count = labels.length;
    const rawMax = Math.max(0, ...allValues);
    const rawMin = Math.min(0, ...allValues);
    const pad = (rawMax - rawMin || Math.abs(rawMax) || 1) * 0.08;
    const yMax = rawMax + pad;
    const yMin = rawMin - pad;
    const span = yMax - yMin || 1;

    const xPct = (index: number) => (count === 1 ? 50 : (index / (count - 1)) * 100);
    const yPct = (value: number) => clampPct(((yMax - value) / span) * 100);
    const zeroYPct = yPct(0);

    const paths = series.map((entry) => {
      const points = entry.values.map((value, index) => ({
        x: xPct(index),
        y: yPct(value),
      }));
      const linePath = points
        .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x},${point.y}`)
        .join(' ');
      const areaPath =
        points.length > 0
          ? `M${xPct(0)},${zeroYPct} ` +
            points.map((point) => `L${point.x},${point.y}`).join(' ') +
            ` L${xPct(count - 1)},${zeroYPct} Z`
          : '';
      return { entry, linePath, areaPath, last: points[points.length - 1] };
    });

    const yStep = niceStep(span / 4);
    const yTicks: { value: number; topPct: number }[] = [];
    for (let value = Math.ceil(yMin / yStep) * yStep; value <= yMax; value += yStep) {
      yTicks.push({ value, topPct: yPct(value) });
    }

    const tickCount = Math.min(6, count);
    const xTicks = Array.from({ length: tickCount }, (_, tick) => {
      const index =
        tickCount === 1 ? 0 : Math.round((tick / (tickCount - 1)) * (count - 1));
      return { leftPct: xPct(index), label: labels[index] };
    });

    return { paths, yTicks, xTicks, zeroYPct, hasNegative: rawMin < 0 };
  }, [labels, series]);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        <div className="flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
          {series.map((entry) => (
            <span key={entry.name} className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: entry.color }}
                aria-hidden
              />
              {entry.name}
              {entry.values.length > 0 ? (
                <span className="font-semibold tabular-nums text-[var(--text)]">
                  {formatValue(entry.values[entry.values.length - 1])}
                </span>
              ) : null}
            </span>
          ))}
        </div>
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
              {geometry.yTicks.map((tick) =>
                tick.value !== 0 ? (
                  <div
                    key={tick.value}
                    className="pointer-events-none absolute inset-x-0 border-t border-[var(--border)] opacity-40"
                    style={{ top: `${tick.topPct}%` }}
                    aria-hidden
                  />
                ) : null,
              )}

              <svg
                className="pointer-events-none absolute inset-0 h-full w-full"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                aria-hidden
              >
                {geometry.paths.map((path) =>
                  path.entry.fill ? (
                    <path
                      key={`area-${path.entry.name}`}
                      d={path.areaPath}
                      fill={path.entry.color}
                      opacity={0.12}
                    />
                  ) : null,
                )}
                {geometry.hasNegative ? (
                  <line
                    x1="0"
                    y1={geometry.zeroYPct}
                    x2="100"
                    y2={geometry.zeroYPct}
                    stroke="var(--border)"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    vectorEffect="non-scaling-stroke"
                  />
                ) : null}
                {geometry.paths.map((path) => (
                  <path
                    key={`line-${path.entry.name}`}
                    d={path.linePath}
                    fill="none"
                    stroke={path.entry.color}
                    strokeWidth={2}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    vectorEffect="non-scaling-stroke"
                  />
                ))}
              </svg>

              {geometry.paths.map((path) =>
                path.last ? (
                  <span
                    key={`dot-${path.entry.name}`}
                    className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-[var(--surface)]"
                    style={{
                      left: `${path.last.x}%`,
                      top: `${path.last.y}%`,
                      backgroundColor: path.entry.color,
                    }}
                    aria-hidden
                  />
                ) : null,
              )}
            </div>
          </div>

          <div className="relative mt-2 ml-14 h-4 text-xs text-[var(--text-muted)]">
            {geometry.xTicks.map((tick, index) => (
              <span
                key={`${tick.label}-${index}`}
                className="absolute whitespace-nowrap"
                style={{
                  left: `${tick.leftPct}%`,
                  transform:
                    index === 0
                      ? 'translateX(0)'
                      : index === geometry.xTicks.length - 1
                        ? 'translateX(-100%)'
                        : 'translateX(-50%)',
                }}
              >
                {tick.label}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
