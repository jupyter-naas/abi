'use client';

import type { GeographicShare } from '@/lib/treasury/cashPosition/model';

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

/** Share above which one country holds an uncomfortable amount of the cash. */
const CONCENTRATION_THRESHOLD = 0.5;

type GeographicDistributionProps = {
  title: string;
  hint?: string;
  countries: GeographicShare[];
  emptyMessage?: string;
};

/**
 * Cash by country of the holding account, with the currencies held there.
 * Concentration matters for treasury: cash sitting in one jurisdiction can be
 * slower to mobilise, so the leading country is flagged once it passes half of
 * the total.
 */
export function GeographicDistribution({
  title,
  hint,
  countries,
  emptyMessage = 'No accounts for this perimeter.',
}: GeographicDistributionProps) {
  const total = countries.reduce((sum, country) => sum + country.value, 0);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="type-title-5" title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          {countries.length} countr{countries.length === 1 ? 'y' : 'ies'}
        </span>
      </div>

      {total <= 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul className="space-y-3">
          {countries.map((country) => {
            const share = country.value / total;
            const concentrated = share > CONCENTRATION_THRESHOLD;
            return (
              <li key={country.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span className="flex min-w-0 items-baseline gap-2">
                    <span
                      className="shrink-0 rounded-sm bg-[var(--border)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                      aria-hidden
                    >
                      {country.key}
                    </span>
                    <span className="min-w-0 truncate text-sm font-medium">
                      {country.label}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm tabular-nums">
                    {compactCurrency.format(country.value)}
                  </span>
                </div>

                <div className="progress-bar-bg h-3 overflow-hidden rounded-sm">
                  <div
                    className="h-full rounded-sm transition-[width] duration-500"
                    style={{
                      width: `${Math.max(2, share * 100)}%`,
                      backgroundColor: concentrated
                        ? 'var(--recovery-orange)'
                        : 'var(--primary)',
                    }}
                  />
                </div>

                <p className="mt-1 flex justify-between text-xs text-[var(--text-muted)]">
                  <span>
                    {country.count} account{country.count === 1 ? '' : 's'} ·{' '}
                    {country.currencies.join(', ')}
                  </span>
                  <span className="tabular-nums">{percentFormatter.format(share)}</span>
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
