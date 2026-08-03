'use client';

import type { ScenarioCase } from '@/lib/pilotage/scenarioAnalysis/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 14;

const REVENUE_COLOR = 'color-mix(in srgb, var(--primary) 45%, var(--surface))';
const EBITDA_COLOR = 'var(--primary)';
const BASE_OUTLINE = 'var(--secondary)';

type ScenarioComparisonProps = {
  title: string;
  hint?: string;
  cases: ScenarioCase[];
  emptyMessage?: string;
};

/**
 * Revenue and EBITDA side by side for each what-if case, ordered best to worst.
 * The base case is outlined so the reader can see which column is today's plan
 * and read the others as departures from it.
 */
export function ScenarioComparison({
  title,
  hint,
  cases,
  emptyMessage = 'No scenarios for this perimeter.',
}: ScenarioComparisonProps) {
  const max = cases.reduce(
    (acc, entry) => Math.max(acc, entry.revenue, entry.ebitda),
    0,
  );
  const scale = max * 1.12 || 1;

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
              style={{ backgroundColor: REVENUE_COLOR }}
              aria-hidden
            />
            Revenue
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: EBITDA_COLOR }}
              aria-hidden
            />
            EBITDA
          </span>
        </div>
      </div>

      {cases.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="flex items-end justify-between gap-4"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {cases.map((entry) => (
              <div
                key={entry.key}
                className="flex h-full min-w-0 flex-1 flex-col justify-end"
              >
                <div className="flex h-full items-end justify-center gap-1">
                  {[
                    { key: 'revenue', value: entry.revenue, color: REVENUE_COLOR },
                    { key: 'ebitda', value: entry.ebitda, color: EBITDA_COLOR },
                  ].map((bar) => (
                    <div
                      key={bar.key}
                      className="w-1/2 max-w-[2.5rem] rounded-t-sm"
                      style={{
                        height: `${Math.max(0.5, (Math.max(0, bar.value) / scale) * 100)}%`,
                        backgroundColor: bar.color,
                        outline: entry.isBase ? `1.5px solid ${BASE_OUTLINE}` : undefined,
                        outlineOffset: entry.isBase ? '1px' : undefined,
                      }}
                      title={`${entry.label} — ${bar.key}: ${compactCurrency.format(bar.value)}`}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>

          <ul className="mt-3 flex justify-between gap-4">
            {cases.map((entry) => (
              <li key={`label-${entry.key}`} className="min-w-0 flex-1 text-center">
                <p
                  className="truncate text-xs font-medium"
                  title={entry.description ?? entry.label}
                >
                  {entry.label}
                  {entry.isBase ? ' ·' : ''}
                </p>
                <p className="text-[10px] tabular-nums text-[var(--text-muted)]">
                  p {percentFormatter.format(entry.probability)}
                </p>
                <p className="text-[10px] tabular-nums text-[var(--text-muted)]">
                  {percentFormatter.format(entry.margin)} margin
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
