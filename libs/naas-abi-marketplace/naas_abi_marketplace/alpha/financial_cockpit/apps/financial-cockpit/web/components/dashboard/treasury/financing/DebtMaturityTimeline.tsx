'use client';

import type { Loan, MaturityBucket } from '@/lib/treasury/financing/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 2,
});

const FLOATING_COLOR = 'var(--recovery-orange)';
const FIXED_COLOR = 'var(--primary)';
const WALL_COLOR = 'var(--secondary)';

type DebtMaturityTimelineProps = {
  title: string;
  hint?: string;
  loans: Loan[];
  maturities: MaturityBucket[];
  /** Bounds of the time axis. */
  start: string | null;
  end: string | null;
  /** Marker for "today" — the close of the selected window. */
  asOf: string | null;
  emptyMessage?: string;
};

function toTime(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * Each facility drawn as a span from origination to maturity, over a shared
 * time axis, with the repayment wall summarised underneath.
 *
 * Reading maturities as spans rather than dates makes refinancing risk visible:
 * several bars ending in the same year is a wall, and the year totals below
 * quantify it.
 */
export function DebtMaturityTimeline({
  title,
  hint,
  loans,
  maturities,
  start,
  end,
  asOf,
  emptyMessage = 'No facilities for this perimeter.',
}: DebtMaturityTimelineProps) {
  const startTime = toTime(start);
  const endTime = toTime(end);
  const asOfTime = toTime(asOf);
  const span = startTime !== null && endTime !== null ? endTime - startTime : 0;

  const live = loans.filter((loan) => loan.outstanding > 0);
  const maxMaturity = maturities.reduce(
    (acc, bucket) => Math.max(acc, bucket.amount),
    0,
  );

  const positioned = span > 0 && startTime !== null;

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
              style={{ backgroundColor: FIXED_COLOR }}
              aria-hidden
            />
            Fixed
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: FLOATING_COLOR }}
              aria-hidden
            />
            Floating
          </span>
        </div>
      </div>

      {live.length === 0 || !positioned ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <ul className="space-y-2">
            {live.map((loan) => {
              const from = toTime(loan.origination);
              const to = toTime(loan.maturity);
              if (from === null || to === null) {
                return null;
              }
              const leftPct = ((from - startTime) / span) * 100;
              const widthPct = Math.max(2, ((to - from) / span) * 100);
              const color = loan.isFloating ? FLOATING_COLOR : FIXED_COLOR;

              return (
                <li key={loan.key} className="flex items-center gap-3">
                  <span
                    className="w-32 shrink-0 truncate text-xs"
                    title={`${loan.label} — ${loan.lender}`}
                  >
                    {loan.label}
                  </span>
                  <span className="relative h-5 min-w-0 flex-1">
                    {asOfTime !== null ? (
                      <span
                        className="absolute inset-y-0 w-px bg-[var(--text-muted)] opacity-60"
                        style={{
                          left: `${((asOfTime - startTime) / span) * 100}%`,
                        }}
                        aria-hidden
                      />
                    ) : null}
                    <span
                      className="absolute inset-y-0 flex items-center justify-end rounded-sm px-1.5"
                      style={{
                        left: `${leftPct}%`,
                        width: `${widthPct}%`,
                        backgroundColor: color,
                        opacity: 0.85,
                      }}
                      title={`${loan.label}: ${compactCurrency.format(
                        loan.outstanding,
                      )} at ${percentFormatter.format(loan.rate)} — ${
                        loan.origination
                      } → ${loan.maturity}`}
                    >
                      <span className="truncate text-[10px] font-semibold text-white">
                        {compactCurrency.format(loan.outstanding)}
                      </span>
                    </span>
                  </span>
                  <span className="w-16 shrink-0 text-right text-[10px] tabular-nums text-[var(--text-muted)]">
                    {loan.maturity.slice(0, 7)}
                  </span>
                </li>
              );
            })}
          </ul>

          <div className="mt-2 ml-[8.75rem] mr-[4.75rem] flex justify-between text-[10px] text-[var(--text-muted)]">
            <span>{start?.slice(0, 4)}</span>
            <span>{end?.slice(0, 4)}</span>
          </div>

          {/* Repayment wall: how much falls due each year. */}
          <div className="mt-5 border-t border-[var(--border)] pt-4">
            <p className="mb-2 text-xs font-medium text-[var(--text-muted)]">
              Falling due by year
            </p>
            <ul className="flex items-end gap-2">
              {maturities.map((bucket) => (
                <li
                  key={bucket.year}
                  className="flex min-w-0 flex-1 flex-col items-center"
                  title={`${bucket.year}: ${compactCurrency.format(
                    bucket.amount,
                  )} — ${bucket.loans.join(', ')}`}
                >
                  <span className="mb-1 text-[10px] tabular-nums text-[var(--text-muted)]">
                    {compactCurrency.format(bucket.amount)}
                  </span>
                  <span
                    className="w-full rounded-t-sm"
                    style={{
                      height: `${Math.max(
                        4,
                        (bucket.amount / (maxMaturity || 1)) * 48,
                      )}px`,
                      backgroundColor: WALL_COLOR,
                    }}
                  />
                  <span className="mt-1 text-[10px] text-[var(--text-muted)]">
                    {bucket.year}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
