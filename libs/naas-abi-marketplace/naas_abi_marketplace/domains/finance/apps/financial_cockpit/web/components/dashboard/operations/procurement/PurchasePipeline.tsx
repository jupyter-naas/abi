'use client';

import type { StageSummary } from '@/lib/operations/procurement/model';

const compactCurrency = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 0,
});

/**
 * Colour per stage: the two middle stages are live commitments — money
 * promised and not yet delivered — so they carry the warm tones.
 */
const STAGE_COLORS: Record<string, string> = {
  requested: 'color-mix(in srgb, var(--primary) 40%, var(--surface))',
  approved: 'var(--recovery-warning)',
  ordered: 'var(--recovery-orange)',
  received: 'var(--secondary)',
  invoiced: 'var(--recovery-success)',
};

type PurchasePipelineProps = {
  title: string;
  hint?: string;
  stages: StageSummary[];
  emptyMessage?: string;
};

/**
 * Where the order book sits right now: one row per stage, sized by the value
 * standing at it. This is a snapshot of the pipeline, not a funnel — an order
 * appears once, at the stage it has actually reached.
 */
export function PurchasePipeline({
  title,
  hint,
  stages,
  emptyMessage = 'No purchase orders for this perimeter.',
}: PurchasePipelineProps) {
  const total = stages.reduce((sum, stage) => sum + stage.amount, 0);
  const max = Math.max(...stages.map((stage) => stage.amount), 1);
  const orderCount = stages.reduce((sum, stage) => sum + stage.count, 0);

  return (
    <div className="glass rounded-lg p-6 h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          {orderCount} order{orderCount === 1 ? '' : 's'} ·{' '}
          <span className="font-semibold tabular-nums text-[var(--text)]">
            {compactCurrency.format(total)}
          </span>
        </span>
      </div>

      {total <= 0 && orderCount === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <ul className="space-y-3">
          {stages.map((stage) => {
            const widthPct = Math.max(
              stage.amount > 0 ? 3 : 0,
              Math.round((stage.amount / max) * 100),
            );
            return (
              <li key={stage.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-medium">
                    {stage.label}
                  </span>
                  <span className="shrink-0 text-sm tabular-nums">
                    {compactCurrency.format(stage.amount)}
                  </span>
                </div>
                <div className="progress-bar-bg h-3 overflow-hidden rounded-sm">
                  <div
                    className="h-full rounded-sm transition-[width] duration-500"
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: STAGE_COLORS[stage.key] ?? 'var(--primary)',
                    }}
                    title={`${stage.count} order${
                      stage.count === 1 ? '' : 's'
                    } standing at ${stage.label.toLowerCase()}`}
                  />
                </div>
                <p className="mt-1 text-[11px] tabular-nums text-[var(--text-muted)]">
                  {stage.count} order{stage.count === 1 ? '' : 's'} ·{' '}
                  {percentFormatter.format(total > 0 ? stage.amount / total : 0)} of the
                  book
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
