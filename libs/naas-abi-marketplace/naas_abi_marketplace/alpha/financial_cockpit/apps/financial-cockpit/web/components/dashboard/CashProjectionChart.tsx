'use client';

import { useMemo, useState } from 'react';

import { ThemeNumber } from '@/components/theme/ThemeNumber';
import type { CashProjectionPoint } from '@/lib/data/treasury';

const CHART_HEIGHT_REM = 18;

const dateFormatter = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: 'short',
});
const fullDateFormatter = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: 'long',
  year: 'numeric',
});
const currencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});
const compactCurrencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

/** Round a rough step up to a "nice" 1/2/5 × 10ⁿ value. */
function niceStep(rough: number): number {
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  const normalized = rough / power;
  const nice = normalized >= 5 ? 10 : normalized >= 2 ? 5 : normalized >= 1 ? 2 : 1;
  return nice * power;
}

function parseISODate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function clampPct(value: number): number {
  return Math.max(0, Math.min(100, value));
}

type CashProjectionChartProps = {
  points: CashProjectionPoint[];
  /** Current bank position (chart anchor). */
  initialPosition: number;
  /** ISO date the position was measured (data extraction date). */
  positionDate?: string | null;
  /** Called when a day of the projection is clicked (drill-down). */
  onPointClick?: (point: CashProjectionPoint) => void;
  /** ISO date of the currently drilled-down day, if any. */
  activeDate?: string | null;
};

export function CashProjectionChart({
  points,
  initialPosition,
  positionDate,
  onPointClick,
  activeDate,
}: CashProjectionChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const geometry = useMemo(() => {
    if (points.length === 0) {
      return null;
    }
    const balances = points.map((point) => point.balance);
    const rawMax = Math.max(0, ...balances);
    const rawMin = Math.min(0, ...balances);
    const pad = (rawMax - rawMin || Math.abs(rawMax) || 1) * 0.08;
    const yMax = rawMax + pad;
    const yMin = rawMin - pad;
    const span = yMax - yMin || 1;

    const xPct = (index: number) =>
      points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
    const yPct = (value: number) => clampPct(((yMax - value) / span) * 100);
    const zeroYPct = yPct(0);

    const plotted = points.map((point, index) => ({
      point,
      leftPct: xPct(index),
      topPct: yPct(point.balance),
    }));

    const linePath = plotted
      .map((entry, index) => `${index === 0 ? 'M' : 'L'}${entry.leftPct},${entry.topPct}`)
      .join(' ');

    const areaPath =
      `M${xPct(0)},${zeroYPct} ` +
      plotted.map((entry) => `L${entry.leftPct},${entry.topPct}`).join(' ') +
      ` L${xPct(points.length - 1)},${zeroYPct} Z`;

    const markers = plotted.filter(
      (entry) => entry.point.inflow > 0 || entry.point.outflow > 0,
    );

    const tickCount = Math.min(6, points.length);
    const xTicks = Array.from({ length: tickCount }, (_, tick) => {
      const index =
        tickCount === 1
          ? 0
          : Math.round((tick / (tickCount - 1)) * (points.length - 1));
      return { leftPct: xPct(index), date: points[index].date };
    });

    // A handful of round y-axis values (1/2/5 steps) inside the padded domain.
    const yStep = niceStep(span / 4);
    const yTicks: { value: number; topPct: number }[] = [];
    for (
      let value = Math.ceil(yMin / yStep) * yStep;
      value <= yMax;
      value += yStep
    ) {
      yTicks.push({ value, topPct: yPct(value) });
    }

    return {
      plotted,
      linePath,
      areaPath,
      zeroYPct,
      yMax: rawMax,
      yMin: rawMin,
      markers,
      xTicks,
      yTicks,
      lastBalance: balances[balances.length - 1],
    };
  }, [points]);

  if (!geometry) {
    return null;
  }

  const hasNegative = geometry.yMin < 0;
  const hovered =
    hoverIndex !== null && geometry.plotted[hoverIndex]
      ? geometry.plotted[hoverIndex]
      : null;
  const selected = activeDate
    ? (geometry.plotted.find((entry) => entry.point.date === activeDate) ?? null)
    : null;

  function indexFromEvent(event: React.MouseEvent<HTMLDivElement>): number | null {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width === 0) return null;
    const ratio = (event.clientX - rect.left) / rect.width;
    const index = Math.round(ratio * (points.length - 1));
    return Math.max(0, Math.min(points.length - 1, index));
  }

  function handleMove(event: React.MouseEvent<HTMLDivElement>) {
    const index = indexFromEvent(event);
    if (index !== null) setHoverIndex(index);
  }

  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!onPointClick) return;
    const index = indexFromEvent(event);
    if (index !== null) onPointClick(points[index]);
  }

  return (
    <div className="glass rounded-lg p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        {/* Initial position — top-left corner. */}
        <span className="text-sm text-[var(--text-muted)]">
          Position{positionDate ? ` au ${fullDateFormatter.format(parseISODate(positionDate))}` : ''}
          <ThemeNumber
            value={initialPosition}
            style="currency"
            maximumFractionDigits={0}
            className={`mt-1 block text-xl font-semibold tabular-nums tracking-tight ${
              initialPosition < 0 ? 'text-[var(--recovery-danger)]' : 'text-[var(--text)]'
            }`}
          />
        </span>
        <span className="text-right text-sm text-[var(--text-muted)]">
          Solde prévisionnel à échéance
          <span
            className={`mt-1 block text-xl font-semibold tabular-nums tracking-tight ${
              geometry.lastBalance < 0
                ? 'text-[var(--recovery-danger)]'
                : 'text-[var(--text)]'
            }`}
          >
            {currencyFormatter.format(geometry.lastBalance)}
          </span>
        </span>
      </div>

      <div className="flex" style={{ height: `${CHART_HEIGHT_REM}rem` }}>
        {/* Y-axis labels — outside the plot */}
        <div className="relative w-16 shrink-0 pr-2" aria-hidden>
          {geometry.yTicks.map((tick) => (
            <span
              key={tick.value}
              className="absolute right-2 -translate-y-1/2 text-right text-[10px] tabular-nums text-[var(--text-muted)]"
              style={{ top: `${tick.topPct}%` }}
            >
              {compactCurrencyFormatter.format(tick.value)}
            </span>
          ))}
        </div>

        {/* Plot area */}
        <div
          className={`relative h-full min-w-0 flex-1${onPointClick ? ' cursor-pointer' : ''}`}
          onMouseMove={handleMove}
          onClick={handleClick}
          onMouseLeave={() => setHoverIndex(null)}
        >
          {/* Y-axis gridlines (HTML overlay to avoid viewBox distortion) */}
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
            <defs>
              <clipPath id="cash-projection-below" clipPathUnits="userSpaceOnUse">
                <rect
                  x="0"
                  y={geometry.zeroYPct}
                  width="100"
                  height={100 - geometry.zeroYPct}
                />
              </clipPath>
              <clipPath id="cash-projection-above" clipPathUnits="userSpaceOnUse">
                <rect x="0" y="0" width="100" height={geometry.zeroYPct} />
              </clipPath>
            </defs>

            {/* Positive area (subtle) */}
            <path
              d={geometry.areaPath}
              fill="var(--recovery-success)"
              opacity={0.12}
              clipPath="url(#cash-projection-above)"
            />
            {/* Negative area (red zone below 0) */}
            <path
              d={geometry.areaPath}
              fill="var(--recovery-danger)"
              opacity={0.22}
              clipPath="url(#cash-projection-below)"
            />

            {/* Zero baseline */}
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

            {/* Projection line */}
            <path
              d={geometry.linePath}
              fill="none"
              stroke="var(--primary)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          </svg>

          {/* Event markers (HTML overlay to avoid viewBox distortion) */}
          {geometry.markers.map((marker) => (
            <span
              key={marker.point.date}
              className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-[var(--surface)]"
              style={{
                left: `${marker.leftPct}%`,
                top: `${marker.topPct}%`,
                backgroundColor:
                  marker.point.balance < 0
                    ? 'var(--recovery-danger)'
                    : 'var(--primary)',
              }}
            />
          ))}

          {/* Selected day (drill-down) — persistent guide + marker */}
          {selected ? (
            <>
              <span
                className="pointer-events-none absolute inset-y-0 w-px bg-[var(--secondary)]"
                style={{ left: `${selected.leftPct}%` }}
                aria-hidden
              />
              <span
                className="pointer-events-none absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--secondary)] bg-[var(--surface)]"
                style={{ left: `${selected.leftPct}%`, top: `${selected.topPct}%` }}
                aria-hidden
              />
            </>
          ) : null}

          {/* Hover guide + highlighted point */}
          {hovered ? (
            <>
              <span
                className="pointer-events-none absolute inset-y-0 w-px border-l border-dashed border-[var(--secondary)]"
                style={{ left: `${hovered.leftPct}%` }}
                aria-hidden
              />
              <span
                className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--surface)] bg-[var(--secondary)]"
                style={{ left: `${hovered.leftPct}%`, top: `${hovered.topPct}%` }}
                aria-hidden
              />
              <ProjectionTooltip
                balance={hovered.point.balance}
                leftPct={hovered.leftPct}
              />
            </>
          ) : null}
        </div>
      </div>

      {/* X-axis date labels — aligned with the plot (offset by y-axis column) */}
      <div className="relative mt-2 ml-16 h-4 text-xs text-[var(--text-muted)]">
        {geometry.xTicks.map((tick, index) => (
          <span
            key={tick.date}
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
            {dateFormatter.format(parseISODate(tick.date))}
          </span>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
        <LegendSwatch color="var(--primary)" label="Solde projeté" />
        {hasNegative ? (
          <LegendSwatch color="var(--recovery-danger)" label="Trésorerie négative" />
        ) : null}
      </div>
    </div>
  );
}

function ProjectionTooltip({
  balance,
  leftPct,
}: {
  balance: number;
  leftPct: number;
}) {
  // Pin to the top of the plot and shift horizontally off the guide/marker so
  // the label never sits on top of the selected/hovered point.
  const anchorRight = leftPct > 55;
  return (
    <div
      className="pointer-events-none absolute top-2 z-10 whitespace-nowrap rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-xs shadow-lg"
      style={{
        left: `${leftPct}%`,
        transform: anchorRight
          ? 'translateX(calc(-100% - 14px))'
          : 'translateX(14px)',
      }}
    >
      <span className="text-[var(--text-muted)]">Solde projeté </span>
      <span
        className={`font-semibold tabular-nums ${
          balance < 0 ? 'text-[var(--recovery-danger)]' : 'text-[var(--text)]'
        }`}
      >
        {currencyFormatter.format(balance)}
      </span>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-3 w-3 rounded-sm"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      {label}
    </span>
  );
}
