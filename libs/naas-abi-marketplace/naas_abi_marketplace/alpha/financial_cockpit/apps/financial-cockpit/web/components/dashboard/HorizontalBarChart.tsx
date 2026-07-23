'use client';

import { ThemeNumber } from '@/components/theme/ThemeNumber';
import type { MiseEnDemeureBarItem } from '@/lib/data/unpaidClients';

/** Approximate height of one bar row (label + bar + count + gap). */
const ROW_HEIGHT_REM = 4.25;

type HorizontalBarChartProps = {
  title: string;
  items: MiseEnDemeureBarItem[];
  emptyMessage?: string;
  /** How many rows are visible before scrolling inside the tile. */
  visibleCount?: number;
};

export function HorizontalBarChart({
  title,
  items,
  emptyMessage = 'Aucune donnée.',
  visibleCount = 3,
}: HorizontalBarChartProps) {
  const maxAmount = Math.max(...items.map((item) => item.amount), 1);
  const scrollable = items.length > visibleCount;

  return (
    <div className="glass rounded-lg p-6 h-full">
      <h3 className="type-title-5 mb-4">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul
          className={`space-y-3 overflow-y-auto overscroll-contain pr-1${scrollable ? ' scrollbar-thin' : ''}`}
          style={{ maxHeight: `${visibleCount * ROW_HEIGHT_REM}rem` }}
          aria-label={scrollable ? `${title} — ${items.length} entrées, défilement` : undefined}
        >
          {items.map((item) => {
            const widthPct = Math.max(4, Math.round((item.amount / maxAmount) * 100));
            return (
              <li key={item.label}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-medium" title={item.label}>
                    {item.label}
                  </span>
                  <ThemeNumber
                    value={item.amount}
                    style="currency"
                    className="shrink-0 text-sm tabular-nums"
                  />
                </div>
                <div className="progress-bar-bg h-3 overflow-hidden rounded-sm">
                  <div
                    className="h-full rounded-sm bg-[var(--primary)] transition-[width] duration-500"
                    style={{ width: `${widthPct}%` }}
                    title={`${item.count} facture${item.count > 1 ? 's' : ''}`}
                  />
                </div>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {item.count} facture{item.count > 1 ? 's' : ''}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
