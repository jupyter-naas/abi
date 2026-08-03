'use client';

import type { LedgerTrendPoint } from '@/lib/comptabilite/generalLedger/model';

const integerFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 0,
});

const CHART_HEIGHT_REM = 15;

type EntryVolumeChartProps = {
  title: string;
  hint?: string;
  points: LedgerTrendPoint[];
  emptyMessage?: string;
};

/**
 * Entries posted per month, split by how they got there: the imported bulk
 * that flows in from the source systems, and the manual entries a human keyed
 * stacked on top. Counting **entries** rather than lines is what makes the two
 * comparable — a sales invoice carries three lines and a manual accrual two,
 * so lines would exaggerate the automated half.
 */
export function EntryVolumeChart({
  title,
  hint,
  points,
  emptyMessage = 'No entries for this perimeter.',
}: EntryVolumeChartProps) {
  const max = Math.max(...points.map((point) => point.entries), 1);
  // Past ~24 months the labels stop fitting; thin them rather than overlap.
  const labelStep = Math.ceil(points.length / 12);

  return (
    <div className="glass h-full rounded-lg p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: 'var(--primary)' }}
              aria-hidden
            />
            Imported
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: 'var(--recovery-orange)' }}
              aria-hidden
            />
            Manual
          </span>
        </div>
      </div>

      {points.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div
            className="flex items-end gap-1"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            {points.map((point) => (
              <div
                key={point.period}
                className="flex min-w-0 flex-1 flex-col justify-end"
                title={`${point.label} — ${integerFormatter.format(
                  point.entries,
                )} entries (${integerFormatter.format(
                  point.manualEntries,
                )} manual, ${integerFormatter.format(point.lines)} lines)`}
              >
                <div
                  className="w-full rounded-t-sm transition-[height] duration-500"
                  style={{
                    height: `${(point.manualEntries / max) * 100}%`,
                    backgroundColor: 'var(--recovery-orange)',
                  }}
                />
                <div
                  className="w-full transition-[height] duration-500"
                  style={{
                    height: `${(point.importedEntries / max) * 100}%`,
                    backgroundColor: 'var(--primary)',
                  }}
                />
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-1">
            {points.map((point, index) => (
              <span
                key={point.period}
                className="min-w-0 flex-1 truncate text-center text-[10px] text-[var(--text-muted)]"
              >
                {index % labelStep === 0 ? point.label : ''}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
