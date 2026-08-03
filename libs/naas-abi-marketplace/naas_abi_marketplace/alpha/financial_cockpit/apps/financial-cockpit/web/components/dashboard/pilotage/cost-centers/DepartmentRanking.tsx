'use client';

import type { CostCenterSummary } from '@/lib/pilotage/costCenters/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
});

/** Overspend beyond this share of budget reads as a problem, not noise. */
const OVERSPEND_THRESHOLD = 0.05;

type DepartmentRankingProps = {
  title: string;
  hint?: string;
  centers: CostCenterSummary[];
  emptyMessage?: string;
  /** How many rows are visible before the list scrolls. */
  visibleCount?: number;
};

/**
 * Departments ranked by spend, with the budget drawn as a marker on each bar
 * and the variance called out on the right — so the biggest spenders and the
 * worst overruns can be read from the same row.
 */
export function DepartmentRanking({
  title,
  hint,
  centers,
  emptyMessage = 'No cost centers for this perimeter.',
  visibleCount = 8,
}: DepartmentRankingProps) {
  const max = centers.reduce(
    (acc, center) => Math.max(acc, center.actual, center.budget),
    0,
  );
  const scale = max * 1.08 || 1;
  const scrollable = centers.length > visibleCount;

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
          <span
            className="inline-block h-3 w-0.5 bg-[var(--text-muted)]"
            aria-hidden
          />
          Budget
        </span>
      </div>

      {centers.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul
          className={`space-y-3 overflow-y-auto overscroll-contain pr-1${
            scrollable ? ' scrollbar-thin' : ''
          }`}
          style={{ maxHeight: `${visibleCount * 3.75}rem` }}
          aria-label={
            scrollable ? `${title} — ${centers.length} entries, scrollable` : undefined
          }
        >
          {centers.map((center) => {
            const overspent =
              center.variancePct !== null && center.variancePct > OVERSPEND_THRESHOLD;
            const color = overspent
              ? 'var(--recovery-danger)'
              : center.variance > 0
                ? 'var(--recovery-orange)'
                : 'var(--primary)';
            const actualPct = Math.max(2, (center.actual / scale) * 100);
            const budgetPct = Math.max(0, (center.budget / scale) * 100);

            return (
              <li key={center.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span
                    className="min-w-0 truncate text-sm font-medium"
                    title={`${center.divisionLabel} · ${center.label}`}
                  >
                    {center.label}
                  </span>
                  <span className="shrink-0 text-sm tabular-nums">
                    {compactCurrency.format(center.actual)}
                  </span>
                </div>

                <div className="progress-bar-bg relative h-3 overflow-hidden rounded-sm">
                  <div
                    className="h-full rounded-sm transition-[width] duration-500"
                    style={{ width: `${actualPct}%`, backgroundColor: color }}
                  />
                  <span
                    className="absolute inset-y-0 w-0.5 bg-[var(--text-muted)]"
                    style={{ left: `${budgetPct}%` }}
                    title={`Budget: ${compactCurrency.format(center.budget)}`}
                    aria-hidden
                  />
                </div>

                <p className="mt-1 flex justify-between text-xs text-[var(--text-muted)]">
                  <span>{center.divisionLabel}</span>
                  <span
                    className="tabular-nums"
                    style={{
                      color: overspent ? 'var(--recovery-danger)' : undefined,
                    }}
                  >
                    {center.variancePct !== null
                      ? `${percentFormatter.format(center.variancePct)} vs budget`
                      : '—'}
                  </span>
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
