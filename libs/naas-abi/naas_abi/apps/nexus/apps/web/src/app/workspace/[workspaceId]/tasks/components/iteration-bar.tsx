'use client';

import { Archive, Forward } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SCOPE_LABELS, formatWeekRange, parseIsoDate, type TaskIteration, type TasksScope } from '@/lib/tasks';

const SCOPE_DESCRIPTIONS: Partial<Record<TasksScope, string>> = {
  inbox: 'New requests waiting for triage. Drag one onto an iteration or the backlog.',
  backlog: 'Triaged tasks not scheduled in an iteration yet.',
};

export function IterationBar({
  scope,
  day,
  iteration,
  showArchived,
  canCarryOver,
  onToggleArchived,
  onCarryOver,
}: {
  scope: TasksScope;
  /** A day inside the shown iteration; null for Inbox and Backlog. */
  day: string | null;
  /** The scope's iteration; null until a task creates it. */
  iteration: TaskIteration | null;
  showArchived: boolean;
  canCarryOver: boolean;
  onToggleArchived: () => void;
  onCarryOver: () => void;
}) {
  return (
    <div className="tasks-iteration-bar">
      <div className="tasks-iteration-heading">
        <h2 className="tasks-iteration-title">{SCOPE_LABELS[scope]}</h2>
        <span className="tasks-iteration-range">
          {iteration
            ? `${formatWeekRange(iteration.start_date, iteration.end_date)} · ${iteration.iso_week}`
            : day
              ? `Not planned yet: ${scope === 'last' ? 'ended' : 'starts'} around ${parseIsoDate(day).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
              : SCOPE_DESCRIPTIONS[scope]}
        </span>
      </div>
      <div className="tasks-iteration-actions">
        {(scope === 'current' || scope === 'last') && (
          <button
            type="button"
            className="tasks-button"
            disabled={!canCarryOver}
            title="Move every task that is not Done to the following iteration"
            onClick={onCarryOver}
          >
            <Forward size={13} /> Move unfinished to next
          </button>
        )}
        <button
          type="button"
          className={cn('tasks-button', showArchived && 'tasks-button-active')}
          aria-pressed={showArchived}
          onClick={onToggleArchived}
        >
          <Archive size={13} /> {showArchived ? 'Hide archived' : 'Show archived'}
        </button>
      </div>
    </div>
  );
}
