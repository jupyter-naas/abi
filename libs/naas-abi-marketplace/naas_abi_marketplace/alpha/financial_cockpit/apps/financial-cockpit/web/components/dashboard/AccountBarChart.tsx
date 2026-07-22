'use client';

import { ThemeNumber } from '@/components/theme/ThemeNumber';
import type { AccountValue } from '@/lib/data/treasury';

/** Approximate height of one bar row (label + bar + gap). */
const ROW_HEIGHT_REM = 4.25;

type AccountBarChartProps = {
  title: string;
  hint?: string;
  items: AccountValue[];
  emptyMessage?: string;
  /** How many rows are visible before scrolling inside the tile. */
  visibleCount?: number;
  /**
   * 'diverging' → bars grow left/right from a centered zero line (signed values).
   * 'bar'       → left-anchored bars (magnitudes).
   */
  variant?: 'diverging' | 'bar';
  /** Forces every bar to this color (else colored by sign). */
  color?: string;
};

export function AccountBarChart({
  title,
  hint,
  items,
  emptyMessage = 'Aucune donnée pour ce périmètre.',
  visibleCount = 5,
  variant = 'bar',
  color,
}: AccountBarChartProps) {
  const maxAbs = Math.max(...items.map((item) => Math.abs(item.value)), 1);
  const scrollable = items.length > visibleCount;

  return (
    <div className="glass rounded-lg p-6 h-full">
      <h3 className="type-title-5 mb-4" title={hint}>
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul
          className={`space-y-3 overflow-y-auto overscroll-contain pr-1${scrollable ? ' scrollbar-thin' : ''}`}
          style={{ maxHeight: `${visibleCount * ROW_HEIGHT_REM}rem` }}
          aria-label={scrollable ? `${title} — ${items.length} lignes, défilement` : undefined}
        >
          {items.map((item) => {
            const negative = item.value < 0;
            const barColor =
              color ?? (negative ? 'var(--recovery-danger)' : 'var(--primary)');
            const magnitudePct =
              item.value === 0 ? 0 : (Math.abs(item.value) / maxAbs) * 100;
            const diverging = variant === 'diverging';
            const widthPct = diverging
              ? Math.max(item.value === 0 ? 0 : 1.5, magnitudePct / 2)
              : Math.max(item.value === 0 ? 0 : 4, magnitudePct);
            return (
              <li key={item.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-medium" title={item.label}>
                    {item.label}
                  </span>
                  <ThemeNumber
                    value={item.value}
                    style="currency"
                    maximumFractionDigits={0}
                    className="shrink-0 text-sm tabular-nums"
                  />
                </div>
                <div className="progress-bar-bg relative h-3 overflow-hidden rounded-sm">
                  <div
                    className="h-full rounded-sm transition-[width] duration-500"
                    style={{
                      position: 'absolute',
                      top: 0,
                      bottom: 0,
                      width: `${widthPct}%`,
                      backgroundColor: barColor,
                      ...(diverging
                        ? negative
                          ? { right: '50%' }
                          : { left: '50%' }
                        : { left: 0 }),
                    }}
                  />
                  {diverging ? (
                    <div
                      className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[var(--text-muted)] opacity-60"
                      aria-hidden
                    />
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
