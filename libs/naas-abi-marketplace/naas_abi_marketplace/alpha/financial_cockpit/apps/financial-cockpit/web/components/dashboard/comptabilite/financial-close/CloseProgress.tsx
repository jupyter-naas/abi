'use client';

import type { AreaProgress } from '@/lib/comptabilite/financialClose/model';

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 0,
});

/** Colors match the Task Status donut, so the two tiles read as one picture. */
const SEGMENTS: {
  key: keyof Pick<AreaProgress, 'done' | 'running' | 'blocked' | 'notStarted'>;
  label: string;
  color: string;
}[] = [
  { key: 'done', label: 'Done', color: 'var(--recovery-success)' },
  { key: 'running', label: 'In progress', color: 'var(--primary)' },
  { key: 'blocked', label: 'Blocked', color: 'var(--recovery-danger)' },
  {
    key: 'notStarted',
    label: 'Not started',
    color: 'color-mix(in srgb, var(--text-muted) 30%, var(--surface))',
  },
];

type CloseProgressProps = {
  title: string;
  hint?: string;
  areas: AreaProgress[];
  emptyMessage?: string;
};

/**
 * Where the close stands, area by area. Each bar is one area's checklist, every
 * task counted once at the state it is in, so the bar is always full — what
 * moves is the colour. Areas are ordered by completion, worst first: the bar at
 * the top is what is holding the close up.
 */
export function CloseProgress({
  title,
  hint,
  areas,
  emptyMessage = 'No close checklist for this perimeter.',
}: CloseProgressProps) {
  const total = areas.reduce((sum, area) => sum + area.total, 0);
  const done = areas.reduce((sum, area) => sum + area.done, 0);

  return (
    <div className="glass h-full rounded-lg p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          <span className="font-semibold tabular-nums text-[var(--text)]">
            {done}
          </span>{' '}
          of {total} tasks done
        </span>
      </div>

      {areas.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <ul className="space-y-2.5">
            {areas.map((area) => (
              <li key={area.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-medium" title={area.label}>
                    {area.label}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-[var(--text-muted)]">
                    {area.done}/{area.total} ·{' '}
                    <span className="font-semibold text-[var(--text)]">
                      {percentFormatter.format(area.completion)}
                    </span>
                  </span>
                </div>
                <div className="flex h-3 overflow-hidden rounded-sm progress-bar-bg">
                  {SEGMENTS.map((segment) => {
                    const count = area[segment.key];
                    if (count === 0) {
                      return null;
                    }
                    return (
                      <div
                        key={segment.key}
                        className="h-full transition-[width] duration-500"
                        style={{
                          width: `${(count / area.total) * 100}%`,
                          backgroundColor: segment.color,
                        }}
                        title={`${count} ${segment.label.toLowerCase()}`}
                      />
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-[var(--text-muted)]">
            {SEGMENTS.map((segment) => (
              <span key={segment.key} className="flex items-center gap-1.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: segment.color }}
                  aria-hidden
                />
                {segment.label}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
