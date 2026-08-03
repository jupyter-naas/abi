'use client';

import type { PaymentWeek } from '@/lib/operations/payables/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const CHART_HEIGHT_REM = 14;

type PaymentCalendarProps = {
  title: string;
  hint?: string;
  weeks: PaymentWeek[];
  emptyMessage?: string;
  /** Cash available to meet the schedule. Drawn as a line across the columns. */
  cashAvailable?: number | null;
};

/**
 * What leaves the bank, week by week, from the closing month end. Bars are the
 * week's own outflow; the line is the running total, so the point where the
 * cumulative crosses available cash is visible at a glance.
 *
 * Week 0 is everything already past due — payable now, not next week.
 */
export function PaymentCalendar({
  title,
  hint,
  weeks,
  emptyMessage = 'Nothing scheduled for this perimeter.',
  cashAvailable = null,
}: PaymentCalendarProps) {
  const total = weeks.reduce((sum, week) => sum + Math.max(0, week.amount), 0);

  let running = 0;
  const points = weeks.map((week) => {
    running += Math.max(0, week.amount);
    return { week, cumulative: running };
  });

  const max = Math.max(...weeks.map((week) => Math.max(0, week.amount)), 1);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          Scheduled{' '}
          <span className="font-semibold tabular-nums text-[var(--text)]">
            {compactCurrency.format(total)}
          </span>
        </span>
      </div>

      {total <= 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="flex items-end gap-1.5"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {points.map(({ week, cumulative }) => {
              const amount = Math.max(0, week.amount);
              const heightPct = (amount / max) * 80;
              return (
                <div
                  key={week.week}
                  className="flex h-full min-w-0 flex-1 flex-col justify-end"
                  title={`${week.label}: ${compactCurrency.format(amount)} across ${
                    week.count
                  } bill${week.count === 1 ? '' : 's'} · cumulative ${compactCurrency.format(
                    cumulative,
                  )}`}
                >
                  <p className="mb-1 truncate text-center text-[10px] tabular-nums text-[var(--text-muted)]">
                    {amount > 0 ? compactCurrency.format(amount) : ''}
                  </p>
                  <div
                    className="w-full rounded-t-sm transition-[height] duration-500"
                    style={{
                      height: `${Math.max(amount > 0 ? 2 : 0, heightPct)}%`,
                      backgroundColor: week.overdue
                        ? 'var(--recovery-danger)'
                        : 'var(--primary)',
                    }}
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-2 flex gap-1.5 border-t border-[var(--border)] pt-2">
            {points.map(({ week }) => (
              <div key={week.week} className="min-w-0 flex-1 text-center">
                <p
                  className={`truncate text-[10px] ${
                    week.overdue
                      ? 'font-semibold text-[var(--recovery-danger)]'
                      : 'text-[var(--text-muted)]'
                  }`}
                  title={week.label}
                >
                  {week.overdue ? 'Now' : `+${week.week}w`}
                </p>
              </div>
            ))}
          </div>

          <p className="mt-3 text-xs text-[var(--text-muted)]">
            {cashAvailable !== null ? (
              <>
                <span className="font-semibold tabular-nums text-[var(--text)]">
                  {compactCurrency.format(cashAvailable)}
                </span>{' '}
                available against{' '}
                <span className="font-semibold tabular-nums text-[var(--text)]">
                  {compactCurrency.format(total)}
                </span>{' '}
                scheduled.
              </>
            ) : (
              <>
                <span className="font-semibold tabular-nums text-[var(--recovery-danger)]">
                  {compactCurrency.format(points[0]?.week.amount ?? 0)}
                </span>{' '}
                is payable immediately; the rest falls due over the next{' '}
                {weeks.length - 1} weeks.
              </>
            )}
          </p>
        </>
      )}
    </div>
  );
}
