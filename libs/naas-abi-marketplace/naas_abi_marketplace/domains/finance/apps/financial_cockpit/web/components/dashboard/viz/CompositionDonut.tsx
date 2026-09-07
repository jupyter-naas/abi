'use client';

import type { CompositionSlice } from '@/lib/performance/balanceSheet/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

/** Theme-driven palette, reused for donut arcs and legend swatches. */
export const BS_PALETTE = [
  'var(--primary)',
  'var(--secondary)',
  'var(--recovery-success)',
  'var(--recovery-warning)',
  'var(--recovery-orange)',
  'var(--recovery-danger)',
  'color-mix(in srgb, var(--primary) 45%, var(--surface))',
];

const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

type CompositionDonutProps = {
  title: string;
  hint?: string;
  slices: CompositionSlice[];
  emptyMessage?: string;
  /** Caption above the total in the donut hole. */
  totalLabel?: string;
  /**
   * Formats the hole total and the legend values. Defaults to compact EUR —
   * pass an integer formatter for a donut that slices counts rather than money.
   */
  formatValue?: (value: number) => string;
};

export function CompositionDonut({
  title,
  hint,
  slices,
  emptyMessage = 'No data for this perimeter.',
  totalLabel = 'Total assets',
  formatValue = (value: number) => compactCurrency.format(value),
}: CompositionDonutProps) {
  const total = slices.reduce((sum, slice) => sum + Math.max(0, slice.value), 0);

  let offset = 0;
  const arcs = slices.map((slice, index) => {
    const fraction = total > 0 ? Math.max(0, slice.value) / total : 0;
    const length = fraction * CIRCUMFERENCE;
    const arc = {
      slice,
      color: BS_PALETTE[index % BS_PALETTE.length],
      dashArray: `${length} ${CIRCUMFERENCE - length}`,
      dashOffset: -offset,
      fraction,
    };
    offset += length;
    return arc;
  });

  return (
    <div className="glass rounded-lg p-6 h-full">
      <h3 className="type-title-5 mb-4" title={hint}>
        {title}
      </h3>
      {total <= 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-6">
          <div className="relative h-40 w-40 shrink-0">
            <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
              <circle
                cx="50"
                cy="50"
                r={RADIUS}
                fill="none"
                stroke="var(--border)"
                strokeWidth="12"
                opacity={0.35}
              />
              {arcs.map((arc) => (
                <circle
                  key={arc.slice.key}
                  cx="50"
                  cy="50"
                  r={RADIUS}
                  fill="none"
                  stroke={arc.color}
                  strokeWidth="12"
                  strokeDasharray={arc.dashArray}
                  strokeDashoffset={arc.dashOffset}
                />
              ))}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                {totalLabel}
              </span>
              <span className="text-sm font-semibold tabular-nums">
                {formatValue(total)}
              </span>
            </div>
          </div>

          <ul className="min-w-0 flex-1 space-y-1.5">
            {arcs.map((arc) => (
              <li key={arc.slice.key} className="flex items-center gap-2 text-sm">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{ backgroundColor: arc.color }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate" title={arc.slice.label}>
                  {arc.slice.label}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-[var(--text-muted)]">
                  {percentFormatter.format(arc.fraction)}
                </span>
                <span className="w-16 shrink-0 text-right text-xs tabular-nums">
                  {formatValue(arc.slice.value)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
