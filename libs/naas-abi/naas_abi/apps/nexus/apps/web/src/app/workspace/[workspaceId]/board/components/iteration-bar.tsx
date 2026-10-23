'use client';

import { useEffect, useState } from 'react';
import { Archive, Forward } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SCOPE_LABELS, formatWeekRange, parseIsoDate, type BoardIteration, type BoardScope } from '@/lib/board';

const SCOPE_DESCRIPTIONS: Partial<Record<BoardScope, string>> = {
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
  onSaveGoal,
  onCarryOver,
}: {
  scope: BoardScope;
  /** A day inside the shown iteration; null for Inbox and Backlog. */
  day: string | null;
  /** The scope's iteration; null until a task or a goal creates it. */
  iteration: BoardIteration | null;
  showArchived: boolean;
  canCarryOver: boolean;
  onToggleArchived: () => void;
  onSaveGoal: (goal: string) => void;
  onCarryOver: () => void;
}) {
  const [goal, setGoal] = useState(iteration?.goal ?? '');
  useEffect(() => setGoal(iteration?.goal ?? ''), [iteration?.id, iteration?.goal]);

  return (
    <div className="board-iteration-bar">
      <div className="board-iteration-heading">
        <h2 className="board-iteration-title">{SCOPE_LABELS[scope]}</h2>
        <span className="board-iteration-range">
          {iteration
            ? `${formatWeekRange(iteration.start_date, iteration.end_date)} · ${iteration.iso_week}`
            : day
              ? `Not planned yet: ${scope === 'last' ? 'ended' : 'starts'} around ${parseIsoDate(day).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
              : SCOPE_DESCRIPTIONS[scope]}
        </span>
      </div>
      {day && (
        <label className="board-iteration-goal">
          <span className="board-iteration-goal-label">Goal</span>
          <input
            className="board-iteration-goal-input"
            value={goal}
            maxLength={200}
            placeholder="One line on what this iteration delivers"
            onChange={(e) => setGoal(e.target.value)}
            onBlur={() => goal.trim() !== (iteration?.goal ?? '') && onSaveGoal(goal.trim())}
            onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
          />
        </label>
      )}

      <div className="board-iteration-actions">
        {(scope === 'current' || scope === 'last') && (
          <button
            type="button"
            className="board-button"
            disabled={!canCarryOver}
            title="Move every task that is not Done to the following iteration"
            onClick={onCarryOver}
          >
            <Forward size={13} /> Move unfinished to next
          </button>
        )}
        <button
          type="button"
          className={cn('board-button', showArchived && 'board-button-active')}
          aria-pressed={showArchived}
          onClick={onToggleArchived}
        >
          <Archive size={13} /> {showArchived ? 'Hide archived' : 'Show archived'}
        </button>
      </div>
    </div>
  );
}
