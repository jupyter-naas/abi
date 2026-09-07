'use client';

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

const CHART_HEIGHT_REM = 13;

/**
 * Bucket colours run from healthy to alarming, left to right. Aging is always
 * ordered youngest-first, so the ramp reads as "how far right is the money".
 */
const BUCKET_COLORS = [
  'var(--recovery-success)',
  'var(--recovery-warning)',
  'var(--recovery-orange)',
  'color-mix(in srgb, var(--recovery-danger) 70%, var(--recovery-orange))',
  'var(--recovery-danger)',
];

export type AgingBucketBar = {
  key: string;
  label: string;
  amount: number;
  count: number;
  /** Share of the total open balance, 0–1. */
  share: number;
};

type AgingBarChartProps = {
  title: string;
  hint?: string;
  buckets: AgingBucketBar[];
  emptyMessage?: string;
  /** Noun for `bucket.count` ("invoice" → "6 invoices"). */
  countNoun?: string;
  /** Caption next to the total in the header. */
  totalLabel?: string;
};

/**
 * Open balance by days past due. The first bucket is everything still inside
 * terms, so a healthy book is heavily weighted to the left.
 */
export function AgingBarChart({
  title,
  hint,
  buckets,
  emptyMessage = 'No open balance for this perimeter.',
  countNoun = 'invoice',
  totalLabel = 'Total open',
}: AgingBarChartProps) {
  const total = buckets.reduce((sum, bucket) => sum + Math.max(0, bucket.amount), 0);
  const max = Math.max(...buckets.map((bucket) => Math.max(0, bucket.amount)), 1);
  // Everything past the first bucket is late money — the number the page is about.
  const overdue = buckets
    .slice(1)
    .reduce((sum, bucket) => sum + Math.max(0, bucket.amount), 0);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          {totalLabel}{' '}
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
            className="flex items-end gap-2 sm:gap-3"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {buckets.map((bucket, index) => {
              const amount = Math.max(0, bucket.amount);
              // Leave room above the tallest bar for its value label.
              const heightPct = (amount / max) * 82;
              return (
                <div
                  key={bucket.key}
                  className="flex h-full min-w-0 flex-1 flex-col justify-end"
                  title={`${bucket.label}: ${compactCurrency.format(amount)} · ${
                    bucket.count
                  } ${countNoun}${bucket.count === 1 ? '' : 's'} · ${percentFormatter.format(
                    bucket.share,
                  )}`}
                >
                  <p className="mb-1 truncate text-center text-[11px] font-semibold tabular-nums">
                    {amount > 0 ? compactCurrency.format(amount) : '—'}
                  </p>
                  <div
                    className="w-full rounded-t-sm transition-[height] duration-500"
                    style={{
                      height: `${Math.max(amount > 0 ? 2 : 0, heightPct)}%`,
                      backgroundColor: BUCKET_COLORS[index % BUCKET_COLORS.length],
                    }}
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-2 flex gap-2 border-t border-[var(--border)] pt-2 sm:gap-3">
            {buckets.map((bucket) => (
              <div key={bucket.key} className="min-w-0 flex-1 text-center">
                <p className="truncate text-[11px] font-medium" title={bucket.label}>
                  {bucket.label}
                </p>
                <p className="text-[10px] tabular-nums text-[var(--text-muted)]">
                  {percentFormatter.format(bucket.share)} · {bucket.count}
                </p>
              </div>
            ))}
          </div>

          <p className="mt-3 text-xs text-[var(--text-muted)]">
            <span className="font-semibold tabular-nums text-[var(--text)]">
              {compactCurrency.format(overdue)}
            </span>{' '}
            past due —{' '}
            {percentFormatter.format(total > 0 ? overdue / total : 0)} of the book.
          </p>
        </>
      )}
    </div>
  );
}
