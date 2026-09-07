'use client';

import type { CloseRecord } from '@/lib/comptabilite/financialClose/model';

const ROW_HEIGHT_REM = 2.1;

/** Bar colour by task state — a late finish is flagged even though it is done. */
function barColor(task: CloseRecord): string {
  if (task.status === 'blocked') return 'var(--recovery-danger)';
  if (task.status === 'in_progress') return 'var(--primary)';
  return task.days_late > 0 ? 'var(--recovery-orange)' : 'var(--recovery-success)';
}

type GanttTimelineProps = {
  title: string;
  hint?: string;
  tasks: CloseRecord[];
  /** Business day the running close has reached; omitted once it is closed. */
  progressDay?: number | null;
  /** How many rows are visible before scrolling inside the tile. */
  visibleCount?: number;
  emptyMessage?: string;
};

/**
 * The close calendar, measured in **business days after the period end** rather
 * than in dates: that is how a close is actually planned, and it makes every
 * month directly comparable however the weekends fall.
 *
 * Each row carries the plan as a hollow track and what happened as a solid bar
 * on top, so an overrun reads as the bar running past its track.
 */
export function GanttTimeline({
  title,
  hint,
  tasks,
  progressDay = null,
  visibleCount = 10,
  emptyMessage = 'No close checklist for this perimeter.',
}: GanttTimelineProps) {
  const lastDay = Math.max(
    ...tasks.map((task) => Math.max(task.planned_end_day, task.actual_end_day)),
    1,
  );
  const days = Array.from({ length: lastDay }, (_, index) => index + 1);
  const pct = (day: number) => (day / lastDay) * 100;
  const scrollable = tasks.length > visibleCount;

  return (
    <div className="glass h-full rounded-lg p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className={`type-title-5${hint ? ' cursor-help' : ''}`} title={hint}>
          {title}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">
          Business days after the period end
        </span>
      </div>

      {tasks.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>
      ) : (
        <>
          <div className="mb-1 flex items-center gap-2">
            <span className="w-40 shrink-0" aria-hidden />
            <div className="flex min-w-0 flex-1">
              {days.map((day) => (
                <span
                  key={day}
                  className="min-w-0 flex-1 text-center text-[10px] text-[var(--text-muted)]"
                >
                  D{day}
                </span>
              ))}
            </div>
          </div>

          <ul
            className={`space-y-1 overflow-y-auto overscroll-contain pr-1${
              scrollable ? ' scrollbar-thin' : ''
            }`}
            style={{ maxHeight: `${visibleCount * ROW_HEIGHT_REM}rem` }}
            aria-label={
              scrollable ? `${title} — ${tasks.length} tasks, scrollable` : undefined
            }
          >
            {tasks.map((task) => {
              const start = task.planned_start_day - 1;
              const plannedWidth = task.planned_end_day - start;
              const actualEnd =
                task.status === 'done'
                  ? task.actual_end_day
                  : task.status === 'not_started'
                    ? start
                    : Math.max(progressDay ?? start, start);
              return (
                <li key={task.task_ref} className="flex items-center gap-2">
                  <span
                    className="w-40 shrink-0 truncate text-xs font-medium"
                    title={`${task.task_label} — ${task.owner}`}
                  >
                    {task.task_label}
                  </span>
                  <div className="relative min-w-0 flex-1">
                    {/* the plan */}
                    <div
                      className="h-4 rounded-sm border border-dashed border-[var(--border)]"
                      style={{
                        marginLeft: `${pct(start)}%`,
                        width: `${pct(plannedWidth)}%`,
                      }}
                      title={`Planned D${task.planned_start_day}–D${task.planned_end_day}`}
                    />
                    {/* what happened */}
                    {actualEnd > start ? (
                      <div
                        className="absolute inset-y-0.5 rounded-sm transition-[width] duration-500"
                        style={{
                          left: `${pct(start)}%`,
                          width: `${pct(actualEnd - start)}%`,
                          backgroundColor: barColor(task),
                        }}
                        title={`${task.status_label}${
                          task.days_late > 0 ? ` — ${task.days_late} d late` : ''
                        }`}
                      />
                    ) : null}
                    {progressDay !== null ? (
                      <div
                        className="pointer-events-none absolute inset-y-0 w-px bg-[var(--secondary)]"
                        style={{ left: `${pct(progressDay)}%` }}
                        aria-hidden
                      />
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>

          <p className="mt-3 text-xs text-[var(--text-muted)]">
            Dashed tracks are the plan, solid bars what happened — orange where a
            task overran it, red where it is blocked.
            {progressDay !== null
              ? ` The vertical rule marks day ${progressDay}, where this close has got to.`
              : ''}
          </p>
        </>
      )}
    </div>
  );
}
